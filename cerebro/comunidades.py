"""
Comunidades sobre el grafo de artefactos, y sus resúmenes.

    uv run rag comunidades              # detecta y describe
    uv run rag comunidades --resumir    # + un resumen por comunidad (gasta LLM)

Para qué sirve una comunidad. Para las preguntas de tipo `aggregation`, que son
las que ningún carril de recuperación contesta bien: *«¿qué he aprendido sobre
medir con pocas muestras?»* no tiene un fragmento que la responda, tiene doce.
Recuperar los doce y pegarlos al prompt gasta contexto y devuelve una lista;
recuperar **el resumen de la comunidad** devuelve una respuesta.

Es la idea central de GraphRAG, y aquí llega con dos diferencias. Una: se
construye sobre un grafo de artefactos, no de entidades extraídas, así que no
cuesta una llamada de LLM por documento para poblarlo. Dos: es una **costura**
con disparador escrito —`aggregation` por debajo de 0,60— y viene apagada.

**Propagación de etiquetas, no Leiden.** Leiden es mejor y necesita `igraph` +
`leidenalg`, dos dependencias binarias para particionar trescientos nodos. La
propagación de etiquetas es determinista si se fija el orden, converge en menos
de veinte pasadas a esta escala, y su defecto conocido —particiones inestables
en grafos poco densos— aquí se detecta solo: la modularidad se reporta siempre,
y por debajo de 0,30 el informe dice que la partición no significa nada en vez
de dibujar comunidades bonitas sobre ruido.
"""

from __future__ import annotations

import json
from collections import defaultdict
from typing import Any

from cerebro.almacen import ESQUEMA, conexion, epoca_abierta
from cerebro.config import PALANCAS, Palancas
from cerebro.grafo import Grafo, cargar, modularidad

#: Por debajo de esto la partición no dice nada y el informe lo dice.
MODULARIDAD_MINIMA = 0.30

#: Una comunidad de un solo artefacto no es una comunidad.
TAMANO_MINIMO = 2


def propagar_etiquetas(g: Grafo, *, pasadas: int = 20) -> dict[str, int]:
    """Detección de comunidades por propagación de etiquetas.

    Cada nodo adopta la etiqueta más pesada de sus vecinos; se repite hasta que
    nadie cambia. **El orden de recorrido está fijado alfabéticamente y los
    empates se rompen por la etiqueta menor**, que es lo que hace el resultado
    reproducible — la versión aleatoria del algoritmo da particiones distintas
    en cada ejecución, y una comunidad que cambia entre dos corridas idénticas
    no se puede usar para medir nada.
    """
    if not g.vecinos:
        return {}

    ndir: dict[str, dict[str, float]] = defaultdict(dict)
    for o, vs in g.vecinos.items():
        ndir.setdefault(o, {})
        for d, w in vs.items():
            ndir[o][d] = ndir[o].get(d, 0.0) + w
            ndir.setdefault(d, {})
            ndir[d][o] = ndir[d].get(o, 0.0) + w

    orden = sorted(ndir)
    etiqueta = {n: i for i, n in enumerate(orden)}

    for _ in range(pasadas):
        cambios = 0
        for n in orden:
            if not ndir[n]:
                continue
            acumulado: dict[int, float] = defaultdict(float)
            for v, w in ndir[n].items():
                acumulado[etiqueta[v]] += w
            # max por (peso, -etiqueta): el peso manda, y el empate lo rompe la
            # etiqueta más baja. Determinista.
            mejor = max(acumulado.items(), key=lambda kv: (kv[1], -kv[0]))[0]
            if mejor != etiqueta[n]:
                etiqueta[n] = mejor
                cambios += 1
        if not cambios:
            break

    # Renumerar de forma estable: la comunidad 0 es la mayor, y dentro del
    # mismo tamaño manda el id alfabéticamente menor. Sin esto los números
    # bailarían entre corridas aunque la partición fuera idéntica.
    grupos: dict[int, list[str]] = defaultdict(list)
    for n, e in etiqueta.items():
        grupos[e].append(n)
    ordenadas = sorted(grupos.values(), key=lambda m: (-len(m), sorted(m)[0]))
    return {n: i for i, miembros in enumerate(ordenadas) for n in sorted(miembros)}


def detectar(*, epoca: int | None = None) -> dict[str, Any]:
    """Detecta, mide y persiste. Devuelve el informe."""
    ep = epoca if epoca is not None else epoca_abierta()
    g = cargar(epoca=ep)
    part = propagar_etiquetas(g)
    q = modularidad(g, part) if part else 0.0

    grupos: dict[int, list[str]] = defaultdict(list)
    for n, c in part.items():
        grupos[c].append(n)
    utiles = {c: sorted(m) for c, m in grupos.items() if len(m) >= TAMANO_MINIMO}

    with conexion() as con:
        con.execute(f"delete from {ESQUEMA}.comunidad where epoca = %s", (ep,))
        for c, miembros in utiles.items():
            con.execute(
                f"""insert into {ESQUEMA}.comunidad
                      (id, epoca, miembros, etiqueta, cohesion)
                    values (%s,%s,%s,%s,%s)""",
                (c, ep, miembros, _etiqueta_por_temas(con, miembros),
                 _cohesion(g, miembros)),
            )
        con.commit()

    return {
        "epoca": ep,
        "modularidad": q,
        "significativa": q >= MODULARIDAD_MINIMA,
        "n_comunidades": len(utiles),
        "sueltos": sum(1 for m in grupos.values() if len(m) < TAMANO_MINIMO),
        "comunidades": utiles,
    }


