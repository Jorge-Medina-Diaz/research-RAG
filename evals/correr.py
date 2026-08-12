"""
El arnés: corre el golden set y saca el informe.

    uv run rag eval                      # nivel 0 si no hay claves, completo si las hay
    uv run rag eval --nivel0             # solo recuperación: 0 llamadas a LLM
    uv run rag eval --k 5                # 5 intentos por probe -> ruido real
    uv run rag eval --ruido              # 5 corridas completas -> sigma
    uv run rag eval --solo P-04,P-07     # re-ejecuta solo lo que falló
    uv run rag eval --epoca 0            # mide a una época concreta
    uv run rag eval --diff runs/base.json

El informe agrupa por CATEGORÍA y por DIAGNÓSTICO, no por nota global. Una nota
global dice que algo va mal; el desglose dice qué palanca tocar.

**Nivel 0** mide solo recuperación —¿llegó el artefacto que contiene la
respuesta?— y no gasta ni una llamada. Es la señal más barata que existe, la que
corre en CI, y la única que funciona sin ninguna clave de API. Casi todo el
mundo se la salta.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from cerebro.almacen import epoca_medicion, migrar, sha_corpus  # noqa: E402
from cerebro.config import (  # noqa: E402
    INDEX_BOUND,
    PALANCAS,
    Palancas,
    huella,
    tabla_fragmentos,
)
from evals.entorno import (  # noqa: E402
    cargar,
    clasificar,
    comprobar_suelo_de_estrato,
    construir_entorno,
)
from evals.estadistica import (  # noqa: E402
    mcnemar_exacto,
    ruido,
    vuelcos,
    vuelcos_minimos_detectables,
)

#: Los suelos de spec.md. Un cambio que rompa uno no se acepta, mejore lo que
#: mejore. En RECUENTO y no en tasa donde importa: con n≈15 el semiancho del IC
#: al 95 % ronda ±25 puntos y un suelo de «0,85» no es exigible.
SUELOS_RECUENTO = {"R2": 0, "R4": 0, "R5": 0}
SUELO_RECALL = 0.85
SUELO_R6 = 0.95
SUELO_P95_MS = 8000


def hay_llm() -> bool:
    return (os.getenv("LLM_PROVIDER") or "mock").strip().lower() != "mock"


# --------------------------------------------------------------------------- #
# Identidad de corrida: las tres huellas
# --------------------------------------------------------------------------- #


def identidad(p: Palancas, epoca: int | None, usar_juez: bool) -> dict[str, Any]:
    """Lo que hace comparables (o no) dos corridas.

    Las tres son NUESTRAS. El `env_fingerprint` de Agno no incluye ni la
    configuración de recuperación ni el corpus, así que para un RAG se equivoca
    en las dos direcciones: se niega cuando afinas `instrucciones` y compara en
    silencio cuando ingieres artefactos.
    """
    from cerebro.scorer import JuezDeSpec

    sha, n = sha_corpus()
    return {
        "huella_config": huella(p, INDEX_BOUND),
        "epoca": epoca,
        "huella_juez": JuezDeSpec(p, usar_juez=usar_juez).digest()[:12],
        "corpus_sha": sha,
        "n_artefactos": n,
        "indice": tabla_fragmentos(p),
    }


def comparables(a: dict, b: dict) -> tuple[bool, list[str]]:
    motivos = []
    for clave, explica in (
        ("huella_config", "la configuración cambió: el delta mezclaría dos cosas"),
        ("epoca", "épocas distintas: el delta mezclaría sistema y corpus"),
        ("huella_juez", "el juez o la spec cambiaron: no es agregación, es cambiar la regla"),
    ):
        if a.get(clave) != b.get(clave):
            motivos.append(f"{clave}: {a.get(clave)} != {b.get(clave)} — {explica}")
    return not motivos, motivos


# --------------------------------------------------------------------------- #
# Nivel 0: recuperación, sin una sola llamada a LLM
# --------------------------------------------------------------------------- #


def medible_en_nivel0(pr: dict) -> bool:
    """El nivel 0 solo puede medir lo que se comprueba SIN respuesta.

    Una probe de `fuera_de_alcance` pregunta si el sistema se calla, y para eso
    hace falta que hable. Una probe sin `requiere` no declara qué artefacto
    debía llegar, así que su recall es trivialmente 1,0.

    Contarlas como fallo daría un 6/21 cuando la cifra honesta es 6/7. Y contarlas
    como acierto sería peor. No se cuentan: es una medición que no ocurrió, la
    misma semántica que Agno aplica a los intentos sin puntuar.
    """
    return pr["categoria"] != "fuera_de_alcance" and bool(pr.get("requiere"))


def nivel0(probes: list[dict], *, epoca: int | None, p: Palancas) -> list[dict]:
    from cerebro.recuperador import construir_recuperador

    filas = []
    for pr in probes:
        if not medible_en_nivel0(pr):
            filas.append({
                "id": pr["id"], "categoria": pr["categoria"],
                "clase": pr.get("clase", "dependiente"),
                "diagnostico": "no-medible", "recall": None,
                "rango_primer_esperado": None, "ms": 0,
                "recuperados": [], "esperados": list(pr.get("requiere") or []),
            })
            continue
        r = construir_recuperador(p, epoca=epoca, es_probe=True, probe_id=pr["id"])
        t0 = time.perf_counter()
        docs = r(pr["consulta"], num_documents=p.top_k)
        ms = (time.perf_counter() - t0) * 1000

        recuperados = [
            (d.get("meta_data") or {}).get("artefacto_id") for d in docs
        ]
        quiero = list(pr.get("requiere") or [])
        # recall@top_k por artefacto: ¿llegó el que contiene la respuesta?
        recall = (
            1.0 if not quiero
            else sum(1 for q in quiero if q in recuperados) / len(quiero)
        )
        # El rango del primer artefacto esperado: distingue «no llegó» (cobertura)
        # de «llegó en el puesto 27» (ordenación) sin necesidad de juez.
        rango = next(
            (i for i, a in enumerate(recuperados, 1) if a in quiero), None
        ) if quiero else None

        filas.append({
            "id": pr["id"], "categoria": pr["categoria"],
            "clase": pr.get("clase", "dependiente"),
            "recall": recall, "rango_primer_esperado": rango,
            "ms": round(ms), "recuperados": recuperados[:5], "esperados": quiero,
            "diagnostico": (
                "ninguno" if recall == 1.0 and (rango or 99) <= 3
                else "cobertura" if recall < 1.0
                else "ordenacion"
            ),
        })
    return filas


# --------------------------------------------------------------------------- #
# Nivel completo: rollouts + juez
# --------------------------------------------------------------------------- #


def completo(probes: list[dict], *, epoca: int | None, p: Palancas, k: int) -> list[dict]:
    from agno.environments import run_rollouts

    env = construir_entorno(probes, epoca=epoca, p=p, usar_juez=True)
    res = run_rollouts(env, k=k, concurrency=2)

    filas = []
    for tr in res.task_results:
        puntuados = [a.score for a in tr.attempts if a.score is not None]
        # Los intentos sin puntuar se EXCLUYEN, no se cuentan como cero: un
        # timeout no es una respuesta incorrecta. Lo hace Agno y aquí se respeta.
        detalles = [s.detail or {} for s in puntuados]
        diag = Counter(d.get("diagnostico", "ninguno") for d in detalles)
        incumple = Counter(r for d in detalles for r in d.get("incumple", []))
        filas.append({
            "id": tr.task.id,
            "categoria": (tr.task.metadata or {}).get("categoria", "?"),
            "clase": (tr.task.metadata or {}).get("clase", "dependiente"),
            "pass_rate": tr.pass_rate,
            "n_puntuados": tr.n_scored, "n_sin_puntuar": tr.n_unscored,
            "en_zona_de_aprendizaje": tr.in_learning_zone,
            "diagnostico": diag.most_common(1)[0][0] if diag else "ninguno",
            "incumple": dict(incumple),
            "motivos": {r: m for d in detalles for r, m in (d.get("motivos") or {}).items()},
        })
    return filas


# --------------------------------------------------------------------------- #
# Informe
# --------------------------------------------------------------------------- #


def informe(filas: list[dict], suspendidas, ident: dict, *, es_nivel0: bool) -> dict:
    # Las no medibles quedan fuera del denominador. El número honesto es sobre
    # lo que de verdad se midió.
    medidas = [f for f in filas if f["diagnostico"] != "no-medible"]
    no_medibles = [f for f in filas if f["diagnostico"] == "no-medible"]
    n = len(medidas)
    if es_nivel0:
        pasan = sum(1 for f in medidas if f["diagnostico"] == "ninguno")
        recall = statistics.mean(f["recall"] for f in medidas) if medidas else 0.0
        p95 = (
            sorted(f["ms"] for f in medidas)[max(0, int(n * 0.95) - 1)] if medidas else 0
        )
    else:
        pasan = sum(1 for f in medidas if (f.get("pass_rate") or 0) >= 1.0)
        recall = float("nan")
        p95 = 0

    print(f"\n{'─' * 68}")
    print(f"  {'NIVEL 0 · solo recuperación' if es_nivel0 else 'COMPLETO'}")
    print(f"  huella config {ident['huella_config']}  ·  época {ident['epoca']}  "
          f"·  juez {ident['huella_juez']}")
    print(f"  corpus {ident['n_artefactos']} artefactos · sha {ident['corpus_sha']}")
    print(f"\n  pasan {pasan}/{n}" + (f"   recall@top_k {recall:.2f}   p95 {p95/1000:.1f}s"
                                      if es_nivel0 else ""))

    if no_medibles:
        cats = Counter(f["categoria"] for f in no_medibles)
        print(f"  {len(no_medibles)} no medibles en nivel 0 "
              f"({', '.join(f'{c}:{n_}' for c, n_ in sorted(cats.items()))})"
              " — necesitan respuesta, no solo recuperación")

    por_cat: dict[str, list[dict]] = defaultdict(list)
    for f in medidas:
        por_cat[f["categoria"]].append(f)
    print("\n  por categoría")
    for cat, fs in sorted(por_cat.items()):
        ok = sum(1 for x in fs if x["diagnostico"] == "ninguno") if es_nivel0 else \
            sum(1 for x in fs if (x.get("pass_rate") or 0) >= 1.0)
        print(f"    {cat:<20} {ok}/{len(fs)}")

    fallos = [f for f in medidas if f["diagnostico"] != "ninguno"]
    if fallos:
        from cerebro.config import DIAGNOSTICO_A_PALANCAS

        print("\n  por diagnóstico — cada uno abre un juego de palancas distinto")
        for d, c in Counter(f["diagnostico"] for f in fallos).most_common():
            palancas = ", ".join(DIAGNOSTICO_A_PALANCAS.get(d, ("—",))[:4])
            print(f"    {d:<14} {c:>2}   → {palancas}")

    if suspendidas:
        print(f"\n  suspendidas ({len(suspendidas)}) — no puntúan ni a favor ni en contra")
        for pr, motivo in suspendidas:
            print(f"    {pr['id']:<6} {motivo}")

    # Suelos
    print("\n  suelos")
    if es_nivel0:
        ok_recall = recall >= SUELO_RECALL
        ok_p95 = p95 <= SUELO_P95_MS
        m = "ok  " if ok_recall else "ROTO"
        print(f"    {m}  recall@top_k ≥ {SUELO_RECALL} ({recall:.2f})")
        print(f"    {'ok  ' if ok_p95 else 'ROTO'}  latencia p95 ≤ 8s ({p95/1000:.1f}s)")
        print("    —     R2/R4/R5/R6 no se comprueban en nivel 0: necesitan respuesta")
    else:
        for regla, tope in SUELOS_RECUENTO.items():
            v = sum(f["incumple"].get(regla, 0) for f in medidas)
            m = "ok  " if v <= tope else "ROTO"
            print(f"    {m}  {regla} · {v} violación(es), tope {tope}")

    print()
    return {
        "fecha": datetime.now(UTC).isoformat(),
        "identidad": ident,
        "nivel": "0" if es_nivel0 else "completo",
        "resumen": {"pasan": pasan, "total": n, "no_medibles": len(no_medibles),
                    "recall": recall, "p95_ms": p95},
        "probes": filas,
        "suspendidas": [{"id": pr["id"], "motivo": m} for pr, m in suspendidas],
    }


def diffear(actual: dict, base_path: Path) -> int:
    base = json.loads(base_path.read_text(encoding="utf-8"))
    ok, motivos = comparables(actual["identidad"], base["identidad"])
    print(f"\n  diff contra {base_path.name}")
    if not ok:
        print("\n  NO COMPARABLE:")
        for m in motivos:
            print(f"    · {m}")
        print(
            "\n  Esto no es un aviso, es una negativa. Comparar de todos modos daría\n"
            "  un número que mezcla dos causas y no se puede atribuir a ninguna.\n"
        )
        return 2

    pas_b = {f["id"]: f["diagnostico"] == "ninguno"
             for f in base["probes"] if f["diagnostico"] != "no-medible"}
    pas_a = {f["id"]: f["diagnostico"] == "ninguno"
             for f in actual["probes"] if f["diagnostico"] != "no-medible"}
    b, c, mejoran = vuelcos(pas_b, pas_a)
    p = mcnemar_exacto(b, c)
    minimo = vuelcos_minimos_detectables()

    print(f"    empeoran {b}  ·  mejoran {c}  ·  McNemar p={p:.4f}")
    if mejoran:
        print(f"    mejoran: {', '.join(mejoran)}")
    if max(b, c) < minimo:
        print(
            f"\n    Con este tamaño de golden set hacen falta {minimo} vuelcos netos\n"
            "    para detectar nada. Por debajo, ninguna corrección estadística lo\n"
            "    cambia: es el suelo del instrumento, no del método.\n"
        )
    return 0


# --------------------------------------------------------------------------- #


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--nivel0", action="store_true", help="solo recuperación, 0 llamadas")
    ap.add_argument("--k", type=int, default=1, help="intentos por probe (nivel completo)")
    ap.add_argument("--ruido", action="store_true", help="5 corridas idénticas → σ")
    ap.add_argument("--solo", default="", help="ids separados por coma")
    ap.add_argument("--epoca", type=int, default=None, help="época de medición")
    ap.add_argument("--json", default="", help="vuelca el informe")
    ap.add_argument("--diff", default="", help="compara contra un informe anterior")
    args = ap.parse_args()

    migrar()
    p = PALANCAS
    epoca = args.epoca if args.epoca is not None else epoca_medicion()
    es_nivel0 = args.nivel0 or not hay_llm()

    if es_nivel0 and not args.nivel0:
        print(
            "\n  Sin LLM_PROVIDER real: se corre el NIVEL 0 (solo recuperación).\n"
            "  Es la señal más barata que existe y la única que funciona sin claves."
        )

    probes = cargar()
    if args.solo:
        pedidos = {x.strip() for x in args.solo.split(",")}
        probes = [pr for pr in probes if pr["id"] in pedidos]

    activas, suspendidas = clasificar(probes, epoca=epoca, p=p)
    if not args.solo:
        comprobar_suelo_de_estrato(activas)
    if not activas:
        print("\n  no queda ninguna probe activa.\n")
        return 1

    ident = identidad(p, epoca, usar_juez=not es_nivel0)

    if args.ruido:
        valores = []
        for i in range(5):
            filas = nivel0(activas, epoca=epoca, p=p) if es_nivel0 else \
                completo(activas, epoca=epoca, p=p, k=1)
            med = [f for f in filas if f["diagnostico"] != "no-medible"]
            v = sum(1 for f in med if f["diagnostico"] == "ninguno") / max(len(med), 1)
            valores.append(v)
            print(f"  corrida {i + 1}/5: {v:.4f}")
        r = ruido(valores, n_probes=len([x for x in activas if x.get("requiere")]))
        print(f"\n  {r}\n")
        if not r.aceptable:
            print(
                "  2σ POR ENCIMA DE 0,08. No tienes un problema de RAG: tienes un\n"
                "  problema de medición, y automatizar encima de una medición rota\n"
                "  solo acelera el desastre. La Fase 0 no está terminada.\n"
            )
            return 1
        return 0

    filas = nivel0(activas, epoca=epoca, p=p) if es_nivel0 else \
        completo(activas, epoca=epoca, p=p, k=args.k)
    inf = informe(filas, suspendidas, ident, es_nivel0=es_nivel0)

    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(
            json.dumps(inf, ensure_ascii=False, indent=1, default=str), encoding="utf-8"
        )
        print(f"  informe en {args.json}\n")

    if args.diff:
        return diffear(inf, Path(args.diff))

    return 0 if inf["resumen"]["pasan"] == inf["resumen"]["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
