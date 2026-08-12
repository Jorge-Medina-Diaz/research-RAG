---
tipo: lectura-paper
titulo: Google Drive tools for listing, searching, reading, uploading, and downloading files
fecha: 2026-08-12
temas: [agno, tools, google, drive]
dominio: producto
madurez: maduro
confianza: alta
fuentes:
  - tipo: repo
    ref: agno-agi/agno
    commit: v2.8.6
    acceso: 2026-08-12
---

> Corpus AJENO. Documentación del módulo `tools\google\drive.py` de Agno 2.8.6,
> tal cual la escribieron sus autores. No es una nota propia y no está
> verificada: entra al corpus para que el golden set deje de preguntar
> solo por material que ya conoces.

Google Drive tools for listing, searching, reading, uploading, and downloading files.

Required Setup:
--------------
**Option A — OAuth (interactive, for local development):**
1. Go to Google Cloud Console -> APIs & Services -> Enable Google Drive API
2. Create OAuth 2.0 credentials (Desktop app)
3. Set environment variables:
   - GOOGLE_CLIENT_ID
   - GOOGLE_CLIENT_SECRET
   - GOOGLE_PROJECT_ID
4. First run opens a browser for consent; token is cached in token.json

**Option B — Service Account (headless, for servers):**
1. Create a service account in Google Cloud Console
2. Download the JSON key file
3. Set GOOGLE_SERVICE_ACCOUNT_FILE to the path of the key file
4. Optionally set GOOGLE_DELEGATED_USER to impersonate a user via domain-wide delegation

Install dependencies: `pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib`

**Shared Drive Support:**

By default, searches only personal Drive (corpora="user"). To access Shared Drives:

    GoogleDriveTools(
        corpora="allDrives",           # Search all drives
        supports_all_drives=True,      # Enable Shared Drive API features
        include_items_from_all_drives=True,  # Include Shared Drive items in results
    )

Corpora options: "user" (default), "domain", "drive" (requires drive_id), "allDrives".
See: https://developers.google.com/drive/api/guides/enable-shareddrives
