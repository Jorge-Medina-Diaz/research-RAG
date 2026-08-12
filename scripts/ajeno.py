"""
Ingerir un corpus que NO escribiste tú.

    uv run rag ajeno --ver          # qué se ingeriría, sin tocar nada
    uv run rag ajeno --ingerir      # lo escribe en artefactos/entrada/

## El problema que resuelve, que es el más de fondo del repositorio

Hasta hoy el corpus eran quince artefactos sobre la construcción de este
repositorio, y las 41 probes salían de esos quince. La circularidad era total:
**el corpus documenta el código que el corpus mide.**

Tres consecuencias, y ninguna es teórica:

1. Toda distancia, todo umbral y toda calibración —el peso IDF del grafo, la
   ventana de analogías, el mínimo de modularidad— están ajustados a un corpus
   monotemático de un solo autor.
2. El golden set no tiene ninguna pregunta cuya respuesta el autor no sepa ya, y
   una pregunta cuya respuesta conoces no mide recuperación: mide tu memoria.
3. El estudio de sensibilidad dijo que el arnés no ve caerse un carril entero, y
   su diagnóstico fue «el conjunto es pequeño». Más probes sobre el mismo
   material monotemático no lo arreglan.

## Por qué los docstrings de Agno y no papers

Cuatro motivos, en orden de importancia:

- **No los escribiste tú**, que es el requisito entero.
- **No sabes lo que dicen.** Sesenta y dos módulos, y la mayoría son de
  subsistemas que este proyecto no usa: OAuth de MCP, la herramienta de Gmail,
  las hojas de cálculo, el middleware de ámbito de usuario. Se pueden escribir
  probes cuya respuesta hay que ir a buscar.
- **Variedad de dominio real.** El corpus propio es todo `evaluacion` y
  `recuperacion`. Esto trae `agentes`, `infraestructura`, `datos` y `producto`,
  que es lo que la minería de analogías cross-dominio necesita para poder
  siquiera formular su pregunta.
- **Está en disco.** Cero red, cero clave, y la versión está fijada por el
  `uv.lock`, así que el corpus es reproducible en cualquier clon.

## Y lo que este script es de verdad: una prueba del contrato

El contrato de ingesta se diseñó para artefactos escritos a mano por una
persona. Aquí llega material ajeno, sin frontmatter, sin `afirmaciones` y sin
`temas`. Que sobreviva —o que reviente, y dónde— es un resultado por sí mismo, y
la carpeta de rechazados es donde se lee.
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from cerebro.config import cargar_env  # noqa: E402

cargar_env()

AGNO = RAIZ / ".venv" / "Lib" / "site-packages" / "agno"
ENTRADA = RAIZ / "artefactos" / "entrada"

#: Mínimo de caracteres para que un docstring sea un artefacto. Por debajo es
#: una nota de una línea y no sostiene ninguna pregunta.
MINIMO = 400

#: Ruta del módulo → dominio del contrato. El vocabulario es CERRADO y esa es su
#: razón de ser: sin un eje cerrado, «contextos dispares» no es una consulta.
#: Este mapa es la única pieza que un humano tiene que revisar, y por eso es
#: pequeño y está a la vista.
DOMINIOS: tuple[tuple[str, str], ...] = (
    ("vectordb", "recuperacion"),
    ("knowledge", "recuperacion"),
    ("reranker", "recuperacion"),
    ("embedder", "recuperacion"),
    ("eval", "evaluacion"),
    ("scorer", "evaluacion"),
    ("environments", "evaluacion"),
    ("learn", "agentes"),
    ("memory", "agentes"),
    ("team", "agentes"),
    ("workflow", "agentes"),
    ("agent", "agentes"),
    ("models", "agentes"),
    ("db", "datos"),
    ("session", "datos"),
    ("os", "infraestructura"),
    ("middleware", "infraestructura"),
    ("mcp", "infraestructura"),
    ("tools", "producto"),
    ("integrations", "producto"),
    ("context", "agentes"),
    ("provider", "agentes"),
    ("guardrail", "producto"),
    ("media", "datos"),
    ("run", "agentes"),
    ("utils", "infraestructura"),
    ("api", "infraestructura"),
    ("cli", "infraestructura"),
)


def dominio_de(ruta: Path) -> str:
    partes = str(ruta).lower().replace("\\", "/")
    for clave, dom in DOMINIOS:
        if clave in partes:
            return dom
    return "otro"


def temas_de(ruta: Path, doc: str) -> list[str]:
    """Los temas salen de la ruta del módulo, no del texto.

    De la ruta y no de palabras clave extraídas del cuerpo: un extractor sobre
    el texto produciría términos plausibles y sin gobierno, y `temas` es lo que
    alimenta el peso IDF del grafo. Metadatos inventados producen aristas
    inventadas, y esas no se distinguen después de las buenas.
    """
    partes = [
        p for p in str(ruta.with_suffix("")).replace("\\", "/").split("/")
        if p not in ("__init__", "base") and len(p) > 2
    ]
    temas = ["agno", *partes[:4]]
    if "async" in doc.lower():
        temas.append("asincronia")
    return list(dict.fromkeys(t.lower().replace("_", "-") for t in temas))[:6]


def _titulo(ruta: Path, doc: str) -> str:
    """La primera frase del docstring, o el nombre del módulo."""
    # Fuera los subrayados de la primera línea: muchos docstrings usan
    # `Título\n=======`, y arrastrarlos deja títulos con veinte signos igual.
    lineas = [
        x for x in doc.strip().split("\n\n")[0].splitlines()
        if x.strip() and set(x.strip()) - set("=-~_*# ")
    ]
    primera = re.sub(r"\s+", " ", " ".join(lineas)).strip(" .")
    if 10 <= len(primera) <= 180:
        return primera
    nombre = str(ruta.with_suffix("")).replace("\\", " · ").replace("/", " · ")
    return f"Agno · {nombre}"


def recolectar() -> list[dict]:
    if not AGNO.exists():
        return []
    fuera: list[dict] = []
    for f in sorted(AGNO.rglob("*.py")):
        if "__pycache__" in str(f):
            continue
        rel = f.relative_to(AGNO)
        try:
            doc = ast.get_docstring(ast.parse(f.read_text(encoding="utf-8", errors="ignore")))
        except SyntaxError:
            continue
        if not doc or len(doc) < MINIMO:
            continue
        slug = "agno-" + re.sub(
            r"[^a-z0-9]+", "-", str(rel.with_suffix("")).lower().replace("\\", "-")
        ).strip("-")
        fuera.append({
            "id": slug[:80],
            "ruta": rel,
            "titulo": _titulo(rel, doc),
            "dominio": dominio_de(rel),
            "temas": temas_de(rel, doc),
            "cuerpo": doc.strip(),
        })
    return fuera


def escribir(arts: list[dict]) -> int:
    ENTRADA.mkdir(parents=True, exist_ok=True)
    for a in arts:
        # `confianza: alta` y `madurez: maduro` porque es documentación oficial
        # del paquete instalado, con su versión fijada en el lock. Y `estado:
        # reportado` en las afirmaciones, NUNCA `probado`: lo dicen sus autores,
        # no lo he comprobado yo. Esa distinción es la mitad del contrato.
        cuerpo = a["cuerpo"].replace("\r\n", "\n")
        frontmatter = "\n".join([
            "---",
            "tipo: lectura-paper",
            f"titulo: {_yaml(a['titulo'])}",
            "fecha: 2026-08-12",
            f"temas: [{', '.join(a['temas'])}]",
            f"dominio: {a['dominio']}",
            "madurez: maduro",
            "confianza: alta",
            "fuentes:",
            "  - tipo: repo",
            "    ref: agno-agi/agno",
            "    commit: v2.8.6",
            "    acceso: 2026-08-12",
            "---",
            "",
            f"> Corpus AJENO. Documentación del módulo `{a['ruta']}` de Agno 2.8.6,",
            "> tal cual la escribieron sus autores. No es una nota propia y no está",
            "> verificada: entra al corpus para que el golden set deje de preguntar",
            "> solo por material que ya conoces.",
            "",
            cuerpo,
            "",
        ])
        (ENTRADA / f"{a['id']}.md").write_text(frontmatter, encoding="utf-8")
    return len(arts)


def _yaml(s: str) -> str:
    """Un título con `:` rompe el YAML. Se entrecomilla si hace falta."""
    if any(c in s for c in ":#[]{}&*!|>%@`") or s.strip() != s:
        return '"' + s.replace('"', "'") + '"'
    return s


def _repartir(arts: list[dict], tope: int) -> list[dict]:
    """Reparte el cupo entre los subárboles de primer nivel, en ronda.

    La variedad de dominio es el punto entero de este corpus, y ordenar
    alfabéticamente la destruye: los cuarenta primeros salían todos de la misma
    carpeta.
    """
    from collections import defaultdict
    from itertools import zip_longest

    por_raiz: dict[str, list[dict]] = defaultdict(list)
    for a in arts:
        por_raiz[str(a["ruta"]).replace("\\", "/").split("/")[0]].append(a)

    rondas = zip_longest(*(v for _, v in sorted(por_raiz.items())))
    fuera: list[dict] = []
    for ronda in rondas:
        for x in ronda:
            if x is not None and len(fuera) < tope:
                fuera.append(x)
    return fuera


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ver", action="store_true")
    ap.add_argument("--ingerir", action="store_true")
    ap.add_argument("--tope", type=int, default=40)
    a = ap.parse_args()

    # Repartido por subárbol, no los primeros por orden alfabético. Coger los
    # 40 primeros daba cuarenta módulos de `context/providers/` — el corpus
    # ajeno habría sido tan monotemático como el propio, que es justo lo que se
    # quería evitar.
    arts = _repartir(recolectar(), a.tope)
    if not arts:
        print(f"\n  no encuentro Agno en {AGNO}\n")
        return 1

    from collections import Counter

    print(f"\n{'─' * 70}")
    print(f"  {len(arts)} artefactos AJENOS de Agno 2.8.6\n")
    for dom, n in sorted(Counter(x["dominio"] for x in arts).items()):
        print(f"    {n:3}  {dom}")
    print("\n  El corpus propio es monotemático: `evaluacion` y `recuperacion`.")
    print("  Esto trae dominios que no toca, y esa variedad es lo que la minería")
    print("  de analogías cross-dominio necesita para poder formular su pregunta.\n")

    if a.ver:
        for x in arts[:10]:
            print(f"    [{x['dominio']:<16}] {x['titulo'][:62]}")
        print("\n  `--ingerir` los escribe en artefactos/entrada/ y después:")
        print("    uv run rag ingerir\n")
        return 0

    if a.ingerir:
        n = escribir(arts)
        print(f"  {n} ficheros escritos en artefactos/entrada/\n")
        print("  Ahora `uv run rag ingerir`. Entrarán en la ÉPOCA ABIERTA, así que")
        print("  la medición no se moverá hasta que la cierres: es exactamente el")
        print("  caso para el que existen las épocas, y la primera vez que el")
        print("  corpus dobla de tamaño de golpe.\n")
        return 0

    print("  `--ver` para inspeccionar · `--ingerir` para escribirlos\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
