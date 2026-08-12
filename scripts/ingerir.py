"""
Ingiere `artefactos/entrada/*.md`.

    uv run rag ingerir
    uv run rag ingerir --no-mover      # deja los ficheros en la bandeja
    uv run rag ingerir --recrear       # borra el índice y reindexa el corpus entero

`--recrear` es lo que hay que correr tras tocar una palanca de grada 3. No lo
hace solo: reindexar cuesta dinero y una reindexación disparada por accidente en
mitad de una ronda deja el archivo con dos configuraciones mezcladas.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from cerebro.almacen import (  # noqa: E402
    epoca_abierta,
    epoca_medicion,
    migrar,
    sha_corpus,
    vaciar_indice,
)
from cerebro.config import PALANCAS, tabla_fragmentos  # noqa: E402
from ingesta.pipeline import BANDEJA, CORPUS, ingerir_bandeja  # noqa: E402


def _reponer_corpus_en_bandeja() -> int:
    """Para reindexar hace falta volver a pasar el corpus por el pipeline."""
    n = 0
    for f in sorted(CORPUS.rglob("*.md")):
        shutil.copy(f, BANDEJA / f.name)
        n += 1
    return n


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--no-mover", action="store_true", help="no mover los ficheros")
    ap.add_argument("--recrear", action="store_true",
                    help="reindexa el corpus entero (obligatorio tras una palanca de grada 3)")
    args = ap.parse_args()

    migrar()
    BANDEJA.mkdir(parents=True, exist_ok=True)

    if args.recrear:
        print(f"→ borrando el índice {tabla_fragmentos()}")
        vaciar_indice()
        n = _reponer_corpus_en_bandeja()
        print(f"→ {n} artefacto(s) del corpus vuelven a la bandeja")

    resultados = ingerir_bandeja(mover=not args.no_mover)

    if not resultados:
        print("\n  bandeja vacía. Suelta artefactos en artefactos/entrada/ y repite.\n")
        return 0

    print()
    for r in resultados:
        marca = "RECHAZA" if r.estado == "rechazado" else f"{r.estado:12}"
        extra = f"  {r.motivo}" if r.motivo else f"  {r.fragmentos} fragmento(s)"
        print(f"  {marca}  {r.ruta.name:<44}{extra}")

    sha, n = sha_corpus()
    print(
        f"\n  corpus {n} artefacto(s) · sha {sha}"
        f"\n  época abierta {epoca_abierta()} · época de medición {epoca_medicion()}"
        f"\n  índice {tabla_fragmentos(PALANCAS)}\n"
    )
    return 1 if any(r.estado == "rechazado" for r in resultados) else 0


if __name__ == "__main__":
    raise SystemExit(main())
