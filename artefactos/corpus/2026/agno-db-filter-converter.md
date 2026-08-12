---
tipo: lectura-paper
titulo: "Generic FilterExpr -> database query converter for named table columns"
fecha: 2026-08-12
temas: [agno, filter-converter]
dominio: datos
madurez: maduro
confianza: alta
fuentes:
  - tipo: repo
    ref: agno-agi/agno
    commit: v2.8.6
    acceso: 2026-08-12
---

> Corpus AJENO. Documentación del módulo `db\filter_converter.py` de Agno 2.8.6,
> tal cual la escribieron sus autores. No es una nota propia y no está
> verificada: entra al corpus para que el golden set deje de preguntar
> solo por material que ya conoces.

Generic FilterExpr -> database query converter for named table columns.

Converts serialized FilterExpr dictionaries (from agno.filters) to database-native
predicates that can be applied to any table with named columns.

This is distinct from PgVector's _dsl_to_sqlalchemy which operates on JSONB metadata
columns. This converter operates on direct table columns (table.c.column_name).

Supported backends:
    - SQLAlchemy (SQLite, PostgreSQL, MySQL, SingleStore)

Usage:
    >>> from agno.db.filter_converter import filter_expr_to_sqlalchemy, TRACE_COLUMNS
    >>>
    >>> # Convert a filter dict to a SQLAlchemy WHERE clause
    >>> filter_dict = {"op": "AND", "conditions": [
    ...     {"op": "EQ", "key": "status", "value": "OK"},
    ...     {"op": "CONTAINS", "key": "user_id", "value": "admin"}
    ... ]}
    >>> where_clause = filter_expr_to_sqlalchemy(filter_dict, table, TRACE_COLUMNS)
    >>> stmt = select(table).where(where_clause)
