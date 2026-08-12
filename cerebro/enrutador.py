"""
Fase 2 · enrutado: qué configuración usa cada consulta.

El estado del arte descarta el routing entre subsistemas heterogéneos, y con
razón: aquí hay un solo subsistema, y un clasificador aprendido necesitaría
meses de tráfico que un usuario con diez consultas a la semana no produce.

Esto es otra cosa, y conviene no confundirlas. No enruta **entre sistemas**:
ajusta **los pesos de los carriles dentro del único sistema** según la forma de
la pregunta. Y lo hace **por reglas escritas a mano sobre la consulta**, no con
un modelo, por tres motivos:

1. Cero latencia y cero coste. Un clasificador LLM añadiría una llamada a cada
   consulta para decidir una cosa que una expresión regular acierta.
2. Es **auditable**: la regla que disparó viaja en la traza, así que cuando el
   enrutado se equivoque se verá cuál fue y se podrá corregir esa.
3. Es **reversible sin reindexar**: es grada 2, y el bucle puede moverla.

Lo que NO hace: no cambia el corpus, no filtra por época, no toca el prompt.
Solo mueve los pesos de fusión y, si el carril de grafo está encendido, decide
si merece la pena pagarlo.

**Su fallo característico**, dicho por delante: una regla que dispara casi
siempre es equivalente a cambiar el valor por defecto, y una que no dispara
nunca es código muerto. Por eso `estadisticas()` cuenta los disparos sobre el
tráfico real, y el informe los enseña: una regla con cero disparos en cien
consultas se borra.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Any

from cerebro.config import PALANCAS, Palancas

#: Un símbolo: MayúsculaCamel, snake_case con guion bajo, versión, o CAPS.
_SIMBOLO = re.compile(
    r"\b(?:[a-z_]+_[a-z_]+|[A-Z][a-z]+[A-Z]\w*|v?\d+\.\d+(?:\.\d+)?|[A-Z]{3,})\b"
)
_COMPARA = re.compile(r"\b(?:o|frente a|vs\.?|en vez de|en lugar de|cuál de)\b", re.I)
_AGREGA = re.compile(
    r"\b(?:qué\s+\w+\s+he\b|todos?\b|cuáles\b|enumera|lista|resume|"
    r"qué he aprendido|en general)\b",
    re.I,
)
_TEMPORAL = re.compile(
    r"\b(?:sigue|vigente|todavía|aún|más reciente|obsolet\w+|superad\w+)\b", re.I
)
_MULTI = re.compile(
    r"\b(?:y\s+(?:qué|cómo|cuál)|relación entre|tienen en común|"
    r"cómo se relaciona|conecta)\b",
    re.I,
)


@dataclass(frozen=True)
class Ruta:
    """La decisión, con su motivo. El motivo va a la traza."""

    palancas: Palancas
    regla: str
    porque: str


def enrutar(consulta: str, p: Palancas = PALANCAS) -> Ruta:
    """Devuelve unas palancas ajustadas a la forma de la consulta.

    Las reglas se evalúan en orden y gana la primera. El orden no es arbitrario:
    va de la señal más específica a la más genérica, porque una consulta que
    pide agregación Y contiene un símbolo es antes una agregación —la respuesta
    está repartida— que una búsqueda exacta.
    """
    if p.enrutado == "none":
        return Ruta(p, "none", "el enrutado está apagado")

    carriles = list(p.carriles)
    pesos = list(p.peso_carril)

    def con_peso(**cambios: float) -> Palancas:
        nuevos = list(pesos)
        for nombre, w in cambios.items():
            if nombre in carriles:
                nuevos[carriles.index(nombre)] = w
        return replace(p, peso_carril=tuple(nuevos))

    if _AGREGA.search(consulta):
        # Agregación: la respuesta está repartida, hace falta cobertura ancha.
        # Si hay grafo, aquí es donde más aporta: trae los vecinos del tema.
        return Ruta(
            replace(con_peso(denso=1.2, lexico=0.8), top_k=min(p.top_k * 2, 24)),
            "agregacion",
            "pide barrer el corpus: se dobla top_k y manda el carril denso",
        )

    if _TEMPORAL.search(consulta):
        return Ruta(
            replace(con_peso(denso=1.0, lexico=1.0), solo_vigentes=False),
            "temporal",
            "pregunta por vigencia: hay que VER lo superado para poder nombrarlo",
        )

    if _MULTI.search(consulta):
        return Ruta(
            replace(con_peso(denso=1.3, lexico=0.7, grafo=1.5),
                    top_k=min(p.top_k + 4, 20)),
            "multi_hop",
            "pide cruzar dos cosas: pesa el grafo si está y amplía top_k",
        )

    n_simbolos = len(_SIMBOLO.findall(consulta))
    if n_simbolos >= 2 or (n_simbolos and _COMPARA.search(consulta)):
        # Símbolos exactos, y encima comparando dos: es exactamente lo que el
        # embedding aplasta y el carril léxico clava.
        return Ruta(
            replace(con_peso(denso=0.6, lexico=1.6), fts_modo="and"),
            "lexico_exacto",
            f"{n_simbolos} símbolo(s) literales: manda el léxico, y en modo AND",
        )

    return Ruta(p, "por_defecto", "ninguna regla dispara: la configuración base")


def estadisticas(*, limite: int = 500) -> dict[str, Any]:
    """Cuántas veces disparó cada regla sobre el tráfico real.

    Es la comprobación que impide que esta palanca se pudra. Una regla con cero
    disparos es código muerto; una que dispara en el 90 % de las consultas es un
    valor por defecto disfrazado de regla, y en los dos casos hay que tocarla.
    """
    from collections import Counter

    from cerebro.almacen import ESQUEMA, conexion

    with conexion() as con:
        filas = con.execute(
            f"select consulta from {ESQUEMA}.consulta order by ts desc limit %s",
            (limite,),
        ).fetchall()

    p = replace(PALANCAS, enrutado="reglas")
    cuenta = Counter(enrutar(f["consulta"], p).regla for f in filas)
    n = sum(cuenta.values())
    return {
        "n": n,
        "por_regla": dict(cuenta.most_common()),
        "muertas": [
            r for r in ("agregacion", "temporal", "multi_hop", "lexico_exacto")
            if cuenta.get(r, 0) == 0
        ],
        "dominantes": [r for r, c in cuenta.items() if n and c / n > 0.75],
    }
