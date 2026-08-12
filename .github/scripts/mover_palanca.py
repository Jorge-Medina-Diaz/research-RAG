"""Mueve una palanca entera de `cerebro/config.py` a un valor DISTINTO del actual.

Existe porque la comprobación de CI «el diff se niega cuando se mueven dos
palancas» tenía los valores escritos a mano (`top_k: int = 20`), y la ronda 1
del bucle dejó `top_k` justamente en 20. El `sed` dejó de cambiar nada, el arnés
dijo con razón «misma configuración: esto mide RUIDO», y la comprobación falló.

Falló, que es mejor que pasar en falso. Pero falló por haberse quedado vieja, no
por el defecto que vigila — y una prueba que envejece al ritmo al que el bucle
mueve palancas acabará mintiendo en la dirección contraria el día que el valor
nuevo coincida con el que ella escribe.

Leer el valor y sumarle uno hace que el no-op sea imposible por construcción.
"""

from __future__ import annotations

import pathlib
import re
import sys

CONFIG = pathlib.Path(__file__).resolve().parents[2] / "cerebro" / "config.py"


def main() -> int:
    if len(sys.argv) != 2:
        print("uso: mover_palanca.py <nombre_de_palanca>", file=sys.stderr)
        return 2
    palanca = sys.argv[1]
    src = CONFIG.read_text(encoding="utf-8")
    patron = re.compile(rf"^(    {re.escape(palanca)}: int = )(\d+)", re.M)
    m = patron.search(src)
    if not m:
        print(f"no encontré una palanca entera llamada {palanca!r} en {CONFIG}",
              file=sys.stderr)
        return 1
    antes = int(m.group(2))
    despues = antes + 1
    CONFIG.write_text(patron.sub(rf"\g<1>{despues}", src, count=1), encoding="utf-8")
    print(f"  {palanca}: {antes} → {despues}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
