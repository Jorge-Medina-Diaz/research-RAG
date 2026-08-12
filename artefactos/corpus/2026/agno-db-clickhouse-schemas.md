---
tipo: lectura-paper
titulo: DDL statements used by the ClickHouse traces DB
fecha: 2026-08-12
temas: [agno, clickhouse, schemas]
dominio: datos
madurez: maduro
confianza: alta
fuentes:
  - tipo: repo
    ref: agno-agi/agno
    commit: v2.8.6
    acceso: 2026-08-12
---

> Corpus AJENO. Documentación del módulo `db\clickhouse\schemas.py` de Agno 2.8.6,
> tal cual la escribieron sus autores. No es una nota propia y no está
> verificada: entra al corpus para que el golden set deje de preguntar
> solo por material que ya conoces.

DDL statements used by the ClickHouse traces DB.

ClickHouse is an OLAP store — it is a great fit for trace ingestion (high write
throughput, columnar scans for aggregate queries) but a poor fit for sessions,
memories, or anything that needs row-level updates. The adapter only persists
the trace/span tables; everything else on ``BaseDb`` raises ``NotImplementedError``.

Engine choice:

* ``traces`` uses ``MergeTree``. The exporter ingests a trace as several
  partial rows (one per span batch), reconciled into one row per ``trace_id`` at
  read time. ``MergeTree`` never drops rows, so every partial survives background
  merges.
* ``spans`` uses ``MergeTree`` — spans are immutable and append-only.

Partitioning is by month on ``start_time`` so retention can be enforced with a
single ``ALTER TABLE ... DROP PARTITION`` if desired.
