"""
Fusión de carriles por Reciprocal Rank Fusion.

Extraído de `CVs-SaaS/backend/src/graph/application/retrieval/fusion.py` y de
`_base.py`, con pesos por carril añadidos.

**Por qué RRF y no la fusión híbrida de Agno.** `PgVector.hybrid_search` combina
los carriles con una suma lineal —`w·vector_score + (1-w)·text_rank`— de dos
escalas que no son comparables: un coseno y un `ts_rank_cd` normalizado. Eso
significa dos cosas malas. Una, que `peso_vectorial = 0.5` no quiere decir
«mitad y mitad» y no tiene punto medio interpretable. Dos, que es exactamente la
patología del tipo de cambio: los pesos definen una tasa de conversión entre
métricas y el optimizador la usará para maximizar el número.

RRF es rank-only y lane-agnostic **a propósito**, y por eso es inmune: no mira
los scores, solo las posiciones. El peso por carril sigue siendo una palanca,
pero opera sobre una escala común.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class Hit:
    """Un resultado de un solo carril.

    `score` significa cosas distintas según el carril (coseno, `ts_rank_cd`), así
    que solo sirve para desempatar y para diagnosticar. Lo que fusiona es el
    RANGO. Por eso `score_tipo` no es opcional: un 0,87 sin saber de qué escala
    viene no significa nada, y esa ambigüedad es la que hace indistinguibles tres
    movimientos distintos cuando el bucle mueve una palanca.
    """

    doc_id: str
    contenido: str
    score: float | None
    score_tipo: str
    rango: int
    carril: str
    meta: dict = field(default_factory=dict)


@dataclass(slots=True)
class Fusionado:
    """Un resultado fusionado, con su procedencia completa."""

    doc_id: str
    contenido: str
    score_fusion: float
    meta: dict = field(default_factory=dict)
    #: carril -> {rango, score}. Es literalmente la regla de rag-glue: el score
    #: capturado en el instante de la búsqueda. Sin esto no se puede escribir
    #: «la léxica lo tenía en el puesto 3 y la vectorial en el 180», que es la
    #: frase que de verdad diagnostica.
    por_carril: dict[str, dict[str, float | None]] = field(default_factory=dict)
    rango_final: int = 0


def rrf(
    rankings: list[list[Hit]],
    *,
    k: int = 60,
    top_k: int = 12,
    pesos: dict[str, float] | None = None,
) -> list[Fusionado]:
    """RRF como en Cormack, Clarke & Buettcher (SIGIR 2009).

    score(d) = Σ_carril  peso_carril / (k + rango_carril(d))

    k=60 es el canónico y el que usan Weaviate, Vespa y OpenSearch por defecto.
    Qdrant usa 2, con otra fórmula: cualquier umbral copiado de un ejemplo está
    sesgado si no se fija k explícitamente.

    Los rangos son 1-indexados. Un rango 0 se trata como «no rankeado» y no
    contribuye — un `1/(k+0)` daría a un no-resultado el peso del primer puesto.
    """
    pesos = pesos or {}
    agregado: dict[str, Fusionado] = {}

    for ranking in rankings:
        for hit in ranking:
            if hit.rango <= 0:
                continue
            peso = pesos.get(hit.carril, 1.0)
            contribucion = peso / (k + hit.rango)

            actual = agregado.get(hit.doc_id)
            if actual is None:
                actual = Fusionado(
                    doc_id=hit.doc_id,
                    contenido=hit.contenido,
                    score_fusion=0.0,
                    meta=dict(hit.meta),
                )
                agregado[hit.doc_id] = actual
            actual.score_fusion += contribucion
            actual.por_carril[hit.carril] = {
                "rango": float(hit.rango),
                "score": hit.score,
                "tipo": hit.score_tipo,  # type: ignore[dict-item]
            }

    fuera = sorted(agregado.values(), key=lambda r: (-r.score_fusion, r.doc_id))
    for i, r in enumerate(fuera, start=1):
        r.rango_final = i
    return fuera[:top_k]


def a_dicts(resultados: list[Fusionado]) -> list[dict]:
    """La forma que devuelve el `knowledge_retriever` al agente.

    `Document.to_dict()` de Agno 2.8.6 devuelve solo {name, meta_data, content}:
    descarta `id` y `reranking_score`, y el parecido sobrevive únicamente porque
    PgVector lo escribe dentro de `meta_data`. Devolviendo dicts propios nos
    saltamos esa pérdida y el score llega entero al juez, que es quien lo
    necesita para distinguir `cobertura` de `ordenacion`.
    """
    return [
        {
            "name": r.meta.get("artefacto_id", r.doc_id),
            "content": r.contenido,
            "meta_data": {
                **r.meta,
                "doc_id": r.doc_id,
                "rango": r.rango_final,
                "score_fusion": round(r.score_fusion, 6),
                "score_tipo": "rrf",
                "por_carril": r.por_carril,
            },
        }
        for r in resultados
    ]
