"""
Las reglas que comprueba CÓDIGO, no el juez.

Cinco de las ocho de `spec.md`: R1, R2, R4, R7, R8. Y no es una optimización de
coste, aunque también lo sea. Es que **una regla que un `re.findall` puede
decidir no debería depender de un modelo**: el juez introduce sesgo, varianza y
una llamada, y a cambio no aporta nada que un patrón no vea.

Consecuencia práctica: este módulo corre offline, sin claves y en milisegundos.
Es el nivel 0 de la pila de métricas y es lo que hace posible que la señal
determinista entre en CI.

Todas las funciones devuelven `(cumple, motivo)`. El motivo es una frase y dice
qué falta exactamente — no «R4 incumplida» sino «cita 2.8.5 y en los fragmentos
pone 2.8.6».
"""

from __future__ import annotations

import re
import unicodedata

#: La frase exacta de R2. Cualquier añadido incumple.
ABSTENCION = "No lo tengo en la memoria."

CITA = re.compile(r"\[\[art:([a-z0-9\-]+)\]\]")

#: Literales que R4 obliga a reproducir tal cual. El orden importa: las
#: alternativas más específicas van primero para que no las coma una más laxa.
LITERAL = re.compile(
    r"arXiv:\d{4}\.\d{4,5}"          # ids de arXiv
    r"|v?\d+\.\d+(?:\.\d+)*"         # versiones semánticas
    r"|[a-z_]+\.[a-z_]+"             # nombres de símbolo: hnsw.ef_search
    r"|\d[\d.,]*"                    # cifras
)

MARCADORES_EPISTEMICOS = (
    "extrapolación", "extrapolacion", "conjetura", "auto-reportado",
    "autorreportado", "sin verificar", "no verificado",
    "sin réplica independiente", "sin replica independiente", "reportado",
)

#: Fórmulas de cortesía. Lista cerrada a propósito: una lista abierta la decide
#: un modelo, y entonces R8 deja de ser comprobable por código.
RELLENO = (
    "espero que", "aquí tienes", "aqui tienes", "claro,", "por supuesto",
    "en resumen", "en conclusión", "en conclusion", "déjame", "dejame",
    "es importante destacar", "cabe señalar", "cabe senalar",
    "buena pregunta", "excelente pregunta",
)


def _normalizar(t: str) -> str:
    return " ".join(t.split()).strip()


def _sin_tildes(t: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", t.lower()) if unicodedata.category(c) != "Mn"
    )


def _texto_fragmentos(fragmentos: list[dict]) -> str:
    return "\n".join(str(f.get("content", "")) for f in fragmentos)


def _ids_fragmentos(fragmentos: list[dict]) -> set[str]:
    ids = set()
    for f in fragmentos:
        meta = f.get("meta_data") or {}
        if a := meta.get("artefacto_id"):
            ids.add(str(a))
    return ids


def r1_cita(respuesta: str, fragmentos: list[dict]) -> tuple[bool, str]:
    if abstiene(respuesta):
        return True, ""  # una abstención no tiene nada que citar
    citas = set(CITA.findall(respuesta))
    if not citas:
        return False, "no cita ningún artefacto"
    if fantasmas := citas - _ids_fragmentos(fragmentos):
        return False, f"cita artefactos que no se recuperaron: {sorted(fantasmas)}"
    return True, ""


def abstiene(respuesta: str) -> bool:
    return _normalizar(respuesta) == ABSTENCION


def r2_abstencion(respuesta: str, debe_abstenerse: bool) -> tuple[bool, str]:
    """Solo aplica a las probes que declaran que la respuesta no está."""
    if not debe_abstenerse:
        return True, ""
    n = _normalizar(respuesta)
    if n == ABSTENCION:
        return True, ""
    if ABSTENCION in n:
        return False, f"se abstiene pero añade texto: {n[:120]!r}"
    return False, f"debía abstenerse y respondió: {n[:120]!r}"


def r4_literales(respuesta: str, fragmentos: list[dict]) -> tuple[bool, str]:
    if abstiene(respuesta):
        return True, ""
    contexto = _texto_fragmentos(fragmentos)
    inventados = [
        t for t in {m.group(0) for m in LITERAL.finditer(respuesta)} if t not in contexto
    ]
    if inventados:
        return False, f"literales que no están en los fragmentos: {sorted(inventados)[:6]}"
    return True, ""


def r7_estatus(respuesta: str, fragmentos: list[dict]) -> tuple[bool, str]:
    """Si lo que sostiene la respuesta viene marcado como no probado, la
    respuesta tiene que decirlo. Es la nota de honestidad intelectual convertida
    en regla."""
    if abstiene(respuesta):
        return True, ""
    contexto = _texto_fragmentos(fragmentos).lower()
    marcado = any(m in contexto for m in ("[extrapolacion]", "[conjetura]", "[reportado]"))
    if not marcado:
        return True, ""
    r = _sin_tildes(respuesta)
    if any(_sin_tildes(m) in r for m in MARCADORES_EPISTEMICOS):
        return True, ""
    return False, (
        "los fragmentos marcan la afirmación como no probada y la respuesta la "
        "presenta sin matizar"
    )


def r8_sin_relleno(respuesta: str, *, max_frases: int = 8) -> tuple[bool, str]:
    if abstiene(respuesta):
        return True, ""
    r = _sin_tildes(respuesta)
    if encontradas := [f for f in RELLENO if _sin_tildes(f) in r]:
        return False, f"fórmulas de relleno: {encontradas[:3]}"
    # Las líneas de una enumeración no cuentan como frases: R8 permite enumerar.
    cuerpo = "\n".join(
        ln for ln in respuesta.splitlines() if not ln.lstrip().startswith(("-", "*", "|"))
    )
    frases = [s for s in re.split(r"[.!?]+(?:\s|$)", cuerpo) if s.strip()]
    if len(frases) > max_frases:
        return False, f"{len(frases)} frases, el máximo es {max_frases}"
    return True, ""


#: id de regla -> (función, qué argumentos necesita)
DETERMINISTAS = ("R1", "R2", "R4", "R7", "R8")
DEL_JUEZ = ("R3", "R5", "R6")


def comprobar_deterministas(
    respuesta: str, fragmentos: list[dict], *, reglas: list[str], debe_abstenerse: bool
) -> dict[str, tuple[bool, str]]:
    """Comprueba las reglas de código que apliquen a esta probe."""
    todas = {
        "R1": lambda: r1_cita(respuesta, fragmentos),
        "R2": lambda: r2_abstencion(respuesta, debe_abstenerse),
        "R4": lambda: r4_literales(respuesta, fragmentos),
        "R7": lambda: r7_estatus(respuesta, fragmentos),
        "R8": lambda: r8_sin_relleno(respuesta),
    }
    return {r: todas[r]() for r in reglas if r in todas}
