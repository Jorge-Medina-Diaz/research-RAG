---
tipo: lectura-paper
titulo: Google Calendar Context Provider
fecha: 2026-08-12
temas: [agno, context, calendar, provider]
dominio: agentes
madurez: maduro
confianza: alta
fuentes:
  - tipo: repo
    ref: agno-agi/agno
    commit: v2.8.6
    acceso: 2026-08-12
---

> Corpus AJENO. Documentación del módulo `context\calendar\provider.py` de Agno 2.8.6,
> tal cual la escribieron sus autores. No es una nota propia y no está
> verificada: entra al corpus para que el golden set deje de preguntar
> solo por material que ya conoces.

Google Calendar Context Provider
================================

Read/write Calendar access via two tools:

- ``query_<id>`` — natural-language calendar reads (list events,
  check availability, find free slots).
- ``update_<id>`` — natural-language writes (create, update, delete
  events).

Separate sub-agents keep each scope narrow. Reads get list/search
tools; writes get CRUD plus lookup tools.

**Auth methods:**

1. Service Account + domain-wide delegation (headless):
   - Set ``GOOGLE_SERVICE_ACCOUNT_FILE`` and optionally ``GOOGLE_DELEGATED_USER``
   - Without ``delegated_user``, operates on the service account's own calendar

2. OAuth (interactive, for personal Calendar):
   - Set ``GOOGLE_CLIENT_ID``, ``GOOGLE_CLIENT_SECRET``, ``GOOGLE_PROJECT_ID``
   - Opens browser on first use, caches token to ``calendar_token.json``
