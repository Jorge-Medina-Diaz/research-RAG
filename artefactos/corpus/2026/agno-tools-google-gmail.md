---
tipo: lectura-paper
titulo: Gmail Toolkit for interacting with Gmail API
fecha: 2026-08-12
temas: [agno, tools, google, gmail]
dominio: producto
madurez: maduro
confianza: alta
fuentes:
  - tipo: repo
    ref: agno-agi/agno
    commit: v2.8.6
    acceso: 2026-08-12
---

> Corpus AJENO. Documentación del módulo `tools\google\gmail.py` de Agno 2.8.6,
> tal cual la escribieron sus autores. No es una nota propia y no está
> verificada: entra al corpus para que el golden set deje de preguntar
> solo por material que ya conoces.

Gmail Toolkit for interacting with Gmail API

Required Environment Variables:
-----------------------------
- GOOGLE_CLIENT_ID: Google OAuth client ID
- GOOGLE_CLIENT_SECRET: Google OAuth client secret
- GOOGLE_PROJECT_ID: Google Cloud project ID
- GOOGLE_REDIRECT_URI: Google OAuth redirect URI (default: http://localhost)

How to Get These Credentials:
---------------------------
1. Go to Google Cloud Console (https://console.cloud.google.com)
2. Create a new project or select an existing one
3. Enable the Gmail API:
   - Go to "APIs & Services" > "Enable APIs and Services"
   - Search for "Gmail API"
   - Click "Enable"

4. Create OAuth 2.0 credentials:
   - Go to "APIs & Services" > "Credentials"
   - Click "Create Credentials" > "OAuth client ID"
   - Go through the OAuth consent screen setup
   - Give it a name and click "Create"
   - You'll receive:
     * Client ID (GOOGLE_CLIENT_ID)
     * Client Secret (GOOGLE_CLIENT_SECRET)
   - The Project ID (GOOGLE_PROJECT_ID) is visible in the project dropdown at the top of the page

5. Add auth redirect URI:
   - Go to https://console.cloud.google.com/auth/clients and add the redirect URI as http://127.0.0.1/

6. Set up environment variables:
   Create a .envrc file in your project root with:
   ```
   export GOOGLE_CLIENT_ID=your_client_id_here
   export GOOGLE_CLIENT_SECRET=your_client_secret_here
   export GOOGLE_PROJECT_ID=your_project_id_here
   export GOOGLE_REDIRECT_URI=http://127.0.0.1/  # Default value
   ```

Note: The first time you run the application, it will open a browser window for OAuth authentication.
A token.json file will be created to store the authentication credentials for future use.

Service Account Authentication (Alternative):
---------------------------------------------
For server/bot deployments where no browser is available, use a Google service account
with domain-wide delegation instead of OAuth.

1. Create a service account in Google Cloud Console > "IAM & Admin" > "Service Accounts"
2. Download the JSON key file
3. In Google Workspace Admin Console, go to Security > API Controls > Domain-wide Delegation
4. Add the service account's client_id with the Gmail scopes your agent needs
5. Set environment variables:
   ```
   export GOOGLE_SERVICE_ACCOUNT_FILE=/path/to/service-account-key.json
   export GOOGLE_DELEGATED_USER=user@yourdomain.com
   ```

When service_account_path (or GOOGLE_SERVICE_ACCOUNT_FILE) is set, OAuth is skipped entirely.
The delegated_user specifies which mailbox the service account will access.
