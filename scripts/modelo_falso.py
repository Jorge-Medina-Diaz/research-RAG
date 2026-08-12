"""
Un modelo guionizado que habla el protocolo de OpenAI.

    uv run rag falso        # lo levanta en :7799
    LLM_PROVIDER=falso      # en .env

Para qué existe: sin esto, «el sistema arranca sin claves» significa «solo el
nivel 0». Con esto significa **el nivel completo**: rollouts, tool calls,
output_schema, extracción de references, el scorer y las tres huellas — todo el
camino real de Agno, con el único trozo simulado siendo la inteligencia.

Y esa es exactamente la separación que interesa. Los bugs de fontanería —un
`response_format` mal parseado, un `references` vacío, un veredicto que no casa
con su esquema— no dependen de que el modelo sea listo, y son los que se llevan
la tarde. Con un modelo guionizado se cazan en segundos y gratis; lo que queda
para la primera corrida con clave de verdad es solo calidad.

NO sustituye a una corrida real. El modelo de aquí no razona: sigue un guion
deliberadamente tonto —responde siempre citando lo primero que le llegue— que
hace FALLAR las probes de `fuera_de_alcance`. Eso es a propósito: así se ejercita
también el camino de fallo, que es el que de verdad hay que ver funcionando.
"""

from __future__ import annotations

import json
import re
import sys
import time
import uuid
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from fastapi import FastAPI  # noqa: E402
from fastapi.responses import JSONResponse, StreamingResponse  # noqa: E402

ABSTENCION = "No lo tengo en la memoria."
ART = re.compile(r"'artefacto_id':\s*'([a-z0-9\-]+)'|\"artefacto_id\":\s*\"([a-z0-9\-]+)\"")

app = FastAPI(title="modelo falso")


def _ids_en(texto: str) -> list[str]:
    fuera = []
    for a, b in ART.findall(texto):
        i = a or b
        if i and i not in fuera:
            fuera.append(i)
    return fuera


def _desde_esquema(esquema: dict[str, Any]) -> Any:
    """Construye una instancia válida mínima a partir de un JSON Schema.

    Genérico a propósito: sirve para el Veredicto del juez y para cualquier
    output_schema futuro sin tocar este fichero.
    """
    tipo = esquema.get("type")
    if "enum" in esquema:
        return esquema["enum"][0]
    if "anyOf" in esquema:
        return _desde_esquema(esquema["anyOf"][0])
    if tipo == "object":
        props = esquema.get("properties", {})
        req = esquema.get("required", list(props))
        return {k: _desde_esquema(v) for k, v in props.items() if k in req}
    if tipo == "array":
        # Un elemento: una lista vacía haría que el scorer derive
        # `passed = bool(evaluadas) and ...` a False y todo fallaría por vacío,
        # que no es el camino que se quiere ejercitar.
        return [_desde_esquema(esquema.get("items", {"type": "string"}))]
    if tipo == "boolean":
        return True
    if tipo in ("integer", "number"):
        return 1
    return "guion"


def _veredicto(esquema: dict[str, Any], reglas: list[str]) -> dict[str, Any]:
    """El Veredicto, con una entrada por regla pedida. Todas cumplen."""
    base = _desde_esquema(esquema)
    if isinstance(base, dict) and "reglas" in base:
        base["reglas"] = [
            {"regla": r, "cumple": True, "motivo": ""} for r in (reglas or ["R3"])
        ]
        base["diagnostico"] = "ninguno"
    return base


#: Bitácora de lo que llega. Sin esto, depurar por qué una corrida sale vacía
#: es adivinar: uvicorn con log_level=warning no registra peticiones, y un log
#: vacío se lee como «no llamó» cuando puede ser «llamó y no se registró».
BITACORA = RAIZ / "runs" / "modelo-falso.log"


def _apuntar(linea: str) -> None:
    BITACORA.parent.mkdir(parents=True, exist_ok=True)
    with BITACORA.open("a", encoding="utf-8") as f:
        f.write(linea + "\n")


