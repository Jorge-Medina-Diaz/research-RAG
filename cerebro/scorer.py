"""
El juez, envuelto en el protocolo `Scorer` de Agno.

Dos piezas que parecen fontanería y no lo son:

**`passed` se deriva en código, nunca se toma del modelo.** El esquema del juez
podría llevar un campo `pasa` con la descripción «True solo si todas las reglas
cumplen», pero eso es una instrucción, no una garantía, y la métrica que titula
el informe no puede depender de que un modelo la respete.

**`digest()` sella la spec.** `agno.environments._scorer_digest` lanza
`FingerprintError` si el scorer no lo tiene, y el digest entra en el
`env_fingerprint`. Aquí metemos además el sha de `spec.md` y el de `reglas.py`,
así que tocar el juez, la spec o los comprobadores deterministas hace que toda
comparación con mediciones anteriores quede marcada como ilegal.

Eso es el escalón 6 impedido estructuralmente y no por educación: el agente
puede editar el juez —ejecuta Python arbitrario, nada se lo impide— y lo que no
puede es hacer que su edición cuente. El patrón está en `agno/scorer/judge.py:146`,
cuyo propio docstring dice que cambiar el juez «is an environment change».
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from agno.scorer import Score

from cerebro.config import JUEZ, PALANCAS, Palancas
from cerebro.juez import INSTRUCCIONES, Veredicto, construir_juez, juzgar
from cerebro.reglas import DEL_JUEZ, DETERMINISTAS, comprobar_deterministas

RAIZ = Path(__file__).resolve().parent.parent
SPEC = RAIZ / "cerebro" / "spec.md"
REGLAS_PY = RAIZ / "cerebro" / "reglas.py"


def _sha(ruta: Path) -> str:
    return hashlib.sha256(ruta.read_bytes()).hexdigest()[:12]


def fragmentos_de(salida: Any) -> list[dict]:
    """Los fragmentos recuperados, en orden.

    Trampa verificada en agno 2.8.6: `Document.to_dict()` devuelve solo
    {name, meta_data, content} — descarta `id` y `reranking_score`. Por eso el
    recuperador devuelve dicts propios: todo lo que el juez necesita viaja
    dentro de `meta_data`, que es lo único que sobrevive.
    """
    fuera: list[dict] = []
    for bloque in getattr(salida, "references", None) or []:
        for ref in getattr(bloque, "references", None) or []:
            if isinstance(ref, dict):
                fuera.append(ref)
    return fuera


def texto_de(salida: Any) -> str:
    try:
        return salida.get_content_as_string() if salida.content is not None else ""
    except Exception:
        return str(getattr(salida, "content", "") or "")


class JuezDeSpec:
    """Scorer de Agno. Un `Score` por intento, con el desglose en `detail`."""

    def __init__(self, p: Palancas = PALANCAS, *, usar_juez: bool = True) -> None:
        self.p = p
        # En modo mock el juez LLM no puede correr. Se comprueban solo las
        # reglas deterministas y se dice en el detalle, en vez de fingir un
        # veredicto que nadie ha emitido.
        self.usar_juez = usar_juez
        self._juez = None

    def _agente_juez(self):
        if self._juez is None:
            self._juez = construir_juez(self.p)
        return self._juez

    async def ascore(self, run: Any, expected: Any = None) -> Score:
        probe: dict = expected if isinstance(expected, dict) else {}
        respuesta = texto_de(run)
        fragmentos = fragmentos_de(run)
        reglas: list[str] = list(probe.get("reglas") or [])
        debe_abstenerse = probe.get("categoria") == "fuera_de_alcance"

        veredictos: dict[str, tuple[bool, str]] = comprobar_deterministas(
            respuesta, fragmentos, reglas=reglas, debe_abstenerse=debe_abstenerse
        )

        diagnostico = "ninguno"
        del_juez = [r for r in reglas if r in DEL_JUEZ]
        if del_juez and self.usar_juez:
            v: Veredicto = juzgar(
                self._agente_juez(),
                pregunta=probe.get("consulta", ""),
                respuesta=respuesta,
                espera=probe.get("espera", ""),
                reglas=del_juez,
                fragmentos=fragmentos,
            )
            for vr in v.reglas:
                veredictos[vr.regla] = (vr.cumple, vr.motivo)
            diagnostico = v.diagnostico

        # `passed` se deriva aquí. No se pregunta.
        evaluadas = list(veredictos)
        incumple = [r for r, (ok, _) in veredictos.items() if not ok]
        passed = bool(evaluadas) and not incumple
        valor = (len(evaluadas) - len(incumple)) / len(evaluadas) if evaluadas else 0.0

        if not passed and diagnostico == "ninguno":
            # Si solo fallaron reglas deterministas, el diagnóstico se infiere:
            # sin fragmentos es cobertura; con ellos, el prompt.
            diagnostico = "cobertura" if not fragmentos else "prompt"

        return Score(
            value=valor,
            passed=passed,
            reason=veredictos[incumple[0]][1] if incumple else None,
            detail={
                "diagnostico": diagnostico,
                "incumple": incumple,
                "motivos": {r: m for r, (ok, m) in veredictos.items() if not ok},
                "evaluadas": evaluadas,
                "juez_llm": bool(del_juez and self.usar_juez),
                "artefactos": [
                    (f.get("meta_data") or {}).get("artefacto_id") for f in fragmentos
                ],
                "abstuvo": respuesta.strip() == "No lo tengo en la memoria.",
            },
        )

    def score(self, run: Any, expected: Any = None) -> Score:
        import asyncio

        return asyncio.run(self.ascore(run, expected))

    def digest(self) -> str:
        """sha256 sobre TODO lo que define la regla de puntuación.

        La spec y los comprobadores deterministas entran junto al modelo y las
        instrucciones del juez. Si cualquiera cambia, el `env_fingerprint`
        cambia y `MismatchError` hace ilegal comparar con lo medido antes.

        `usar_juez` NO entra, y esa ausencia costó un lector externo. Estaba en
        el payload, así que comparar una corrida de nivel 0 con una de nivel
        completo imprimía «el juez o la spec cambiaron» — y no había cambiado
        ninguno de los dos: solo se había corrido con `--nivel0`. Un falso
        positivo, y de un detector que este repo defiende explícitamente
        diciendo que uno que se equivoca en las dos direcciones se deja de
        mirar. El nivel no es una propiedad del juez; es del arnés, y viaja en
        `identidad()` por su propia clave.
        """
        payload = {
            "modelo_juez": JUEZ,
            "instrucciones_juez": INSTRUCCIONES,
            "spec_sha": _sha(SPEC),
            "reglas_sha": _sha(REGLAS_PY),
            "deterministas": list(DETERMINISTAS),
            "del_juez": list(DEL_JUEZ),
        }
        canonico = json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
        return hashlib.sha256(canonico.encode()).hexdigest()
