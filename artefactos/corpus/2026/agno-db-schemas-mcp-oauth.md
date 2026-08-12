---
tipo: lectura-paper
titulo: Schemas for the built-in MCP OAuth authorization server's token store
fecha: 2026-08-12
temas: [agno, schemas, mcp-oauth]
dominio: datos
madurez: maduro
confianza: alta
fuentes:
  - tipo: repo
    ref: agno-agi/agno
    commit: v2.8.6
    acceso: 2026-08-12
---

> Corpus AJENO. Documentación del módulo `db\schemas\mcp_oauth.py` de Agno 2.8.6,
> tal cual la escribieron sus autores. No es una nota propia y no está
> verificada: entra al corpus para que el golden set deje de preguntar
> solo por material que ya conoces.

Schemas for the built-in MCP OAuth authorization server's token store.

These five tables back ``AgentOSBuiltinAuth`` (``agno.os.mcp_auth_builtin``): the
OAuth authorization server the AgentOS MCP endpoint runs when a deployer opts in via
``AgentOS(mcp_auth=AgentOSBuiltinAuth(...))``. They live here -- alongside every other
agno table schema -- and are reached through the ``BaseDb`` contract (the
``*_mcp_oauth_*`` methods, implemented by the sync SQLAlchemy backends and inherited as
``NotImplementedError`` everywhere else) rather than defined inside the provider, so a
single place owns the schema and the store is created by the same schema-aware,
migration-aware path as the rest of agno.

The columns hold no replayable secrets: authorization codes and refresh tokens are
stored SHA-256-hashed (the ``*_hash`` primary keys), matching the service-account PAT
model, so a database read yields nothing that can be presented as a bearer.
