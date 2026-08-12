"""
El cerebro: traduce PALANCAS a objetos de Agno.

Reparto deliberado:

  ESCRITURA   la posee Agno. `Knowledge` + `PgVector` hacen el troceado, el
              embedding, el upsert por content_hash y los filtros jsonb. Forkear
              eso para añadir tres columnas sería pagar mantenimiento eterno.

  LECTURA     la poseemos nosotros, vía `knowledge_retriever`. Ver recuperador.py
              para los tres motivos, todos verificados contra 2.8.6.

Verificado contra agno 2.8.6.
"""

from __future__ import annotations

from agno.agent import Agent
from agno.db.postgres import PostgresDb
from agno.knowledge.knowledge import Knowledge
from agno.vectordb.distance import Distance
from agno.vectordb.pgvector import PgVector, SearchType

from cerebro.config import DB_URL, ESQUEMA, JUEZ, PALANCAS, SISTEMA, Palancas, tabla_fragmentos
from cerebro.embeddings import construir_embedder


def construir_vector_db(p: Palancas = PALANCAS) -> PgVector:
    """El almacén de fragmentos.

    `search_type=vector` y no `hybrid` a propósito: la fusión híbrida de Agno
    suma linealmente un coseno y un `ts_rank_cd` normalizado, dos escalas que no
    son comparables, y su predicado `@@` está comentado (pgvector.py:1157) así
    que además escanea la tabla entera. Los dos carriles y su fusión RRF viven en
    recuperador.py. Aquí PgVector solo escribe.

    Tampoco se le pasa `reranker`: el reordenador se aplica sobre el pool
    fusionado, no dentro de un carril.
    """
    return PgVector(
        table_name=tabla_fragmentos(p),
        schema=ESQUEMA,
        db_url=DB_URL,
        search_type=SearchType.vector,
        distance=Distance(p.distancia),
        content_language=p.idioma_fts,
        embedder=construir_embedder(p),
    )


def construir_knowledge(p: Palancas = PALANCAS) -> Knowledge:
    # max_results ES el top-k del agente. No es un parámetro del Agent.
    return Knowledge(name="cerebro", vector_db=construir_vector_db(p), max_results=p.top_k)


def construir_reordenador(p: Palancas = PALANCAS):
    """Reordenador nativo de Agno, aplicado por nosotros sobre el pool fusionado.

    Toda implementación degrada a identidad ante excepción: la recuperación no se
    rompe nunca por culpa de esta etapa. Es el invariante del `Reranker` de
    CVs-SaaS y es la razón de que allí nunca se cayera una respuesta por el
    reordenador.
    """
    if p.reranker == "cohere":
        from agno.knowledge.reranker.cohere import CohereReranker

        return CohereReranker(model="rerank-v3.5", top_n=p.reranker_top_n)
    if p.reranker == "local":
        try:
            from agno.knowledge.reranker.sentence_transformer import (
                SentenceTransformerReranker,
            )
        except ImportError as e:
            raise ImportError(
                "reranker='local' necesita sentence-transformers. Instálalo con "
                "`uv run rag extras`, o usa reranker='none'."
            ) from e
        return SentenceTransformerReranker(
            model="BAAI/bge-reranker-v2-m3", top_n=p.reranker_top_n
        )
    return None


def construir_modelo(id_modelo: str):
    """Un id de modelo a su objeto de Agno.

    Tres modos:

      mock    no se llama nunca. Los caminos que usan modelo están cortados
              aguas arriba; existe para que construir el agente no reviente.
      falso   `scripts/modelo_falso.py`, un guion que habla el protocolo de
              OpenAI. Ejercita el camino REAL de Agno —tool calls,
              output_schema, references, rollouts— sin ninguna clave.
      real    anthropic | openai | google según el id.
    """
    import os

    proveedor = (os.getenv("LLM_PROVIDER") or "mock").strip().lower()

    if proveedor == "mock":
        from agno.models.openai import OpenAILike

        return OpenAILike(id="mock", api_key="mock", base_url="http://localhost:1/v1")

    if proveedor == "falso":
        from agno.models.openai import OpenAILike

        url = os.getenv("MODELO_FALSO_URL", "http://127.0.0.1:7799/v1")
        return OpenAILike(id=id_modelo, api_key="falso", base_url=url)

    fam = id_modelo.split("-")[0].lower()
    if fam == "claude":
        from agno.models.anthropic import Claude

        return Claude(id=id_modelo)
    if fam == "gemini":
        from agno.models.google import Gemini

        return Gemini(id=id_modelo)
    from agno.models.openai import OpenAIChat

    return OpenAIChat(id=id_modelo)


def construir_db() -> PostgresDb:
    """Sesiones, trazas, evals y schedules. Las sesiones SON los datos de uso de
    los que salen las probes mineradas del tráfico real."""
    return PostgresDb(db_url=DB_URL, db_schema=ESQUEMA)


def construir_agente(p: Palancas = PALANCAS, *, epoca: int | None = None) -> Agent:
    """El cerebro.

    `epoca` solo se pasa al MEDIR. Al servir es None y el agente ve todo el
    corpus: congelamos la vista para medir, no el corpus para servir.
    """
    from cerebro.recuperador import construir_recuperador

    return Agent(
        name="Cerebro",
        id="cerebro",
        model=construir_modelo(SISTEMA),
        db=construir_db(),
        knowledge=construir_knowledge(p),
        knowledge_retriever=construir_recuperador(p, epoca=epoca),
        search_knowledge=True,
        instructions=list(p.instrucciones),
        markdown=False,  # empieza por el dato
        store_events=True,  # sin esto las trazas no quedan en la base
    )


# Nada de `cerebro = construir_agente()` a nivel de módulo: PgVector abre la
# conexión al construirse, así que un import con la base caída se queda colgado
# hasta que expira el tiempo de espera. Quien necesite el agente lo construye.

__all__ = [
    "JUEZ",
    "SISTEMA",
    "construir_agente",
    "construir_db",
    "construir_knowledge",
    "construir_modelo",
    "construir_reordenador",
    "construir_vector_db",
]
