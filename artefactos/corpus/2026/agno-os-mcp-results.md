---
tipo: lectura-paper
titulo: Serialization of run outputs into MCP tool results
fecha: 2026-08-12
temas: [agno, mcp-results]
dominio: infraestructura
madurez: maduro
confianza: alta
fuentes:
  - tipo: repo
    ref: agno-agi/agno
    commit: v2.8.6
    acceso: 2026-08-12
---

> Corpus AJENO. Documentación del módulo `os\mcp_results.py` de Agno 2.8.6,
> tal cual la escribieron sus autores. No es una nota propia y no está
> verificada: entra al corpus para que el golden set deje de preguntar
> solo por material que ya conoces.

Serialization of run outputs into MCP tool results.

The run tools on the AgentOS MCP server return results sized for the consuming
LLM: MCP tool results are injected directly into the frontend model's context
window, so the default ("trimmed") mode carries the answer and a minimal set of
identifiers rather than the full run transcript. Raw dataclass serialization is
never used -- it dumps internal message history (including the system prompt)
over the wire and raises on binary media.
