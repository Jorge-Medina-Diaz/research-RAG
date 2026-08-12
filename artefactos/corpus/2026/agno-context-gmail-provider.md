---
tipo: lectura-paper
titulo: Gmail Context Provider
fecha: 2026-08-12
temas: [agno, context, gmail, provider]
dominio: agentes
madurez: maduro
confianza: alta
fuentes:
  - tipo: repo
    ref: agno-agi/agno
    commit: v2.8.6
    acceso: 2026-08-12
---

> Corpus AJENO. Documentación del módulo `context\gmail\provider.py` de Agno 2.8.6,
> tal cual la escribieron sus autores. No es una nota propia y no está
> verificada: entra al corpus para que el golden set deje de preguntar
> solo por material que ya conoces.

Gmail Context Provider
======================

Read/write Gmail access via two tools:

- ``query_<id>`` — natural-language email reads (search, threads,
  message details, labels).
- ``update_<id>`` — natural-language writes (drafts, send, reply,
  label management).

Separate sub-agents keep each scope narrow. Reads get search and
message tools; writes get compose plus lookup tools.

**Auth methods:**

1. Service Account + domain-wide delegation (headless):
   - Set ``GOOGLE_SERVICE_ACCOUNT_FILE`` and ``GOOGLE_DELEGATED_USER``
   - Gmail requires ``delegated_user`` because service accounts have no inbox

2. OAuth (interactive, for personal Gmail):
   - Set ``GOOGLE_CLIENT_ID``, ``GOOGLE_CLIENT_SECRET``, ``GOOGLE_PROJECT_ID``
   - Opens browser on first use, caches token to ``gmail_token.json``
