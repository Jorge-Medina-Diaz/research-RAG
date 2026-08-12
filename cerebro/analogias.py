"""
Analogías entre dominios distintos: la costura del requisito titular.

    uv run rag analogias --minar        # propone (gasta LLM)
    uv run rag analogias                # lista lo pendiente
    uv run rag analogias --aceptar 7    # firma una
    uv run rag analogias --rechazar 7 --motivo "es la misma idea, no una analogía"

El requisito original de este proyecto decía «capturar sutilezas y relacionar
contextos dispares, autodescubrir conexiones y relaciones no aparentes». Esto es
esa pieza, y llega la última por un motivo que conviene decir por delante:
**proponer analogías es fácil y evaluarlas es muy difícil.**

El único juez posible eres tú, una por una. Un sistema que propone conexiones sin
criterio de admisión produce una lista que crece más rápido de lo que la revisas,
y eso es la definición de ruido. Así que aquí hay tres filtros antes de que algo
llegue a tus ojos, y los tres son baratos:

1. **Cross-dominio obligatorio.** `dominio` es un vocabulario CERRADO justo para
   esto: sin un eje cerrado, «contextos dispares» no es una consulta, es una
   intuición. Dos artefactos del mismo dominio que se parecen no son una
   analogía, son un duplicado.
2. **Ni muy cerca ni muy lejos.** Muy cerca es el mismo tema con otras palabras;
   muy lejos es ruido de embedding. La ventana es una palanca.
3. **Sin arista previa.** Si ya están conectados en el grafo, la relación no es
   «no aparente»: está escrita.

Lo que sobrevive va a un LLM que tiene que **nombrar la abstracción compartida**,
no decir si se parecen. Es la diferencia que hace la tarea evaluable: «los dos
hablan de fallos» no vale; «los dos son un parámetro que se lee como vivo y no
lo está» sí, porque es comprobable contra los dos artefactos.

**Nada entra al corpus sin firma.** Las aceptadas se escriben como aristas de
tipo `analogia` y como una nota en la cola; el corpus solo lo escribes tú.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from cerebro.almacen import ESQUEMA, conexion, epoca_abierta
from cerebro.config import PALANCAS, Palancas


@dataclass(frozen=True)
class Candidata:
    a: str
    b: str
    dominio_a: str
    dominio_b: str
    distancia: float
    titulo_a: str
    titulo_b: str


def _centroides(con, epoca: int, p: Palancas) -> dict[str, tuple[list[float], dict]]:
    """Un vector por artefacto: la media de sus fragmentos, normalizada.

    Comparar artefactos y no fragmentos es deliberado. Dos fragmentos parecidos
    de artefactos distintos suelen ser dos párrafos de contexto que se parecen
    —una introducción, una advertencia— y no dicen nada del artefacto. El
    centroide promedia eso y deja el tema.
    """
    from cerebro.config import tabla_fragmentos

    tabla = tabla_fragmentos(p)
    filas = con.execute(
        f"""select a.id, a.dominio, a.titulo, f.embedding
            from {ESQUEMA}.artefacto a
            join {ESQUEMA}.{tabla} f
              on (f.meta_data->>'artefacto_id') = a.id
            where a.valido_hasta is null and a.epoca <= %s
              and coalesce((f.meta_data->>'vigente')::bool, true)""",
        (epoca,),
    ).fetchall()

    acumulado: dict[str, list[float]] = {}
    cuenta: dict[str, int] = {}
    meta: dict[str, dict] = {}
    for f in filas:
        v = _a_lista(f["embedding"])
        if not v:
            continue
        if f["id"] not in acumulado:
            acumulado[f["id"]] = [0.0] * len(v)
            cuenta[f["id"]] = 0
            meta[f["id"]] = {"dominio": f["dominio"], "titulo": f["titulo"]}
        for i, x in enumerate(v):
            acumulado[f["id"]][i] += x
        cuenta[f["id"]] += 1

    fuera: dict[str, tuple[list[float], dict]] = {}
    for k, v in acumulado.items():
        n = cuenta[k] or 1
        med = [x / n for x in v]
        norma = sum(x * x for x in med) ** 0.5 or 1.0
        fuera[k] = ([x / norma for x in med], meta[k])
    return fuera


def _a_lista(emb: Any) -> list[float]:
    """pgvector puede llegar como lista, como su tipo propio o como cadena.

    El orden de las ramas importa: `str` se comprueba ANTES que el iterable,
    porque `list("[0.1,0.2]")` no falla — devuelve una lista de caracteres, y
    el error aparece después, en el `float('[')`. Una comprobación de tipo que
    «funciona» sobre el tipo equivocado es la clase de fallo que este
    repositorio persigue.
    """
    if emb is None:
        return []
    if isinstance(emb, str):
        return [float(x) for x in emb.strip("[] ").split(",") if x.strip()]
    if isinstance(emb, (list, tuple)):
        return [float(x) for x in emb]
    try:
        return [float(x) for x in list(emb)]
    except (TypeError, ValueError):
        return []


def diagnostico(*, epoca: int | None = None, p: Palancas = PALANCAS) -> dict[str, Any]:
    """Por qué la ventana encuentra lo que encuentra. Se mira ANTES de minar.

    Existe porque la primera versión, al no encontrar nada, sugería que «el
    corpus es pequeño o los dominios están muy separados» — y la causa real era
    otra y no estaba en la lista. Un diagnóstico que da un motivo plausible y
    equivocado es peor que no dar ninguno: te manda a arreglar lo que no está
    roto.
    """
    from cerebro.embeddings import proveedor_embeddings

    ep = epoca if epoca is not None else epoca_abierta()
    with conexion() as con:
        cent = _centroides(con, ep, p)

    ids = sorted(cent)
    ds: list[float] = []
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            if cent[a][1]["dominio"] == cent[b][1]["dominio"]:
                continue
            sim = sum(x * y for x, y in zip(cent[a][0], cent[b][0], strict=False))
            ds.append(1.0 - sim)
    ds.sort()

    prov = proveedor_embeddings()
    n = len(ds)
    d = {
        "proveedor": prov,
        "n_artefactos": len(ids),
        "n_pares_cross_dominio": n,
        "ventana": [p.analogia_min, p.analogia_max],
        "dentro": sum(1 for x in ds if p.analogia_min <= x <= p.analogia_max),
        "min": ds[0] if ds else None,
        "p25": ds[n // 4] if n else None,
        "mediana": ds[n // 2] if n else None,
        "max": ds[-1] if ds else None,
    }

    # La causa que hay que nombrar la PRIMERA, porque es la que invalida el
    # resto del diagnóstico: el embedder determinista es SHA-256 normalizado, y
    # dos hashes distintos son vectores casi ortogonales. La distancia entre
    # CUALQUIER par ronda 1,0 y no significa nada. No es que no haya analogías:
    # es que con este embedder la pregunta no se puede formular.
    if prov == "mock":
        d["veredicto"] = (
            "el embedder es `mock` (SHA-256): todos los vectores son casi "
            "ortogonales y toda distancia ronda 1,0 POR CONSTRUCCIÓN. La "
            "minería de analogías necesita un embedder real; con este no es "
            "que no encuentre, es que la pregunta no se puede formular."
        )
    elif not n:
        d["veredicto"] = "no hay ningún par de artefactos de dominios distintos"
    elif d["dentro"] == 0 and d["mediana"] is not None:
        d["veredicto"] = (
            f"la ventana [{p.analogia_min}, {p.analogia_max}] no coge nada: la "
            f"mediana real es {d['mediana']:.2f}. Ajusta `analogia_min` y "
            "`analogia_max` a la distribución de TU corpus."
        )
    else:
        d["veredicto"] = f"{d['dentro']} par(es) en la ventana"
    return d


def candidatas(
    *, epoca: int | None = None, p: Palancas = PALANCAS, tope: int = 40
) -> list[Candidata]:
    """Los pares que pasan los tres filtros baratos, ordenados por prometedores."""
    from cerebro.grafo import cargar

    ep = epoca if epoca is not None else epoca_abierta()
    g = cargar(epoca=ep)

    with conexion() as con:
        cent = _centroides(con, ep, p)

    ids = sorted(cent)
    fuera: list[Candidata] = []
    for i, a in enumerate(ids):
        va, ma = cent[a]
        for b in ids[i + 1:]:
            vb, mb = cent[b]
            # filtro 1 · dominios distintos
            if ma["dominio"] == mb["dominio"]:
                continue
            # filtro 3 · sin arista previa, en ninguna dirección
            if b in g.vecinos.get(a, {}) or a in g.vecinos.get(b, {}):
                continue
            sim = sum(x * y for x, y in zip(va, vb, strict=False))
            dist = 1.0 - sim
            # filtro 2 · la ventana
            if not (p.analogia_min <= dist <= p.analogia_max):
                continue
            fuera.append(Candidata(a, b, ma["dominio"], mb["dominio"], dist,
                                   ma["titulo"], mb["titulo"]))

    # Del centro de la ventana hacia fuera: el par más prometedor es el que está
    # justo en la distancia donde suele haber analogía, no el más cercano —ese
    # es casi un duplicado— ni el más lejano, que es casi ruido.
    centro = (p.analogia_min + p.analogia_max) / 2
    fuera.sort(key=lambda c: abs(c.distancia - centro))
    return fuera[:tope]


async def minar(
    *, epoca: int | None = None, p: Palancas = PALANCAS, tope: int = 12
) -> dict[str, int]:
    """Pasa las candidatas por el modelo y encola las que sobreviven.

    El modelo NO decide si se parecen: eso ya lo decidió la distancia. Decide si
    hay una **abstracción compartida que se pueda nombrar**, y tiene que
    escribirla. Una analogía que no se puede nombrar no se puede comprobar, y
    una que no se puede comprobar no se puede revisar en diez segundos, que es
    todo el presupuesto que una cola de propuestas tiene.
    """
    from agno.agent import Agent

    from cerebro.agente import construir_modelo

    ep = epoca if epoca is not None else epoca_abierta()
    cands = candidatas(epoca=ep, p=p, tope=tope * 3)
    if not cands:
        return {"candidatas": 0, "propuestas": 0, "descartadas": 0}

    modelo = construir_modelo(p)
    if modelo is None:
        return {"candidatas": len(cands), "propuestas": 0, "descartadas": 0}

    verificador = Agent(
        model=modelo,
        instructions=[
            "Te doy dos notas de investigación de DOMINIOS distintos.",
            "Decide si comparten una ABSTRACCIÓN que se pueda nombrar en una frase.",
            "Responde exactamente en este formato, sin nada más:",
            "VEREDICTO: si|no",
            "ABSTRACCION: <una frase, o vacío si el veredicto es no>",
            "COMPROBABLE: <cómo se vería que la abstracción es real en las dos notas>",
            "",
            "Di 'no' por defecto. Que dos notas técnicas usen palabras parecidas "
            "no es una analogía. Que las dos hablen de 'fallos' o de 'medición' "
            "tampoco: eso es el tema, no la abstracción.",
        ],
        markdown=False,
    )

    propuestas = descartadas = 0
    with conexion() as con:
        for c in cands:
            if propuestas >= tope:
                break
            if _ya_propuesta(con, c.a, c.b):
                continue
            texto = (
                f"NOTA A · dominio {c.dominio_a}\n{c.titulo_a}\n\n"
                f"NOTA B · dominio {c.dominio_b}\n{c.titulo_b}"
            )
            r = await verificador.arun(texto)
            v = _parsear(r.content or "")
            if not v["si"] or not v["abstraccion"]:
                descartadas += 1
                continue
            con.execute(
                f"""insert into {ESQUEMA}.propuesta
                      (clase, epoca, sujeto, objeto, cuerpo, evidencia)
                    values ('analogia', %s, %s, %s, %s, %s)""",
                (ep, c.a, c.b,
                 json.dumps({"abstraccion": v["abstraccion"],
                             "comprobable": v["comprobable"]}, ensure_ascii=False),
                 json.dumps({"distancia": round(c.distancia, 4),
                             "dominio_a": c.dominio_a, "dominio_b": c.dominio_b,
                             "modelo": getattr(modelo, "id", "?")}, ensure_ascii=False)),
            )
            propuestas += 1
        con.commit()

    return {"candidatas": len(cands), "propuestas": propuestas, "descartadas": descartadas}


def _parsear(texto: str) -> dict[str, Any]:
    d = {"si": False, "abstraccion": "", "comprobable": ""}
    for linea in texto.splitlines():
        x = linea.strip()
        if x.upper().startswith("VEREDICTO:"):
            d["si"] = x.split(":", 1)[1].strip().lower().startswith("si")
        elif x.upper().startswith("ABSTRACCION:"):
            d["abstraccion"] = x.split(":", 1)[1].strip()
        elif x.upper().startswith("COMPROBABLE:"):
            d["comprobable"] = x.split(":", 1)[1].strip()
    return d


def _ya_propuesta(con, a: str, b: str) -> bool:
    """Una analogía rechazada NO vuelve a proponerse.

    Sin esto la cola repite lo mismo cada noche y en dos semanas nadie la abre,
    que es la forma en que mueren las colas de revisión.
    """
    return bool(
        con.execute(
            f"""select 1 from {ESQUEMA}.propuesta
                where clase='analogia'
                  and ((sujeto=%s and objeto=%s) or (sujeto=%s and objeto=%s))
                limit 1""",
            (a, b, b, a),
        ).fetchone()
    )


# --------------------------------------------------------------------------- #
# La cola
# --------------------------------------------------------------------------- #


def pendientes(clase: str | None = None) -> list[dict[str, Any]]:
    cond = "estado='pendiente'" + (" and clase=%s" if clase else "")
    args = (clase,) if clase else ()
    with conexion() as con:
        return [
            dict(f)
            for f in con.execute(
                f"""select id, ts, clase, sujeto, objeto, cuerpo, evidencia
                    from {ESQUEMA}.propuesta where {cond} order by id""",
                args,
            ).fetchall()
        ]


def resolver(id_: int, *, aceptada: bool, motivo: str = "") -> dict[str, Any] | None:
    """Firma o descarta. Aceptar escribe la arista; rechazar guarda el motivo.

    El motivo de un rechazo es el dato más caro de conseguir y el primero que se
    pierde. Se guarda porque es lo que permitiría algún día ajustar la ventana
    de distancia con datos en vez de a ojo.
    """
    with conexion() as con:
        fila = con.execute(
            f"select * from {ESQUEMA}.propuesta where id=%s and estado='pendiente'",
            (id_,),
        ).fetchone()
        if fila is None:
            return None

        con.execute(
            f"""update {ESQUEMA}.propuesta
                set estado=%s, resuelta_en=now(), motivo=%s where id=%s""",
            ("aceptada" if aceptada else "rechazada", motivo or None, id_),
        )

        if aceptada and fila["clase"] == "analogia" and fila["objeto"]:
            cuerpo = fila["cuerpo"] or {}
            for o, d in ((fila["sujeto"], fila["objeto"]), (fila["objeto"], fila["sujeto"])):
                con.execute(
                    f"""insert into {ESQUEMA}.arista
                          (origen, destino, tipo, peso, procedencia, epoca, detalle)
                        values (%s,%s,'analogia',2.0,'firmada',%s,%s)
                        on conflict (origen, destino, tipo) do update set
                          valido_hasta = null, detalle = excluded.detalle""",
                    (o, d, fila["epoca"],
                     json.dumps({"abstraccion": cuerpo.get("abstraccion", "")},
                                ensure_ascii=False)),
                )
        con.commit()
        return dict(fila)
