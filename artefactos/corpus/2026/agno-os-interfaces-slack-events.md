---
tipo: lectura-paper
titulo: Slack Streaming Event Handlers
fecha: 2026-08-12
temas: [agno, interfaces, slack, events]
dominio: infraestructura
madurez: maduro
confianza: alta
fuentes:
  - tipo: repo
    ref: agno-agi/agno
    commit: v2.8.6
    acceso: 2026-08-12
---

> Corpus AJENO. Documentación del módulo `os\interfaces\slack\events.py` de Agno 2.8.6,
> tal cual la escribieron sus autores. No es una nota propia y no está
> verificada: entra al corpus para que el golden set deje de preguntar
> solo por material que ya conoces.

Slack Streaming Event Handlers
==============================

Processes streaming events from agents, teams, and workflows,
translating them into Slack task cards and buffered content.

Key concepts:
- Events are normalized (Team prefix stripped) for unified handling
- Workflow mode suppresses inner agent events to reduce noise
- Task cards track progress; content is buffered for streaming
- Factory pattern generates simple paired handlers (Started/Completed)
