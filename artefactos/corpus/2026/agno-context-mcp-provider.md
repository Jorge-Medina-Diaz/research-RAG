---
tipo: lectura-paper
titulo: MCP Context Provider
fecha: 2026-08-12
temas: [agno, context, mcp, provider]
dominio: infraestructura
madurez: maduro
confianza: alta
fuentes:
  - tipo: repo
    ref: agno-agi/agno
    commit: v2.8.6
    acceso: 2026-08-12
---

> Corpus AJENO. Documentación del módulo `context\mcp\provider.py` de Agno 2.8.6,
> tal cual la escribieron sus autores. No es una nota propia y no está
> verificada: entra al corpus para que el golden set deje de preguntar
> solo por material que ya conoces.

MCP Context Provider
====================

Wraps a single Model Context Protocol (MCP) server as a context
provider. One MCP server -> one provider -> one ``query_mcp_<slug>``
tool on the calling agent (via the sub-agent wrapper).

Why a sub-agent wrapper:

- Two MCP servers that each expose a ``search`` tool would collide if
  we flattened them onto the calling agent's tool list. The sub-agent
  namespace keeps each server's tool names isolated.
- Tool descriptions vary per server and change when the server
  updates. The sub-agent's instructions are built from
  ``list_tools()`` at connect time, so the calling agent never sees
  stale hand-written tool docs.
- A crashed server degrades gracefully: ``astatus()`` flips to
  ``ok=False`` without taking down the caller.

Lifecycle:

- ``asetup()`` connects to the server, bounded by ``timeout_seconds``.
  Safe to call multiple times. On failure it logs and clears partial
  state; the provider retries on the next call.
- ``aclose()`` releases the session on shutdown.

Callers should bracket usage with ``asetup`` / ``aclose`` (typically
from an app lifespan) so the ``mcp`` SDK's anyio cancel scopes exit
on the task that entered them.
