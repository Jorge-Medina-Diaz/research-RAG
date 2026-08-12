"""
Calibración del juez. La puerta de la Fase 0.

    uv run rag calibrar --preparar     # escribe los casos, SIN el veredicto
    uv run rag calibrar --comparar     # α, α por regla, IC bootstrap

Un juez sesgado produce mejoras ilusorias que degradan el sistema, y no hay
optimizador que arregle una señal mala. Por eso esto existe y por eso bloquea.

  α ≥ 0,60                    adelante
  0,45 ≤ α < 0,60             AFINAR: mira las discrepancias POR REGLA. Si una
                              regla se lleva >50 %, reescribe SU línea
                              *Comprobable* — es el escalón más bajo que puede
                              expresar el fallo.
  α < 0,45                    BLOQUEA
  IC que cruza 0,60 con
  semiancho > 0,15            INDETERMINADO: hacen falta más casos

**El veredicto del juez va cifrado y la vista de etiquetado no lo lee.** Verlo
ancla, y una calibración anclada no mide nada.

**Y el techo no es 1,00.** En la meta-evaluación de RAGChecker el acuerdo entre
anotadores humanos fue 70,09. Con un solo anotador no hay techo inter-anotador;
el sustituto honesto es el techo INTRA: re-etiquetar 20 casos a ciegas siete
días después. Si α_intra < 0,70, lo roto es la rúbrica y no el juez — y eso
lleva a una acción distinta, así que confundirlos cuesta semanas.
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from evals.estadistica import bootstrap_ic, krippendorff_alpha  # noqa: E402

DIR = RAIZ / "evals" / "calibracion"
CASOS = DIR / "casos.md"
ETIQUETAS = DIR / "etiquetas.txt"
VEREDICTOS = DIR / "veredictos.b64"

LINEA = re.compile(r"^\s*(P-[\w\-]+)\s*:\s*(.+)$")
PAR = re.compile(r"(R\d)\s*=\s*([01])")


def _guardar_oculto(datos: dict) -> None:
    """base64, no cifrado fuerte. No protege de un atacante: protege de un
    vistazo. El anclaje es involuntario, y contra eso basta con que no se lea
    de reojo mientras etiquetas."""
    VEREDICTOS.write_text(
        base64.b64encode(json.dumps(datos, ensure_ascii=False).encode()).decode(),
        encoding="utf-8",
    )


def _leer_oculto() -> dict:
    return json.loads(base64.b64decode(VEREDICTOS.read_text(encoding="utf-8")))


def preparar(n: int, semilla: int) -> int:
    """Corre el golden set, guarda el veredicto del juez OCULTO y escribe los
    casos para que los etiquetes a ciegas."""
    import os
    import random

    if (os.getenv("LLM_PROVIDER") or "mock").strip().lower() == "mock":
        print(
            "\n  Calibrar exige un juez de verdad: en modo mock no hay veredicto que\n"
            "  comparar con el tuyo. Pon LLM_PROVIDER y su clave en .env.\n"
        )
        return 1

    from cerebro.almacen import epoca_medicion, migrar
    from cerebro.config import PALANCAS
    from cerebro.scorer import fragmentos_de, texto_de
    from evals.entorno import cargar, clasificar, construir_entorno

    migrar()
    epoca = epoca_medicion()
    activas, _ = clasificar(cargar(), epoca=epoca)
    rng = random.Random(semilla)
    rng.shuffle(activas)
    activas = activas[:n]

    from agno.environments import run_rollouts

    env = construir_entorno(activas, epoca=epoca, p=PALANCAS, usar_juez=True)
    res = run_rollouts(env, k=1, concurrency=2)

    juez: dict[str, dict[str, int]] = {}
    bloques: list[str] = []
    for tr in res.task_results:
        intento = tr.attempts[0] if tr.attempts else None
        if intento is None or intento.score is None:
            continue
        pr = tr.task.expected if isinstance(tr.task.expected, dict) else {}
        detalle = intento.score.detail or {}
        evaluadas = detalle.get("evaluadas") or []
        incumple = set(detalle.get("incumple") or [])
        juez[tr.task.id or "?"] = {r: int(r not in incumple) for r in evaluadas}

        salida = getattr(intento, "run", None) or getattr(intento, "output", None)
        respuesta = texto_de(salida) if salida is not None else "(no disponible)"
        frags = fragmentos_de(salida) if salida is not None else []
        trozos = "\n\n".join(
            f"[{i}] {(f.get('meta_data') or {}).get('artefacto_id', '?')}\n"
            f"{str(f.get('content', ''))[:600]}"
            for i, f in enumerate(frags, 1)
        ) or "(no se recuperó ningún fragmento)"

        bloques.append(
            f"### {tr.task.id}  ·  reglas: {', '.join(evaluadas)}\n\n"
            f"**Pregunta**\n{pr.get('consulta', '')}\n\n"
            f"**Respuesta del sistema**\n{respuesta}\n\n"
            f"**Comportamiento esperado**\n{pr.get('espera', '')}\n\n"
            f"**Fragmentos recuperados, en orden**\n```\n{trozos}\n```\n"
        )

    _guardar_oculto(juez)
    CASOS.write_text(
        "# Calibración del juez\n\n"
        f"{len(bloques)} casos, en orden aleatorio (semilla {semilla}).\n\n"
        "**El veredicto del juez NO está aquí.** Está en "
        f"`{VEREDICTOS.name}`, codificado, y esta vista no lo lee: verlo ancla, y "
        "una calibración anclada no mide nada.\n\n"
        "Para cada caso, decide POR REGLA si se cumple y añade una línea al final "
        "de este fichero:\n\n"
        "```\nP-01: R1=1 R4=1 R7=0\n```\n\n"
        "Cuando termines: `uv run rag calibrar --comparar`\n\n"
        "---\n\n" + "\n---\n\n".join(bloques) +
        "\n\n---\n\n## Tus etiquetas\n\n<!-- una línea por caso, aquí debajo -->\n",
        encoding="utf-8",
    )
    print(
        f"\n  {len(bloques)} casos en {CASOS.relative_to(RAIZ)}\n"
        f"  El veredicto del juez, oculto en {VEREDICTOS.name}\n\n"
        "  Etiqueta al final del fichero, una línea por caso:\n"
        "      P-01: R1=1 R4=1 R7=0\n\n"
        "  Con ~3 reglas por caso son unas 3 pulsaciones cada uno. Hazlo en DOS\n"
        "  sesiones y no en una: una tanda larga se etiqueta peor al final que al\n"
        "  principio, y eso es ruido correlacionado con la posición — el peor tipo.\n\n"
        "  Luego: uv run rag calibrar --comparar\n"
    )
    return 0


def comparar() -> int:
    if not ETIQUETAS.exists() and not CASOS.exists():
        print(f"\n  no hay nada que comparar: falta {CASOS.relative_to(RAIZ)}\n")
        return 1
    if not VEREDICTOS.exists():
        print(f"\n  falta {VEREDICTOS.name}: corre --preparar primero\n")
        return 1

    juez = _leer_oculto()
    fuente = ETIQUETAS if ETIQUETAS.exists() else CASOS
    mias: dict[str, dict[str, int]] = {}
    for linea in fuente.read_text(encoding="utf-8").splitlines():
        if m := LINEA.match(linea):
            pares = PAR.findall(m.group(2))
            if pares:
                mias[m.group(1)] = {r: int(v) for r, v in pares}

    if not mias:
        print(
            "\n  no encontré ninguna línea de etiquetas. El formato es:\n"
            "      P-0037: R1=1 R4=1 R7=0 R8=1\n"
        )
        return 1

    # Unidad = un caso. Cada unidad aporta sus reglas; el bootstrap remuestrea
    # CASOS y no decisiones, porque las decisiones dentro de un caso no son
    # independientes y remuestrearlas estrecha el intervalo artificialmente.
    por_regla: dict[str, list[list[int | None]]] = {}
    for caso, reglas in mias.items():
        if caso not in juez:
            continue
        for regla, valor in reglas.items():
            v_juez = juez[caso].get(regla)
            if v_juez is None:
                continue
            por_regla.setdefault(regla, []).append([valor, int(v_juez)])

    planas = [
        [mias[c][r], juez[c][r]]
        for c in mias if c in juez
        for r in mias[c] if r in juez[c]
    ]
    if not planas:
        print("\n  ningún caso coincide entre tus etiquetas y las del juez.\n")
        return 1

    alpha = krippendorff_alpha(planas)
    lo, hi = bootstrap_ic(planas, krippendorff_alpha, n=2000)

    print(f"\n  casos comparados: {len(mias)}  ·  decisiones: {len(planas)}")
    print(f"  α global = {alpha:.3f}   IC 95 % [{lo:.3f}, {hi:.3f}]\n")
    print("  α por regla — si una se lleva el desacuerdo, el problema es SU rúbrica")
    for regla, u in sorted(por_regla.items()):
        try:
            print(f"    {regla}  {krippendorff_alpha(u):.3f}   ({len(u)} decisiones)")
        except ValueError:
            print(f"    {regla}  —       ({len(u)} decisiones)")

    semiancho = (hi - lo) / 2
    print()
    if lo < 0.60 < hi and semiancho > 0.15:
        print(
            f"  INDETERMINADO. El IC cruza 0,60 con semiancho {semiancho:.2f}.\n"
            "  Etiqueta 30 casos más antes de decidir: con esta precisión, la\n"
            "  puerta la estaría abriendo el azar.\n"
        )
        return 2
    if alpha >= 0.60:
        print("  PUERTA ABIERTA. α ≥ 0,60. El bucle puede correr.")
        print("  Recuerda: el techo no es 1,00. Entre humanos, RAGChecker midió 70,09.\n")
        return 0
    if alpha >= 0.45:
        print(
            "  AFINAR. Mira las discrepancias por regla de arriba. Si una sola se\n"
            "  lleva más de la mitad, reescribe SU línea *Comprobable* en spec.md —\n"
            "  escalón 1, el más bajo que puede expresar el fallo. Si están\n"
            "  repartidas, el problema es el modelo del juez.\n"
        )
        return 1
    print(
        "  BLOQUEA. α < 0,45. El bucle NO corre.\n"
        "  Y antes de cambiar de modelo: mide tu techo intra. Re-etiqueta 20 casos\n"
        "  a ciegas dentro de una semana. Si α_intra < 0,70, lo roto es la rúbrica,\n"
        "  no el juez, y cambiar de modelo no arregla una tarea mal definida.\n"
    )
    return 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--preparar", action="store_true")
    ap.add_argument("--comparar", action="store_true")
    ap.add_argument("--n", type=int, default=60)
    ap.add_argument("--semilla", type=int, default=20260812)
    args = ap.parse_args()

    DIR.mkdir(parents=True, exist_ok=True)
    if args.preparar:
        return preparar(args.n, args.semilla)
    if args.comparar:
        return comparar()
    ap.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
