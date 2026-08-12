---
tipo: lectura-paper
titulo: Decision Log Store Storage backend for Decision Log learning type
fecha: 2026-08-12
temas: [agno, learn, stores, decision-log]
dominio: agentes
madurez: maduro
confianza: alta
fuentes:
  - tipo: repo
    ref: agno-agi/agno
    commit: v2.8.6
    acceso: 2026-08-12
---

> Corpus AJENO. Documentación del módulo `learn\stores\decision_log.py` de Agno 2.8.6,
> tal cual la escribieron sus autores. No es una nota propia y no está
> verificada: entra al corpus para que el golden set deje de preguntar
> solo por material que ya conoces.

Decision Log Store
==================
Storage backend for Decision Log learning type.

Records decisions made by agents with reasoning, context, and outcomes.
Useful for auditing, debugging, and learning from past decisions.

Key Features:
- Log decisions with reasoning and context
- Record outcomes for feedback loops
- Search past decisions by type, time range, or content
- Agent tools for explicit decision logging

Scope:
- Decisions are stored per agent/session
- Can be queried by agent_id, session_id, or time range

Supported Modes:
- AGENTIC: the agent logs decisions via tools.
