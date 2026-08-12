"""
Las épocas: el mecanismo que hace medible un corpus que crece.

    uv run rag epoca            # estado
    uv run rag epoca avanzar    # cierra la abierta, abre la siguiente

El problema que resuelve: `sha_corpus()` cambia cada vez que añades un artefacto,
así que `comparable_con()` devolvería `(False, ['el corpus cambió'])` siempre y
ninguna comparación sería legal jamás. Un detector que dispara siempre está
apagado.

La salida no es relajar el detector: es congelar la VISTA, no el corpus.

  · Servir no filtra. El cerebro ve todo el corpus siempre. Es el producto.
  · Medir filtra a la última época CERRADA. La medición es estacionaria
    mientras el sistema está vivo.
  · Avanzar la época es un acto deliberado y fechado.

**Avanzar la época está en la lista de nunca-automatizado**: mueve la línea base
de todas las mediciones futuras. Cuando avanzas, lo correcto es correr la
configuración incumbente SIN TOCAR contra la época vieja y la nueva: esa única
corrida extra aísla el efecto del corpus con la configuración fija, y su
resultado es la nueva línea base. Es CUPED en su versión barata — no hace falta
el álgebra de la covariable, hace falta re-correr al incumbente.
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from cerebro.almacen import (  # noqa: E402
    ESQUEMA,
    avanzar_epoca,
    conexion,
    epoca_abierta,
    epoca_medicion,
    migrar,
    sha_corpus,
)


def estado() -> int:
    with conexion() as con:
        filas = con.execute(
            f"select e.numero, e.abierta_en, e.cerrada_en, e.corpus_sha, e.n_artefactos, "
            f"  (select count(*) from {ESQUEMA}.artefacto a "
            f"   where a.epoca = e.numero and a.valido_hasta is null) as vivos "
            f"from {ESQUEMA}.epoca e order by e.numero"
        ).fetchall()

    sha, n = sha_corpus()
    print(f"\n  corpus ahora: {n} artefacto(s) vigentes · sha {sha}")
    print(f"  época abierta: {epoca_abierta()}   ·   época de medición: {epoca_medicion()}\n")
    print(f"  {'época':>6}  {'estado':<9} {'artefactos':>10}  {'sha':<14} abierta")
    for f in filas:
        est = "abierta" if f["cerrada_en"] is None else "cerrada"
        sha_e = f["corpus_sha"] or "—"
        print(
            f"  {f['numero']:>6}  {est:<9} {f['vivos']:>10}  {sha_e:<14} "
            f"{f['abierta_en']:%Y-%m-%d %H:%M}"
        )
    print()
    if epoca_abierta() == epoca_medicion():
        print(
            "  Aún no has cerrado ninguna época, así que se mide contra la abierta y\n"
            "  cada artefacto que ingieras mueve la línea base. Cierra una en cuanto\n"
            "  tengas el golden set etiquetado: `uv run rag epoca avanzar`.\n"
        )
    return 0


def avanzar() -> int:
    cerrada, nueva = avanzar_epoca()
    sha, n = sha_corpus()
    print(
        f"\n  época {cerrada} CERRADA · {n} artefacto(s) · sha {sha}"
        f"\n  época {nueva} abierta: lo que ingieras a partir de ahora no entra en la medición."
        f"\n"
        f"\n  Antes de aceptar ningún cambio de configuración, corre la incumbente SIN"
        f"\n  TOCAR contra las dos épocas:"
        f"\n"
        f"\n      uv run rag eval --epoca {epoca_previa(cerrada)}"
        f"\n      uv run rag eval --epoca {cerrada}"
        f"\n"
        f"\n  La diferencia entre las dos es el efecto del CORPUS con la configuración"
        f"\n  fija. Sin ese número, el siguiente delta que midas mezcla las dos cosas.\n"
    )
    return 0


def epoca_previa(n: int) -> int:
    return max(0, n - 1)


def main() -> int:
    migrar()
    if len(sys.argv) > 1 and sys.argv[1] == "avanzar":
        return avanzar()
    return estado()


if __name__ == "__main__":
    raise SystemExit(main())
