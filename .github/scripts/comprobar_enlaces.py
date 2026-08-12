"""
Comprueba que ningún enlace interno de la documentación esté roto.

    uv run python .github/scripts/comprobar_enlaces.py

Existe porque un repositorio cuyo entregable son los documentos se pudre por
los enlaces antes que por el código, y un enlace roto no lanza ninguna
excepción: se descubre cuando alguien de fuera lo pincha.

Reimplementa el algoritmo de slug de GitHub, que tiene un detalle que engaña:
**no colapsa los espacios**. Un título como `## 3 · Las cuatro decisiones`
pierde el `·` y deja dos espacios seguidos, así que su ancla lleva dos guiones
—`#3--las-cuatro-decisiones`— y no uno. Una primera versión de este script
colapsaba, y reportó cinco anclas rotas que no lo estaban: un detector que
dispara de más también está apagado, porque a la tercera falsa alarma se
ignora.
"""

from __future__ import annotations

import pathlib
import re

RAIZ = pathlib.Path(__file__).resolve().parent.parent.parent


def slug(titulo: str) -> str:
    t = re.sub(r"`|\*\*|\*|_", "", titulo).strip().lower()
    t = re.sub(r"[^\w\s-]", "", t, flags=re.UNICODE)
    return t.replace(" ", "-")


def main() -> int:
    ficheros = [RAIZ / "README.md", RAIZ / "CLAUDE.md", *sorted((RAIZ / "docs").glob("*.md"))]
    ficheros = [f for f in ficheros if f.exists()]

    anclas = {
        f.name: {
            slug(m.group(1))
            for m in re.finditer(r"^#{1,6}\s+(.*)$", f.read_text(encoding="utf-8"), re.M)
        }
        for f in ficheros
    }

    malos: list[str] = []
    total = 0
    for f in ficheros:
        for m in re.finditer(r"\[([^\]]*)\]\(([^)]+)\)", f.read_text(encoding="utf-8")):
            dest = m.group(2)
            if dest.startswith(("http", "mailto", "#!")):
                continue
            total += 1
            ruta, _, anc = dest.partition("#")
            obj = (f.parent / ruta).resolve() if ruta else f
            if ruta and not obj.exists():
                malos.append(f"{f.name}: no existe el fichero  ->  {ruta}")
                continue
            if anc and obj.name in anclas and anc not in anclas[obj.name]:
                malos.append(f"{f.name}: ancla inexistente     ->  {dest}")

    for x in malos:
        print(f"  ROTO  {x}")
    print(f"\n  {total - len(malos)}/{total} enlaces internos correctos")
    return 1 if malos else 0


if __name__ == "__main__":
    raise SystemExit(main())