@app.post("/v1/chat/completions")
async def completions(cuerpo: dict[str, Any]) -> JSONResponse:
    mensajes = cuerpo.get("messages") or []
    herramientas = cuerpo.get("tools") or []
    formato = cuerpo.get("response_format") or {}
    stream = bool(cuerpo.get("stream"))
    texto_todo = json.dumps(mensajes, ensure_ascii=False)
    _apuntar(
        f"{len(mensajes)} msg(s) roles={[m.get('role') for m in mensajes]} "
        f"tools={[(t.get('function') or {}).get('name') for t in herramientas]} "
        f"formato={formato.get('type')} stream={stream}"
    )

    # --- salida estructurada (el juez) -----------------------------------
    if formato.get("type") == "json_schema":
        esquema = (formato.get("json_schema") or {}).get("schema") or {}
        reglas = re.findall(r"\bR\d\b", texto_todo)
        # solo las que el prompt pide evaluar, no las que aparezcan de pasada
        pedidas = re.search(r"REGLAS A EVALUAR\s*\n([^\n]+)", texto_todo)
        if pedidas:
            reglas = re.findall(r"R\d", pedidas.group(1))
        contenido = json.dumps(_veredicto(esquema, reglas), ensure_ascii=False)
        return _respuesta(contenido, stream=stream)

    # --- primera vuelta: pide búsqueda -----------------------------------
    tiene_tool = any(
        (t.get("function") or {}).get("name") == "search_knowledge_base" for t in herramientas
    )
    ya_busco = any(m.get("role") == "tool" for m in mensajes)
    if tiene_tool and not ya_busco:
        consulta = next(
            (m.get("content") for m in reversed(mensajes) if m.get("role") == "user"), ""
        )
        return _respuesta(
            None,
            stream=stream,
            tool_calls=[{
                "id": f"call_{uuid.uuid4().hex[:8]}",
                "type": "function",
                "function": {
                    "name": "search_knowledge_base",
                    "arguments": json.dumps({"query": str(consulta)[:300]}),
                },
            }],
        )

    # --- segunda vuelta: responde con lo recuperado ----------------------
    contexto = "\n".join(
        str(m.get("content", "")) for m in mensajes if m.get("role") == "tool"
    )
    ids = _ids_en(contexto)
    if not ids:
        return _respuesta(ABSTENCION, stream=stream)

    # Guion deliberadamente tonto: siempre responde, nunca se abstiene si le
    # llegó algo. Hace fallar `fuera_de_alcance` a propósito.
    return _respuesta(
        f"Segun la memoria, el punto relevante esta recogido en [[art:{ids[0]}]].",
        stream=stream,
    )


def _respuesta(
    contenido: str | None, tool_calls: list | None = None, *, stream: bool = False
):
    """Respuesta completa o en SSE, según lo pida el cliente.

    **El streaming no es opcional aquí.** `agno.environments._attempt_body` invoca
    siempre con `stream=True, stream_events=True`, y con motivo: el flujo puede
    atascarse DESPUÉS de la salida final, y un `arun` esperado entero se cancela
    y no deja nada. O sea que el camino que de verdad recorre el arnés es el de
    streaming — un doble de pruebas que solo hablara el modo completo probaría
    otra cosa, y dejaría pasar exactamente los bugs que se buscan.
    """
    ident = f"chatcmpl-{uuid.uuid4().hex[:12]}"
    creado = int(time.time())
    razon = "tool_calls" if tool_calls else "stop"

    if not stream:
        mensaje: dict[str, Any] = {"role": "assistant", "content": contenido}
        if tool_calls:
            mensaje["tool_calls"] = tool_calls
        return JSONResponse({
            "id": ident, "object": "chat.completion", "created": creado, "model": "falso",
            "choices": [{"index": 0, "message": mensaje, "finish_reason": razon}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        })

    def _trozo(delta: dict[str, Any], fin: str | None = None) -> str:
        cuerpo = {
            "id": ident, "object": "chat.completion.chunk", "created": creado,
            "model": "falso",
            "choices": [{"index": 0, "delta": delta, "finish_reason": fin}],
        }
        return f"data: {json.dumps(cuerpo, ensure_ascii=False)}\n\n"

    def generar():
        yield _trozo({"role": "assistant"})
        if tool_calls:
            for i, tc in enumerate(tool_calls):
                # El id y el nombre en el primer trozo, los argumentos en el
                # segundo: es como lo emite OpenAI y como el SDK espera
                # ensamblarlos por `index`.
                yield _trozo({"tool_calls": [{
                    "index": i, "id": tc["id"], "type": "function",
                    "function": {"name": tc["function"]["name"], "arguments": ""},
                }]})
                yield _trozo({"tool_calls": [{
                    "index": i,
                    "function": {"arguments": tc["function"]["arguments"]},
                }]})
        elif contenido:
            yield _trozo({"content": contenido})
        yield _trozo({}, fin=razon)
        yield "data: [DONE]\n\n"

    return StreamingResponse(generar(), media_type="text/event-stream")


@app.get("/salud")
def salud() -> dict[str, str]:
    return {"estado": "ok"}


def main() -> int:
    import uvicorn

    print("\n  modelo falso en http://127.0.0.1:7799")
    print("  pon LLM_PROVIDER=falso en .env y corre `uv run rag eval`\n")
    uvicorn.run(app, host="127.0.0.1", port=7799, log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
