---
tipo: lectura-paper
titulo: Google Drive Context Provider
fecha: 2026-08-12
temas: [agno, context, gdrive, provider]
dominio: agentes
madurez: maduro
confianza: alta
fuentes:
  - tipo: repo
    ref: agno-agi/agno
    commit: v2.8.6
    acceso: 2026-08-12
---

> Corpus AJENO. Documentación del módulo `context\gdrive\provider.py` de Agno 2.8.6,
> tal cual la escribieron sus autores. No es una nota propia y no está
> verificada: entra al corpus para que el golden set deje de preguntar
> solo por material que ya conoces.

Google Drive Context Provider
=============================

Read-only Google Drive access via a single tool:

- ``query_<id>`` — natural-language file reads (list, search, read
  file contents).

A sub-agent handles Drive query syntax and file navigation. Read-only
by default; uploads/downloads are disabled.

**Auth methods:**

1. Service Account (headless):
   - Set ``GOOGLE_SERVICE_ACCOUNT_FILE`` or pass ``service_account_path``
   - Share folders with the service account email

2. OAuth (interactive, for personal Drive):
   - Set ``GOOGLE_CLIENT_ID``, ``GOOGLE_CLIENT_SECRET``, ``GOOGLE_PROJECT_ID``
   - Or pass ``credentials_path`` / ``token_path`` directly
   - Opens browser on first use, caches token to ``gdrive_token.json``

**Search scope (Shared Drive support):**

By default uses ``corpora="allDrives"`` so service accounts can see files
inside shared folders and Shared Drives. Customize with:

- ``corpora="user"`` — personal Drive only (My Drive + Shared with me)
- ``corpora="domain"`` — all files shared to user's domain
- ``corpora="drive"`` + ``drive_id="..."`` — single Shared Drive
- ``corpora="allDrives"`` — everything (default)

When using non-"user" corpora, set ``supports_all_drives=True`` and
``include_items_from_all_drives=True`` (both default to True).
