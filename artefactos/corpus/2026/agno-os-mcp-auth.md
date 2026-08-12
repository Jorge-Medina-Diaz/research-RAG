---
tipo: lectura-paper
titulo: "OAuth on the AgentOS MCP endpoint -- the ``mcp_auth`` seam"
fecha: 2026-08-12
temas: [agno, mcp-auth]
dominio: infraestructura
madurez: maduro
confianza: alta
fuentes:
  - tipo: repo
    ref: agno-agi/agno
    commit: v2.8.6
    acceso: 2026-08-12
---

> Corpus AJENO. Documentación del módulo `os\mcp_auth.py` de Agno 2.8.6,
> tal cual la escribieron sus autores. No es una nota propia y no está
> verificada: entra al corpus para que el golden set deje de preguntar
> solo por material que ya conoces.

OAuth on the AgentOS MCP endpoint -- the ``mcp_auth`` seam.

``AgentOS(mcp_auth=<fastmcp AuthProvider>)`` hands authentication for the mounted MCP
app to the provider. fastmcp serves the provider's routes (RFC 9728 discovery and, for
an authorization-server provider, ``/authorize``, ``/token``, ``/register``, ``/revoke``)
inside the MCP sub-app -- which AgentOS mounts at root, so they resolve at the public
URLs -- and wraps the MCP path in the SDK's ``RequireAuthMiddleware``, which emits the
``401`` + ``WWW-Authenticate: Bearer resource_metadata="..."`` challenge OAuth clients
(claude.ai, ChatGPT) use for discovery.

agno adds two things on top of the provider:

- **Bearer coexistence**: the provider is composed via fastmcp's ``MultiAuth`` with the
  service-account verifier and, when the deployment has a JWT config, a JWT verifier --
  so existing ``agno_pat_`` bearers (Claude Code, Cursor, the ``agno connect``
  claude-desktop bridge) and agno-JWT bearers keep working on an OAuth-enabled ``/mcp``.
- **The identity bridge**: fastmcp attaches the verified token to the ASGI scope
  (``scope["user"]``), while the MCP tools read ``request.state``. The bridge
  middleware maps one onto the other with the full contract the tool gates need
  (``user_id``, ``scopes``, ``authorization_enabled``, ``admin_scope``). It must run
  INSIDE fastmcp's authentication middleware, so it is passed via
  ``mcp.http_app(middleware=[...])`` -- never ``add_middleware``, which prepends
  outside authentication where no verified token exists yet.
