"""
La puerta 0, preparada hasta donde llega sin claves.

    uv run rag puerta          # dónde está cada mitad de la puerta, hoy
    uv run rag puerta --sigma  # mide la σ de RECUPERACIÓN (5 corridas, gratis)
    uv run rag puerta --casos  # escribe los 60 casos para que los etiquetes

## La puerta y sus dos mitades

    α ≥ 0,60   sobre ≥50 casos etiquetados a mano
    2σ ≤ 0,08  sobre 5 corridas idénticas

Lleva cerrada desde el primer día y nunca se ha intentado abrir. Las dos mitades
tienen costes muy distintos y conviene no tratarlas igual:

**σ se puede medir hoy, gratis y del todo** — para la parte de recuperación.
Cinco corridas de nivel 0 no gastan una llamada, y su desviación típica es una
cifra real. Lo que no cubre es el ruido del JUEZ, que necesita un modelo.

Y hay una trampa que este script se niega a pisar: contra el modelo guionizado σ
sale **0,0000**, y ese cero no significa «excelente». Significa que el guion es
determinista, así que la medición valida la tubería y no dice nada del ruido.
Reportarlo como si pasara la puerta sería el fallo más caro posible, porque es
el único que se ve como un éxito.

**α no se puede medir sin dos cosas: un modelo real y tu tiempo.** Ni una ni
otra las puede poner este script. Lo que sí puede es dejar los casos escritos y
barajados para que etiquetarlos sea una tarde y no un proyecto.

## Por qué los casos se barajan y el veredicto del juez se oculta

Porque etiquetar viendo lo que dijo el juez no mide acuerdo: mide anclaje. Y con
un solo anotador el sesgo no tiene contrapeso — no hay un segundo humano que
discrepe. El orden aleatorio con semilla fija y el veredicto oculto son lo
mínimo, y aun así el α que salga será más frágil que el 70,09 de RAGChecker,
que tenía varios anotadores.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from cerebro.config import cargar_env  # noqa: E402

cargar_env()

SEMILLA = 20260812
DESTINO = RAIZ / "runs" / "calibracion-casos.json"
MIN_CASOS = 50
UMBRAL_ALPHA = 0.60
UMBRAL_2SIGMA = 0.08


def medir_sigma(n: int = 5) -> dict:
    """σ de la señal de RECUPERACIÓN, sobre n corridas idénticas. Cero llamadas.

    Es la mitad de la puerta que sí se puede cerrar hoy. La otra mitad —el ruido
    del juez— necesita un modelo, y mezclarlas en un solo número escondería cuál
    de las dos domina, que es justo el diagnóstico que hace falta para saber si
    la ronda siguiente se gasta en `top_k` o en la rúbrica.
    """
    from evals.estadistica import ruido
    from evals.mutar import _correr

    valores, recalls = [], []
    for _ in range(n):
        r = _correr()
        valores.append(r["pasan"] / max(r["n"], 1))
        recalls.append(r["recall"])

    n_probes = _correr()["n"]
    rr = ruido(valores, n_probes=n_probes)
    return {
        "n_corridas": n,
        "n_probes": n_probes,
        "tasas": valores,
        "recalls": recalls,
        "sigma": rr.sigma,
        "dos_sigma": 2 * rr.sigma,
        "resolucion": rr.resolucion,
        "aceptable": rr.aceptable,
        "pasa": 2 * rr.sigma <= UMBRAL_2SIGMA,
        "cubre": "solo recuperación — el ruido del JUEZ necesita un modelo real",
    }


def preparar_casos(cuantos: int = 60) -> int:
    """Escribe los casos para etiquetar a ciegas. Los baraja y oculta el juicio.

    Cada caso es una probe con su consulta y lo que se espera. Etiquetar es
    decir si una respuesta cumple, así que hacen falta respuestas — y sin modelo
    no las hay. Lo que se deja preparado es el ANDAMIO: la lista, el orden fijo,
    el hueco de la etiqueta y el del veredicto del juez, para que el día que
    haya clave sea `rag calibrar` y no montar esto.
    """
    from evals.entorno import cargar

    probes = list(cargar())
    rng = random.Random(SEMILLA)
    rng.shuffle(probes)

    casos = [
        {
            "n": i,
            "probe": pr["id"],
            "categoria": pr["categoria"],
            "consulta": pr["consulta"],
            "espera": pr.get("espera", ""),
            "reglas": pr.get("reglas", []),
            # Se rellenan cuando haya modelo. El del juez va SEPARADO y se
            # oculta al etiquetar: verlo no mide acuerdo, mide anclaje.
            "respuesta": None,
            "etiqueta_humana": None,
            "veredicto_juez": None,
        }
        for i, pr in enumerate(probes[:cuantos], start=1)
    ]

    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    DESTINO.write_text(
        json.dumps(
            {
                "semilla": SEMILLA,
                "orden": "barajado con semilla fija: reproducible y no alfabético",
                "instrucciones": (
                    "Etiqueta `etiqueta_humana` con true o false: ¿la respuesta "
                    "cumple TODAS las reglas que la probe declara? No mires "
                    "`veredicto_juez` — verlo convierte la medición de acuerdo en "
                    "una medición de anclaje, y con un solo anotador no hay nada "
                    "que compense ese sesgo."
                ),
                "casos": casos,
            },
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
    return len(casos)


def _alpha_medida() -> float | None:
    f = RAIZ / "runs" / "calibracion.json"
    if not f.exists():
        return None
    try:
        return float(json.loads(f.read_text(encoding="utf-8")).get("alpha"))
    except (ValueError, TypeError, KeyError):
        return None


def informe(sigma: dict | None) -> int:
    import os

    print(f"\n{'─' * 70}")
    print("  PUERTA 0 → 1\n")
    print(f"    α ≥ {UMBRAL_ALPHA}    sobre ≥{MIN_CASOS} casos etiquetados a mano")
    print(f"    2σ ≤ {UMBRAL_2SIGMA}  sobre 5 corridas idénticas\n")

    a = _alpha_medida()
    print(f"  α    {'sin medir' if a is None else f'{a:.3f}'}"
          f"{'' if a is None else ('  ✓' if a >= UMBRAL_ALPHA else '  ✗')}")
    if a is None:
        print("       Necesita un modelo real Y tu tiempo etiquetando. Ninguna de")
        print("       las dos las puede poner un script.")

    if sigma is None:
        print("\n  2σ   sin medir en esta ejecución — `--sigma` la mide (gratis)")
    else:
        prov = (os.getenv("LLM_PROVIDER") or "mock").lower()
        print(f"\n  2σ   {sigma['dos_sigma']:.4f}"
              f"{'  ✓' if sigma['pasa'] else '  ✗'}   ({sigma['cubre']})")
        print(f"       σ={sigma['sigma']:.4f} sobre {sigma['n_corridas']} corridas "
              f"de {sigma['n_probes']} probes")
        print(f"       resolución del instrumento 1/n = {sigma['resolucion']:.4f}")
        if sigma["sigma"] == 0.0 and prov in ("mock", "falso"):
            print("\n       ⚠  σ = 0,0000 con LLM_PROVIDER="
                  f"{prov}. Ese cero NO es «excelente»:")
            print("          la recuperación es determinista por construcción, así que")
            print("          valida la tubería y no dice NADA del ruido real. Contarlo")
            print("          como media puerta abierta sería el fallo más caro posible,")
            print("          porque es el único que se ve como un éxito.")

    print(f"\n  casos preparados: {'sí' if DESTINO.exists() else 'no'}"
          f"  ({DESTINO.relative_to(RAIZ)})")
    print("\n  La puerta está CERRADA y su mitad cara necesita una clave y una")
    print("  tarde tuya. Lo que este script deja hecho es que ese día no haya")
    print("  que montar nada: solo etiquetar.\n")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sigma", action="store_true")
    ap.add_argument("--casos", action="store_true")
    a = ap.parse_args()

    if a.casos:
        n = preparar_casos()
        print(f"\n  {n} casos escritos en {DESTINO.relative_to(RAIZ)}")
        print("  Barajados con semilla fija y con el veredicto del juez oculto.\n")

    s = medir_sigma() if a.sigma else None
    return informe(s)


if __name__ == "__main__":
    raise SystemExit(main())
