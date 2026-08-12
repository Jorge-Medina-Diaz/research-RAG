---
tipo: lectura-paper
titulo: Managers for AgentOS
fecha: 2026-08-12
temas: [agno, managers]
dominio: infraestructura
madurez: maduro
confianza: alta
fuentes:
  - tipo: repo
    ref: agno-agi/agno
    commit: v2.8.6
    acceso: 2026-08-12
---

> Corpus AJENO. Documentación del módulo `os\managers.py` de Agno 2.8.6,
> tal cual la escribieron sus autores. No es una nota propia y no está
> verificada: entra al corpus para que el golden set deje de preguntar
> solo por material que ya conoces.

Managers for AgentOS.

This module provides various manager classes for AgentOS:
- WebSocketManager: WebSocket connection management for real-time streaming
- EventsBuffer: Event buffering for agent/team/workflow reconnection support
- WebSocketHandler: Handler for sending events over WebSocket connections
- SSESubscriberManager: Subscriber management for SSE-based reconnection

These managers are used by agents, teams, and workflows for background WebSocket execution.
