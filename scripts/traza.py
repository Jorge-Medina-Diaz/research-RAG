"""
Una consulta, de punta a punta, con todo lo que pasó por el camino.

    uv run rag traza "¿de dónde sale el 60 de RRF?"
    uv run rag traza --probe P-32
    uv run rag traza --probe P-32 --md docs/traza-ejemplo.md

Para qué existe: un RAG que da una buena respuesta y un RAG que da una buena
respuesta POR CASUALIDAD son indistinguibles desde fuera. Lo único que los
separa es el reparto por carril y el rango de cada fragmento ANTES de fusionar,
y esa información deja de existir en cuanto se fusiona.

Es también la pieza más didáctica del repo: en una pantalla se ve qué encontró
cada carril por separado, cómo RRF los mezcló, qué fragmentos llegaron al
prompt, qué respondió el modelo y qué dictaminó el juez regla por regla.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from cerebro.config import PALANCAS, cargar_env  # noqa: E402

cargar_env()


def _linea(car: str = "─", n: int = 74) -> str:
    return car * n


def traza(consulta: str, *, probe: dict | None = None) -> list[str]:
    """Devuelve la traza como lista de líneas, en markdown plano."""
    import asyncio

    from cerebro.agente import construir_agente
    from cerebro.almacen import epoca_medicion
    from cerebro.recuperador import construir_recuperador

    p = PALANCAS
    epoca = epoca_medicion()
    out: list[str] = []
    w = out.append

    w("## 1 · La pregunta\n")
    w(f"> {consulta}\n")
    if probe:
        w(f"Probe `{probe['id']}` · categoría `{probe['categoria']}` · "
          f"clase `{probe.get('clase', 'dependiente')}`\n")
        if req := probe.get("requiere"):
            w("Artefactos que **debían** llegar:\n")
            for r in req:
                w(f"- `{r}`")
            w("")

    # --- recuperación ------------------------------------------------------
    r = construir_recuperador(p, epoca=epoca, es_probe=False)
    docs = r(consulta, num_documents=p.top_k)

    w("## 2 · Los dos carriles, por separado\n")
    w("Cada carril busca a su manera y produce su propio orden. Este es el dato")
    w("que deja de existir en cuanto se fusiona, y sin él `peso_carril`, el")
    w("embedder y el analizador léxico son tres movimientos indistinguibles.\n")

    por_carril: dict[str, list[tuple[float, str]]] = {}
    for d in docs:
        for carril, info in (d.get("meta_data", {}).get("por_carril") or {}).items():
            por_carril.setdefault(carril, []).append((info["rango"], d["name"]))
    for carril in sorted(por_carril):
        # «de los N finales» y no «N de N venían de aquí»: un fragmento puede
        # venir de LOS DOS carriles, así que las dos cifras pueden sumar más
        # que el total sin que haya contradicción. La redacción anterior daba a
        # entender exclusividad y sumaba 24 sobre 12.
        w(f"**{carril}** — respaldó {len(por_carril[carril])} de los "
          f"{len(docs)} fragmentos que acabaron entrando\n")
        w("| puesto que tenía aquí | artefacto |")
        w("|---:|---|")
        for rango, nombre in sorted(por_carril[carril]):
            w(f"| {rango:.0f} | `{nombre}` |")
        w("")
        w("_Los puestos que faltan son candidatos que este carril colocaba por "
          "delante y que el otro no respaldó, así que no sobrevivieron a la "
          "fusión._\n")
    if not por_carril:
        w("_Ningún carril reportó rangos: la traza está rota o los dos vinieron vacíos._\n")

    # --- fusión ------------------------------------------------------------
    w(f"## 3 · La fusión (RRF, k={p.k_rrf})\n")
    w("RRF ignora las puntuaciones y usa solo los puestos, que es lo que lo hace")
    w("inmune a mezclar escalas incomparables. Un documento que sale en los dos")
    w("carriles suma dos veces, así que el **acuerdo** pesa más que un primer")
    w("puesto solitario.\n")
    w("| # | artefacto · fragmento | RRF | puesto en cada carril |")
    w("|---:|---|---:|---|")
    for i, d in enumerate(docs, 1):
        m = d.get("meta_data", {})
        rangos = m.get("por_carril") or {}
        etiq = ", ".join(f"{c} #{v['rango']:.0f}" for c, v in sorted(rangos.items())) or "—"
        frag = str(m.get("doc_id", ""))[-6:]
        w(f"| {i} | `{d['name']}` · `…{frag}` | "
          f"{m.get('score_fusion', 0):.5f} | {etiq} |")
    w("")
    w(f"De un pool de {p.pool_fusion} candidatos por carril salen los "
      f"**{len(docs)}** que llegan al prompt.\n")

    # --- generación --------------------------------------------------------
    w("## 4 · La respuesta\n")
    try:
        agente = construir_agente(p, epoca=None)
        res = asyncio.run(agente.arun(consulta))
        respuesta = (res.content or "").strip()
        w("```")
        w(respuesta or "(vacía)")
        w("```\n")
    except Exception as exc:  # noqa: BLE001
        respuesta = ""
        w(f"_Sin modelo disponible ({type(exc).__name__}). "
          "Levanta `uv run rag falso` o pon una clave real._\n")

    # --- veredicto ---------------------------------------------------------
    if respuesta and probe:
        from cerebro.reglas import comprobar_deterministas

        decl = probe.get("reglas") or []
        w("## 5 · El veredicto, regla por regla\n")
        w("La spec tiene ocho reglas; cinco las decide código y tres el juez. "
          "Una probe no las declara todas: solo las que su caso pone a prueba. "
          f"Esta declara **{len(decl)}** —{', '.join(decl)}— y de esas, las que "
          "van por código son las de la tabla.\n")
        vs = comprobar_deterministas(
            respuesta,
            docs,
            reglas=probe.get("reglas") or [],
            debe_abstenerse=probe["categoria"] == "fuera_de_alcance",
        )
        w("| regla | veredicto | motivo |")
        w("|---|:---:|---|")
        for regla, (cumple, motivo) in sorted(vs.items()):
            w(f"| {regla} | {'✓' if cumple else '✗'} | {motivo or '—'} |")
        w("")
        if faltan := sorted(set(probe.get("reglas") or []) - set(vs)):
            w(f"Las reglas {', '.join(faltan)} las decide el juez LLM, no el "
              "código: dependen de criterio y por eso llevan su propia puerta "
              "de calibración.\n")

    # --- qué enseña --------------------------------------------------------
    w("## 6 · Qué enseña esta traza\n")
    llegaron = {d["name"] for d in docs}
    if probe and (req := probe.get("requiere")):
        for r in req:
            w(f"- {'✓' if r in llegaron else '✗'} `{r}`")
        falta = [r for r in req if r not in llegaron]
        w("")
        w("**Recall de esta probe: "
          f"{(len(req) - len(falta)) / len(req):.0%}.** "
          + ("Los dos artefactos que hacían falta llegaron, así que si la "
             "respuesta falla el problema está en el prompt o en la síntesis, "
             "no en la recuperación. Esa distinción es todo el valor del "
             "diagnóstico: dice qué palanca tocar."
             if not falta else
             f"Faltó `{falta[0]}`, así que el diagnóstico es `cobertura` y "
             "ningún ajuste de prompt lo arregla — el fragmento no llegó."))
        w("")
    # El ejemplo se CALCULA. Una versión anterior lo tenía escrito a mano
    # —«salió séptimo en denso y octavo en léxico»— dentro de un documento
    # generado, y los puestos reales eran otros. Un número inventado en medio
    # de una transcripción real es peor que no poner ninguno: contamina los que
    # sí son ciertos.
    w("Y lo que solo se ve aquí: **un artefacto puede ganar sin ser el primero "
      "de ningún carril.** RRF suma `1/(k+puesto)` de cada carril, así que el "
      "acuerdo entre dos formas distintas de buscar pesa más que la convicción "
      "de una sola.\n")
    ejemplo = next(
        (d for d in docs[1:]
         if len(d.get("meta_data", {}).get("por_carril") or {}) > 1
         and all(v["rango"] > 1 for v in d["meta_data"]["por_carril"].values())),
        None,
    )
    if ejemplo:
        i = docs.index(ejemplo) + 1
        pc = ejemplo["meta_data"]["por_carril"]
        detalle = " y ".join(f"{v['rango']:.0f}.º en {c}" for c, v in sorted(pc.items()))
        w(f"En esta corrida lo hace el número **{i}**: salió {detalle}, sin ser "
          f"primero en ninguno, y aun así entra por delante de candidatos mejor "
          f"situados en un solo carril.\n")
    w("Después de fusionar, esta información ya no existe. Por eso se captura "
      "**en el instante de la búsqueda** y se guarda en la tabla `consulta`: "
      "sin ella, mover `peso_carril`, cambiar de embedder y tocar el "
      "analizador léxico son tres movimientos indistinguibles.\n")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("consulta", nargs="?", default="")
    ap.add_argument("--probe", default="", help="id del golden set")
    ap.add_argument("--md", default="", help="escribe la traza en un .md")
    a = ap.parse_args()

    pr = None
    if a.probe:
        from evals.entorno import cargar

        pr = next((x for x in cargar() if x["id"] == a.probe), None)
        if pr is None:
            print(f"  no existe la probe {a.probe}")
            return 1
        a.consulta = pr["consulta"]
    if not a.consulta:
        print("  hace falta una consulta o --probe")
        return 1

    lineas = traza(a.consulta, probe=pr)
    if a.md:
        cab = [
            "# Una consulta, de punta a punta",
            "",
            "Generado con `uv run rag traza`. Todo lo de abajo salió de una ejecución",
            "real contra el corpus del repo, con el embedder determinista y el modelo",
            "guionizado — sin ninguna clave de API.",
            "",
        ]
        Path(a.md).write_text("\n".join(cab + lineas) + "\n", encoding="utf-8")
        print(f"  traza en {a.md}")
    else:
        print("\n" + _linea())
        print("\n".join(lineas))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
