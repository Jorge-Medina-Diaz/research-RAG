---
tipo: lectura-paper
titulo: ClickHouse traces database adapter
fecha: 2026-08-12
temas: [agno, clickhouse]
dominio: datos
madurez: maduro
confianza: alta
fuentes:
  - tipo: repo
    ref: agno-agi/agno
    commit: v2.8.6
    acceso: 2026-08-12
---

> Corpus AJENO. Documentación del módulo `db\clickhouse\clickhouse.py` de Agno 2.8.6,
> tal cual la escribieron sus autores. No es una nota propia y no está
> verificada: entra al corpus para que el golden set deje de preguntar
> solo por material que ya conoces.

ClickHouse traces database adapter.

This adapter is intentionally **traces-only**. ClickHouse is a columnar OLAP
store that excels at high-volume append workloads (traces, events, metrics)
and at fast aggregate scans, but it does not provide row-level updates or
transactional guarantees suitable for sessions, memories, knowledge content,
or component configs. Pair this DB with a row-store (e.g. ``PostgresDb``) for
those concerns and use ``ClickhouseDb`` exclusively for tracing.

Typical usage::

    from agno.db.postgres import PostgresDb
    from agno.db.clickhouse import ClickhouseDb
    from agno.tracing import setup_tracing

    primary_db = PostgresDb(db_url="postgresql+psycopg://...")
    traces_db = ClickhouseDb(host="localhost", port=8123, database="agno_traces")

    setup_tracing(db=traces_db, batch_processing=True)
