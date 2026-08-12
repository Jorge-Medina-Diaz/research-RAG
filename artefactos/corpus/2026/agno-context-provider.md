---
tipo: lectura-paper
titulo: Context Providers
fecha: 2026-08-12
temas: [agno, context, provider]
dominio: agentes
madurez: maduro
confianza: alta
fuentes:
  - tipo: repo
    ref: agno-agi/agno
    commit: v2.8.6
    acceso: 2026-08-12
---

> Corpus AJENO. Documentación del módulo `context\provider.py` de Agno 2.8.6,
> tal cual la escribieron sus autores. No es una nota propia y no está
> verificada: entra al corpus para que el golden set deje de preguntar
> solo por material que ya conoces.

Context Providers
=================

A `ContextProvider` exposes a source of information — a folder of files,
the web, a database, an MCP server — to an agent. Subclasses implement:

- `query(question)` / `aquery(question)` — natural-language access; returns an `Answer`
- `status()` / `astatus()` — is the source reachable?

Providers that support writes also override `aupdate()` (and optionally
`update()`); the default raises `NotImplementedError` so read-only
providers inherit a clean failure that `_update_tool()` surfaces as "<name> is read-only".

`mode` controls how the provider surfaces itself to the calling agent:

- `ContextMode.default` — the provider's recommended exposure; each
  subclass decides what this means
- `ContextMode.agent` — wraps the provider behind a sub-agent; the
  calling agent gets a single `query_<id>` tool
- `ContextMode.tools` — exposes the provider's underlying tools directly;
  the calling agent orchestrates them itself

`model` swaps the model used by the internal sub-agent. For full
customization, subclass and override `_build_agent()`.

`instructions()` returns mode-aware usage guidance. The wiring layer
chooses how to surface it: inline in the system prompt, or via an
on-demand `learn_context(id)` meta-tool.
