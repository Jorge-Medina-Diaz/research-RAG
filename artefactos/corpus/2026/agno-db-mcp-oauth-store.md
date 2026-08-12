---
tipo: lectura-paper
titulo: Shared SQLAlchemy implementation of the built-in MCP OAuth token store
fecha: 2026-08-12
temas: [agno, mcp-oauth-store]
dominio: datos
madurez: maduro
confianza: alta
fuentes:
  - tipo: repo
    ref: agno-agi/agno
    commit: v2.8.6
    acceso: 2026-08-12
---

> Corpus AJENO. Documentación del módulo `db\mcp_oauth_store.py` de Agno 2.8.6,
> tal cual la escribieron sus autores. No es una nota propia y no está
> verificada: entra al corpus para que el golden set deje de preguntar
> solo por material que ya conoces.

Shared SQLAlchemy implementation of the built-in MCP OAuth token store.

The sync SQLAlchemy backends (``PostgresDb``, ``SqliteDb``) expose the OAuth store as
``BaseDb`` methods (``*_mcp_oauth_*``); both delegate to the functions here so the store
logic -- expiry sweeps, the anti-flood caps, the atomic single-use consume, and the
IntegrityError-tolerant key insert -- lives in one place instead of being duplicated per
backend. Each function takes the backend's ``Engine`` and the already-resolved
``Table`` (the backend fetches it via ``_get_table(..., create_table_if_not_found=True)``
so the table is created by the normal schema-aware path on first use).

Secrets never reach this layer in the clear: the provider SHA-256-hashes authorization
codes and refresh tokens before calling ``store_code`` / ``store_refresh`` and looks them
up by the same hash, and it JSON-serializes payloads/scopes to text. This module only
stores and queries opaque strings.
