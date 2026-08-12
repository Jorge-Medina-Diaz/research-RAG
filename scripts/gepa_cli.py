"""
GEPA desde la línea de comandos.

    uv run rag gepa                 # ¿se puede correr hoy? casi siempre no, y con cifra
    uv run rag gepa --rondas 3      # evoluciona
    uv run rag gepa --rondas 3 --forzar   # aunque la puerta esté cerrada
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from cerebro.config import cargar_env  # noqa: E402

cargar_env()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rondas", type=int, default=0)
    ap.add_argument("--forzar", action="store_true")
    a = ap.parse_args()

    from evals.gepa import MIN_ALPHA, MIN_PROBES, evolucionar, preparar

    adm = preparar()
    print(f"\n{'─' * 68}")
    print("  GEPA · puerta de admisión")
    print(f"\n  probes  {adm.n_probes} / {MIN_PROBES}")
    print(f"  α       {adm.alpha if adm.alpha is not None else 'sin medir'} / {MIN_ALPHA}")

    if adm.puede:
        print("\n  la puerta está ABIERTA\n")
    else:
        print("\n  la puerta está CERRADA:\n")
        for m in adm.motivos:
            print(f"    · {m}")
        print()

    if not a.rondas:
        print("  `--rondas N` lo corre. `--forzar` se salta la puerta, y entonces")
        print("  la propuesta queda marcada como corrida fuera de régimen.\n")
        return 0 if adm.puede else 1

    if not adm.puede and not a.forzar:
        print("  No se corre. Usa --forzar si sabes lo que estás haciendo.\n")
        return 1

    r = asyncio.run(evolucionar(rondas=a.rondas, forzar=a.forzar))
    if not r.get("corrio"):
        for m in r.get("motivos", []):
            print(f"    · {m}")
        return 1

    print(f"\n  {r['generaciones']} generación(es)")
    for h in r["historia"]:
        print(f"    ronda {h['ronda']}: {h['candidatos']} candidato(s) · "
              f"p={h['p_valores']} · umbral BH {h['umbral_bh']} · "
              f"{h['significativos']} significativo(s)")

    if r.get("propuesta"):
        print(f"\n  propuesta {r['propuesta']} encolada. NO se ha aplicado nada.")
        print("  `uv run rag propuestas` para verla y firmarla.")
        if r.get("forzado"):
            print("\n  Corrió fuera de régimen: la mejora que reporta puede ser ruido.")
    else:
        print("\n  ninguna variante mejoró de forma significativa. "
              "Es un resultado, no un fallo.")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
