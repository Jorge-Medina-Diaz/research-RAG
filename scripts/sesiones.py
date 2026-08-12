"""
Vuelca el tráfico real: de aquí salen las probes que valen.

    uv run rag sesiones
    uv run rag sesiones --n 100 --json runs/candidatos.json

El golden set inicial lo escribe una persona mirando el corpus, y por eso
pregunta lo que el corpus responde bien. Las consultas reales no: traen las
formulaciones raras, las abreviaturas de la casa y las cosas que sencillamente
no están.

Cuatro señales, todas baratas y todas deterministas:

  voto -1        lo marcaste tú. La señal más fuerte que existe con un usuario.
  abstuvo        o no estaba —y es una probe de `fuera_de_alcance`— o sí estaba
                 y no llegó, que es el fallo de recuperación más valioso.
  cero hits      cobertura, sin ambigüedad.
  reformulación  dos consultas parecidas en menos de tres minutos. Con un solo
                 usuario es insatisfacción, y cuesta un self-join.

Lo que sale de aquí son CANDIDATOS. Convertir uno en probe exige decidir qué
artefacto debía llegar, y esa etiqueta la pones tú: es justo lo que no se puede
automatizar sin contaminar la medida.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from cerebro.almacen import ESQUEMA, conexion, migrar  # noqa: E402

SQL = f"""
with c as (
  select id, ts, consulta, n_devueltos, abstuvo, voto,
         lag(consulta) over (order by ts) as anterior,
         ts - lag(ts) over (order by ts) as desde_la_anterior
  from {ESQUEMA}.consulta
  where es_probe = false
  order by ts desc
  limit %s
)
select *,
  (desde_la_anterior < interval '3 minutes' and anterior is not null) as reformulacion
from c order by ts desc
"""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n", type=int, default=50)
    ap.add_argument("--json", default="")
    args = ap.parse_args()

    migrar()
    with conexion() as con:
        filas = [dict(f) for f in con.execute(SQL, (args.n,)).fetchall()]

    if not filas:
        print(
            "\n  No hay tráfico todavía. Usa el cerebro (`uv run rag serve`) y vuelve.\n"
            "  Hasta entonces el golden set es 100 % sintético, y eso limita el bucle\n"
            "  a palancas de recuperación: las de generación las firmas tú.\n"
        )
        return 0

    def marca(f: dict) -> str:
        if f["voto"] == -1:
            return "VOTO-"
        if f["abstuvo"]:
            return "ABSTUVO"
        if f["n_devueltos"] == 0:
            return "CERO"
        if f["reformulacion"]:
            return "REFORM"
        return "      "

    candidatos = [f for f in filas if marca(f).strip()]
    print(f"\n  {len(filas)} consulta(s) · {len(candidatos)} candidata(s)\n")
    for f in filas:
        print(f"  {marca(f):<8} #{f['id']:<5} {f['consulta'][:66]}")

    print(
        "\n  Para convertir una en probe hay que decidir qué artefacto debía llegar.\n"
        "  Eso no lo automatiza el bucle: es la etiqueta, y es la medida.\n"
    )

    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(
            json.dumps(candidatos, ensure_ascii=False, indent=1, default=str),
            encoding="utf-8",
        )
        print(f"  volcado a {args.json}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
