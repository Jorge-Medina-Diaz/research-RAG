---
tipo: lectura-paper
titulo: Search filter expressions for filtering knowledge base documents and search results
fecha: 2026-08-12
temas: [agno, filters]
dominio: otro
madurez: maduro
confianza: alta
fuentes:
  - tipo: repo
    ref: agno-agi/agno
    commit: v2.8.6
    acceso: 2026-08-12
---

> Corpus AJENO. Documentación del módulo `filters.py` de Agno 2.8.6,
> tal cual la escribieron sus autores. No es una nota propia y no está
> verificada: entra al corpus para que el golden set deje de preguntar
> solo por material que ya conoces.

Search filter expressions for filtering knowledge base documents and search results.

This module provides a set of filter operators for constructing complex search queries
that can be applied to knowledge bases, vector databases, and other searchable content.

Filter Types:
    - Comparison: EQ (equals), NEQ (not equals), GT (greater than), GTE (greater than or equal),
      LT (less than), LTE (less than or equal)
    - Inclusion: IN (value in list)
    - String: CONTAINS (substring match), STARTSWITH (prefix match)
    - Logical: AND, OR, NOT

Example:
    >>> from agno.filters import EQ, GT, IN, AND, OR, NOT
    >>>
    >>> # Simple equality filter
    >>> filter = EQ("category", "technology")
    >>>
    >>> # Complex filter with multiple conditions
    >>> filter = AND(
    ...     EQ("status", "published"),
    ...     GT("views", 1000),
    ...     IN("category", ["tech", "science"])
    ... )
    >>>
    >>> # Using OR logic
    >>> filter = OR(EQ("priority", "high"), EQ("urgent", True))
    >>>
    >>> # Negating conditions
    >>> filter = NOT(EQ("status", "archived"))
    >>>
    >>> # Complex nested logic
    >>> filter = OR(
    ...     AND(EQ("type", "article"), GT("word_count", 500)),
    ...     AND(EQ("type", "tutorial"), NOT(EQ("difficulty", "beginner")))
    ... )
