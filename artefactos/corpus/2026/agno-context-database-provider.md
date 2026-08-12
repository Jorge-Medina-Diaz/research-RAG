---
tipo: lectura-paper
titulo: Database Context Provider
fecha: 2026-08-12
temas: [agno, context, database, provider]
dominio: agentes
madurez: maduro
confianza: alta
fuentes:
  - tipo: repo
    ref: agno-agi/agno
    commit: v2.8.6
    acceso: 2026-08-12
---

> Corpus AJENO. Documentación del módulo `context\database\provider.py` de Agno 2.8.6,
> tal cual la escribieron sus autores. No es una nota propia y no está
> verificada: entra al corpus para que el golden set deje de preguntar
> solo por material que ya conoces.

Database Context Provider
=========================

A namespaced read/write surface over any SQL database. Two tools:

- `query_<id>` — natural-language reads, backed by a sub-agent bound
                 to a readonly engine.
- `update_<id>` — natural-language writes, backed by a sub-agent bound
                  to a writable engine.

Two sub-agents so the read path never sees the write engine. Callers
supply both engines and the schema the provider is scoped to.
