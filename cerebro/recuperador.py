"""
El recuperador: dos carriles, fusión RRF, reordenación y captura de la traza.

**Por qué esto existe en vez de usar `Knowledge.search()`.** Tres motivos, los
tres verificados contra agno 2.8.6, ninguno estético:

1. *Por el camino por defecto el score se pierde.* `Document.to_dict()`
   (knowledge/document/base.py:39) devuelve solo `{name, meta_data, content}`:
   descarta `id` y `reranking_score`. Sin score no hay forma de distinguir
   «el fragmento no llegó» de «llegó enterrado», que son los dos diagnósticos
   que abren juegos de palancas distintos.

2. *`hybrid_search` no sirve.* Su predicado `@@` está comentado
   (pgvector.py:1157), así que escanea la tabla entera y ningún índice puede
   ayudar; y fusiona con una suma lineal de un coseno y un `ts_rank_cd`, dos
   escalas incomparables cuyo peso es un tipo de cambio que el optimizador
   explotará. RRF fusiona por RANGO y es inmune a eso.

3. *Hace falta el rango POR CARRIL, antes de fusionar.* Sin él, mover
   `peso_carril`, el embedder y el analizador léxico son tres movimientos
   indistinguibles: el bucle mueve palancas al azar y mira si el número sube.

Los carriles corren en secuencia. A esta escala (~10^3 fragmentos) son unos
milisegundos cada uno y el paralelismo sería complejidad sin premio. Deja de ser
cierto alrededor de los 10^4-10^5 fragmentos; ese es el número que hay que
vigilar, y `ms_por_etapa` en la traza es donde se ve venir.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from typing import Any

from cerebro.almacen import ESQUEMA, conexion
from cerebro.config import INDEX_BOUND, PALANCAS, Palancas, huella, tabla_fragmentos
from cerebro.embeddings import construir_embedder
from cerebro.fusion import Fusionado, Hit, a_dicts, rrf


def _condiciones(p: Palancas, epoca: int | None) -> tuple[str, list[Any]]:
    """Los filtros de metadatos, como SQL. Son la palanca más barata que existe."""
    partes: list[str] = []
    args: list[Any] = []

    if p.solo_vigentes:
        # Un artefacto superado sigue en la tabla —nunca se borra— pero sale de
        # la búsqueda. "No reviertas: invalida", implementado como un filtro.
        partes.append("coalesce(meta_data->>'vigente', 'true') = 'true'")

    if epoca is not None:
        # Medir a la época E es filtrar, no copiar. Congelamos la vista, no el
        # corpus: servir NO pasa por aquí y ve todo lo que hay.
        partes.append("(meta_data->>'epoca')::int <= %s")
        args.append(epoca)

    if p.filtro_tipo:
        partes.append("meta_data->>'tipo' = any(%s)")
        args.append(list(p.filtro_tipo))

    if p.filtro_dominio:
        partes.append("meta_data->>'dominio' = any(%s)")
        args.append(list(p.filtro_dominio))

    return (" and ".join(partes) if partes else "true"), args


def _carril_denso(con, p: Palancas, vector: list[float], epoca: int | None) -> list[Hit]:
    tabla = f'{ESQUEMA}."{tabla_fragmentos(p)}"'
    where, args = _condiciones(p, epoca)
    lit = "[" + ",".join(f"{x:.7g}" for x in vector) + "]"

    umbral = ""
    if p.umbral_similitud is not None:
        umbral = f"and (1 - (embedding <=> %s::vector)) >= {float(p.umbral_similitud)}"
        args = args + [lit]

    # En su propia sentencia: psycopg no admite varios comandos en un prepared
    # statement. Y sin LOCAL, porque con autocommit no hay transacción a la que
    # atarlo — la conexión es de una consulta, así que el alcance de sesión vale.
    con.execute(f"set hnsw.ef_search = {int(p.ef_search)}")

    filas = con.execute(
        f"select id, name, content, meta_data, "  # noqa: S608
        f"       1 - (embedding <=> %s::vector) as score "
        f"from {tabla} where {where} {umbral} "
        f"order by embedding <=> %s::vector limit %s",
        [lit, *args, lit, p.top_k_por_carril],
    ).fetchall()

    return [
        Hit(doc_id=f["id"], contenido=f["content"], score=float(f["score"]),
            score_tipo="cosine", rango=i, carril="denso",
            meta={**(f["meta_data"] or {}), "name": f["name"]})
        for i, f in enumerate(filas, start=1)
    ]


def _carril_lexico(con, p: Palancas, consulta: str, epoca: int | None) -> list[Hit]:
    """Cover-density ranking de Postgres, no BM25 de manual. Se dice porque es
    lo que es: `ts_rank_cd` premia la proximidad de los términos, no la
    frecuencia inversa de documento.

    Y aquí SÍ va el predicado `@@` que Agno tiene comentado: sin él no se usa el
    índice GIN y la consulta escanea la tabla entera.
    """
    tabla = f'{ESQUEMA}."{tabla_fragmentos(p)}"'
    where, args = _condiciones(p, epoca)
    idioma = p.idioma_fts

    # `plainto_tsquery` une los términos con AND: "por qué el índice HNSW no
    # existe" se convierte en 'indic' & 'hnsw' & 'exist', y solo casa el
    # fragmento que contenga LOS TRES. Para un carril de recuperación eso es
    # letal: la consulta más informativa es la que menos recupera.
    #
    # Con OR, `ts_rank_cd` hace su trabajo — el que casa más términos y más
    # juntos puntúa más alto — y el ranking, que es lo que RRF consume, sale
    # bien ordenado. Se conserva `plainto_tsquery` por delante para heredar su
    # stemming, sus stopwords y su saneado de la entrada.
    # La expresión con cast va en un CTE: un `replace(...)::tsquery` no es una
    # llamada a función y Postgres no lo admite como elemento del FROM.
    consulta_ts = (
        f"replace(plainto_tsquery('{idioma}', %s)::text, ' & ', ' | ')::tsquery"
        if p.fts_modo == "or"
        else f"plainto_tsquery('{idioma}', %s)"
    )

    filas = con.execute(
        f"with q as (select {consulta_ts} as tsq) "  # noqa: S608
        f"select f.id, f.name, f.content, f.meta_data, "
        f"       ts_rank_cd(to_tsvector('{idioma}', f.content), q.tsq) as score "
        f"from {tabla} f, q "
        f"where {where.replace('meta_data', 'f.meta_data')} "
        f"  and to_tsvector('{idioma}', f.content) @@ q.tsq "
        f"order by score desc limit %s",
        [consulta, *args, p.top_k_por_carril],
    ).fetchall()

    return [
        Hit(doc_id=f["id"], contenido=f["content"], score=float(f["score"]),
            score_tipo="ts_rank_cd", rango=i, carril="lexico",
            meta={**(f["meta_data"] or {}), "name": f["name"]})
        for i, f in enumerate(filas, start=1)
    ]


def _reordenar(p: Palancas, pool: list[Fusionado], consulta: str) -> list[Fusionado]:
    """Reordena el pool fusionado. Degrada a identidad ante cualquier fallo.

    Puerta de latencia, de CVs-SaaS: si el pool no es más ancho que lo que se va
    a devolver, el reordenador no puede DESCARTAR nada, solo reordenar, y no se
    gana su latencia. Se salta.
    """
    if p.reranker == "none" or len(pool) <= p.top_k:
        return pool[: p.top_k]

    from agno.knowledge.document.base import Document

    from cerebro.agente import construir_reordenador

    try:
        rr = construir_reordenador(p)
        if rr is None:
            return pool[: p.top_k]
        docs = [Document(id=f.doc_id, content=f.contenido, meta_data=f.meta) for f in pool]
        ordenados = rr.rerank(query=consulta, documents=docs)
        por_id = {f.doc_id: f for f in pool}
        fuera: list[Fusionado] = []
        for rango, d in enumerate(ordenados[: p.top_k], start=1):
            f = por_id.get(d.id or "")
            if f is None:
                continue
            f.por_carril["rerank"] = {
                "rango": float(rango),
                "score": d.reranking_score,
                "tipo": p.reranker,  # type: ignore[dict-item]
            }
            f.rango_final = rango
            fuera.append(f)
        return fuera or pool[: p.top_k]
    except Exception:
        # El invariante de CVs-SaaS: la recuperación no se rompe jamás por culpa
        # de la etapa de reordenación.
        return pool[: p.top_k]


def _guardar_traza(
    con, p: Palancas, *, consulta: str, consulta_efectiva: str, epoca: int | None,
    pool: list[Fusionado], devueltos: list[Fusionado], ms: dict[str, float],
    es_probe: bool, probe_id: str | None,
) -> None:
    """Se persiste EL POOL ENTERO, no los top_k devueltos.

    Los descartados son justo lo que ningún motor deja ver, y son la mitad del
    diagnóstico de `ordenacion`: para saber que el fragmento bueno llegó y se
    quedó en el puesto 27 hay que haber guardado el puesto 27.
    """
    hits = [
        {
            "doc_id": f.doc_id,
            "rango_fusion": f.rango_final,
            "score_fusion": round(f.score_fusion, 6),
            "por_carril": f.por_carril,
            "artefacto": (f.meta or {}).get("artefacto_id"),
            "devuelto": f.doc_id in {d.doc_id for d in devueltos},
        }
        for f in pool
    ]
    con.execute(
        f"insert into {ESQUEMA}.consulta "
        "(huella_config, huella_indice, epoca_filtro, consulta, consulta_efectiva, "
        " es_probe, probe_id, n_devueltos, ms_por_etapa, hits) "
        "values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        (
            huella(p, INDEX_BOUND), tabla_fragmentos(p), epoca, consulta,
            consulta_efectiva, es_probe, probe_id, len(devueltos),
            json.dumps(ms), json.dumps(hits),
        ),
    )


def _reescribir(consulta: str, p: Palancas):
    """Aplica la reescritura configurada. Ver `cerebro/reescritura.py`.

    Solo los modos sin llamada se resuelven aquí: abrir un bucle de eventos
    dentro del recuperador rompería el que Agno ya tiene abierto para el turno.
    Los modos HyDE se resuelven arriba y llegan ya reescritos, y el modo se
    registra igual para que la traza no mienta sobre lo que pasó.
    """
    from cerebro.reescritura import reescribir_sinc

    return reescribir_sinc(consulta, p)


def _semillas_de(ranking: list[Hit], cuantas: int) -> dict[str, float]:
    """Los artefactos mejor colocados del carril denso, con peso por puesto.

    Por puesto y no por score: el score del carril denso es una distancia coseno
    cuya escala no significa nada fuera de su propia consulta, y meterla como
    peso de reinicio del PPR sería el mismo error de escalas incomparables que
    RRF existe para evitar. `1/(1+rango)` es monótono y adimensional.
    """
    peso: dict[str, float] = {}
    for h in ranking:
        art = (h.meta or {}).get("artefacto_id")
        if not art or art in peso:
            continue
        peso[art] = 1.0 / (1.0 + len(peso))
        if len(peso) >= cuantas:
            break
    return peso


def _carril_grafo(p: Palancas, semillas: dict[str, float], epoca: int | None) -> list[Hit]:
    """El tercer carril: PPR sobre el grafo de artefactos.

    Devuelve **fragmentos**, no artefactos, porque la fusión trabaja en
    fragmentos y devolver artefactos obligaría a una segunda unidad de cuenta.
    De cada artefacto vecino se toma su primer fragmento, que por construcción
    del troceado es el que lleva la cabecera con título, tipo y temas — o sea el
    más representativo del artefacto entero.
    """
    from cerebro.grafo import cargar, ppr

    if not semillas:
        return []
    g = cargar(epoca=epoca)
    puntuados = ppr(g, semillas, alfa=p.grafo_alfa)
    if not puntuados:
        return []

    mejores = sorted(puntuados.items(), key=lambda kv: -kv[1])[: p.grafo_top_k]
    ids = [a for a, _ in mejores]
    tabla = tabla_fragmentos(p)

    hits: list[Hit] = []
    with conexion(autocommit=True) as con:
        for rango, (art, score) in enumerate(mejores, start=1):
            fila = con.execute(
                f"""select id, content, meta_data from {ESQUEMA}.{tabla}
                    where meta_data->>'artefacto_id' = %s
                      and coalesce((meta_data->>'vigente')::bool, true)
                    order by (meta_data->>'indice')::int nulls last
                    limit 1""",
                (art,),
            ).fetchone()
            if fila is None:
                continue
            hits.append(Hit(
                doc_id=fila["id"],
                contenido=fila["content"],
                score=float(score),
                score_tipo="ppr",
                rango=rango,
                carril="grafo",
                meta=fila["meta_data"] or {},
            ))
    _ = ids
    return hits


def construir_recuperador(
    p: Palancas = PALANCAS,
    *,
    epoca: int | None = None,
    es_probe: bool = False,
    probe_id: str | None = None,
) -> Callable[..., list[dict]]:
    """Devuelve la función que se pasa a `Agent(knowledge_retriever=...)`.

    Agno introspecciona la firma: pasa `query` y `num_documents` siempre, y
    `agent` / `filters` / `run_context` solo si están declarados
    (agent/_messages.py:1841-1857). Y RE-LANZA la excepción tras loguearla, así
    que un fallo aquí mata el turno: por eso cada carril va envuelto por
    separado y un carril muerto degrada en vez de romper.
    """
    embedder = construir_embedder(p)

    def recuperar(query: str, num_documents: int | None = None, **kwargs: Any) -> list[dict]:
        # El enrutado decide ANTES de nada: puede cambiar top_k, los pesos y el
        # modo del FTS. Devuelve unas palancas nuevas y su motivo, y el motivo
        # va a la traza — una decisión de enrutado que no se puede leer después
        # es una palanca cuyo efecto nadie puede diagnosticar.
        from cerebro.enrutador import enrutar

        ruta = enrutar(query, p)
        pr = ruta.palancas

        top_k = num_documents or pr.top_k
        ms: dict[str, float] = {}
        t0 = time.perf_counter()

        rw = _reescribir(query, pr)
        efectiva = rw.para_denso
        vector = embedder.get_embedding(efectiva)
        ms["embed"] = round((time.perf_counter() - t0) * 1000, 2)

        rankings: list[list[Hit]] = []
        nombres: list[str] = []
        with conexion(autocommit=True) as con:
            for nombre, fn in (("denso", _carril_denso), ("lexico", _carril_lexico)):
                if nombre not in pr.carriles:
                    continue
                t = time.perf_counter()
                try:
                    # Cada carril busca lo SUYO. El denso quiere prosa (el
                    # señuelo de HyDE); el léxico quiere los símbolos exactos
                    # que escribiste, que una nota generada casi nunca trae.
                    arg = vector if nombre == "denso" else rw.para_lexico
                    rankings.append(fn(con, pr, arg, epoca))  # type: ignore[arg-type]
                except Exception as exc:
                    # Un carril caído degrada la recuperación; no la mata. Pero
                    # se registra: un carril que lleva semanas caído y nadie lo
                    # sabe es peor que uno que revienta.
                    ms[f"{nombre}_error"] = 1.0
                    rankings.append([])
                    print(f"  carril {nombre} caído: {type(exc).__name__}: {exc}")
                nombres.append(nombre)
                ms[nombre] = round((time.perf_counter() - t) * 1000, 2)

            # --- el tercer carril, el de grafo. Va DESPUÉS de los otros dos
            # porque se siembra con lo que el denso encontró: no busca, amplía.
            if pr.grafo_activo and rankings:
                t = time.perf_counter()
                try:
                    semillas = _semillas_de(rankings[0], pr.grafo_semillas)
                    rankings.append(_carril_grafo(pr, semillas, epoca))
                    nombres.append("grafo")
                except Exception as exc:  # noqa: BLE001
                    ms["grafo_error"] = 1.0
                    rankings.append([])
                    nombres.append("grafo")
                    print(f"  carril grafo caído: {type(exc).__name__}: {exc}")
                ms["grafo"] = round((time.perf_counter() - t) * 1000, 2)

            t = time.perf_counter()
            pesos = dict(zip(pr.carriles, pr.peso_carril, strict=False))
            pesos.setdefault("grafo", 1.0)
            pool = rrf(rankings, k=pr.k_rrf, top_k=pr.pool_fusion, pesos=pesos)
            ms["fusion"] = round((time.perf_counter() - t) * 1000, 2)
            ms["_ruta"] = ruta.regla  # type: ignore[assignment]
            ms["_reescritura"] = rw.modo  # type: ignore[assignment]

            t = time.perf_counter()
            devueltos = _reordenar(pr, pool, query)
            ms["rerank"] = round((time.perf_counter() - t) * 1000, 2)
            ms["total"] = round((time.perf_counter() - t0) * 1000, 2)

            _guardar_traza(
                con, pr, consulta=query, consulta_efectiva=efectiva, epoca=epoca,
                pool=pool, devueltos=devueltos, ms=ms, es_probe=es_probe,
                probe_id=probe_id,
            )

        return a_dicts(devueltos[:top_k])

    return recuperar