def _cohesion(g: Grafo, miembros: list[str]) -> float:
    """Fracción del peso de los miembros que se queda dentro de la comunidad.

    Es la cifra que distingue una comunidad de verdad de un grupo que el
    algoritmo tuvo que colocar en algún sitio. Cerca de 1, el grupo casi no
    habla con fuera; cerca de 0, está ahí por descarte.
    """
    dentro = set(miembros)
    interno = externo = 0.0
    for n in miembros:
        for v, w in g.vecinos.get(n, {}).items():
            if v in dentro:
                interno += w
            else:
                externo += w
    total = interno + externo
    return interno / total if total else 0.0


def _etiqueta_por_temas(con, miembros: list[str]) -> str:
    """Nombra la comunidad con los temas que más comparte. Sin LLM.

    Deliberadamente barato: una etiqueta legible por dos euros de llamadas es
    peor que una etiqueta legible gratis. El resumen —eso sí necesita un
    modelo— es un paso aparte y opcional.
    """
    filas = con.execute(
        f"""select temas from {ESQUEMA}.artefacto
            where id = any(%s) and valido_hasta is null""",
        (miembros,),
    ).fetchall()
    cuenta: dict[str, int] = defaultdict(int)
    for f in filas:
        for t in f["temas"] or []:
            cuenta[t] += 1
    top = sorted(cuenta.items(), key=lambda kv: (-kv[1], kv[0]))[:3]
    # Solo los temas que comparte al menos la mitad: los demás describen a un
    # miembro, no al grupo.
    umbral = max(2, len(miembros) // 2)
    elegidos = [t for t, n in top if n >= umbral] or [t for t, _ in top[:2]]
    return " · ".join(elegidos) if elegidos else "sin tema común"


async def resumir(*, epoca: int | None = None, p: Palancas = PALANCAS) -> int:
    """Un resumen por comunidad, con LLM. Devuelve cuántos escribió.

    Cuesta una llamada por comunidad, no por documento — que es la diferencia de
    coste entre esto y GraphRAG, y la razón de que sea asumible en un proyecto
    personal. Con una docena de comunidades son doce llamadas al mes.
    """
    from cerebro.agente import SISTEMA, construir_modelo

    ep = epoca if epoca is not None else epoca_abierta()
    # SISTEMA, no `p`. Ver el mismo arreglo en `analogias.minar`.
    modelo = construir_modelo(SISTEMA)
    if modelo is None:
        return 0

    from agno.agent import Agent

    redactor = Agent(
        model=modelo,
        instructions=[
            "Resume en 3-5 frases QUÉ TIENEN EN COMÚN estos artefactos.",
            "No enumeres los artefactos: di la idea que comparten.",
            "Si no comparten ninguna idea, dilo exactamente así: "
            "'No comparten una idea: los agrupa la topología, no el contenido.'",
            "No inventes nada que no esté en los títulos y afirmaciones dados.",
        ],
        markdown=False,
    )

    escritos = 0
    with conexion() as con:
        comus = con.execute(
            f"select id, miembros from {ESQUEMA}.comunidad where epoca = %s order by id",
            (ep,),
        ).fetchall()
        for c in comus:
            arts = con.execute(
                f"""select titulo, frontmatter from {ESQUEMA}.artefacto
                    where id = any(%s) and valido_hasta is null""",
                (c["miembros"],),
            ).fetchall()
            material = "\n\n".join(
                f"## {a['titulo']}\n"
                + "\n".join(
                    f"- {x.get('texto', '')}"
                    for x in (a["frontmatter"] or {}).get("afirmaciones", [])[:4]
                )
                for a in arts
            )
            res = await redactor.arun(material)
            con.execute(
                f"update {ESQUEMA}.comunidad set resumen = %s where id = %s and epoca = %s",
                ((res.content or "").strip(), c["id"], ep),
            )
            escritos += 1
        con.commit()
    return escritos


def resumenes_vigentes(*, epoca: int | None = None) -> list[dict[str, Any]]:
    """Los resúmenes, para que el recuperador los pueda servir en `aggregation`."""
    ep = epoca if epoca is not None else epoca_abierta()
    with conexion() as con:
        return [
            dict(f)
            for f in con.execute(
                f"""select id, etiqueta, resumen, miembros, cohesion
                    from {ESQUEMA}.comunidad
                    where epoca = %s and resumen is not null
                    order by cardinality(miembros) desc""",
                (ep,),
            ).fetchall()
        ]


def json_seguro(x: Any) -> str:
    return json.dumps(x, ensure_ascii=False, default=str)
