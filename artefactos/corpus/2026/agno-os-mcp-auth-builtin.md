---
tipo: lectura-paper
titulo: The Built-in Authorization Server for the AgentOS MCP endpoint (Tier 1 of mcp_auth)
fecha: 2026-08-12
temas: [agno, mcp-auth-builtin]
dominio: infraestructura
madurez: maduro
confianza: alta
fuentes:
  - tipo: repo
    ref: agno-agi/agno
    commit: v2.8.6
    acceso: 2026-08-12
---

> Corpus AJENO. Documentación del módulo `os\mcp_auth_builtin.py` de Agno 2.8.6,
> tal cual la escribieron sus autores. No es una nota propia y no está
> verificada: entra al corpus para que el golden set deje de preguntar
> solo por material que ya conoces.

The Built-in Authorization Server for the AgentOS MCP endpoint (Tier 1 of mcp_auth).

``AgentOSBuiltinAuth`` makes a self-deployed AgentOS its own OAuth 2.1 authorization
server, so claude.ai / ChatGPT / Claude Code connect by pasting the ``/mcp`` URL with
zero external accounts -- and the endpoint is never open: every authorization requires
the deployer's connect secret on a login+consent page, over HTTPS.

What the SDK/fastmcp provide vs what lives here:

- The protocol layer is SDK-provided through ``OAuthProvider``: the HTTP endpoints
  (``/authorize``, ``/token``, ``/register``, ``/revoke``, discovery metadata), PKCE
  S256 enforcement, redirect-URI exact-match, and MCP-compliant error codes. Signed
  JWT access/refresh tokens come from fastmcp's ``JWTIssuer`` (HS256) -- verification
  is stateless, so any replica sharing the signing key can verify without a DB hit.
- This module implements the OAuthProvider callbacks against the AgentOS database
  (clients / authorization codes / refresh-token / signing-key state), the login+consent
  page (the single deployer-secret gate -- fastmcp has no login building block), and the
  server-decided scope grant. The persistence itself lives on the db behind the
  ``BaseDb.*_mcp_oauth_*`` contract (schemas in ``agno.db.schemas.mcp_oauth``, shared SQL
  in ``agno.db.mcp_oauth_store``, implemented by the sync SQLAlchemy backends), so the
  namespaced tables are created on first use by the same schema-aware path as every other
  agno table -- this module holds only OAuth protocol logic, not DDL.

Security properties, deliberate and load-bearing:

- **Public clients only.** Connector clients (claude.ai, ChatGPT, Claude Code,
  mcp-remote) register as public clients and prove possession via PKCE. DCR normalizes
  an omitted client-auth method to ``none`` and rejects an explicit confidential method,
  so no client secret is ever minted or stored.
- **Hash-at-rest.** Authorization codes and refresh tokens are stored SHA-256-hashed
  (matching the service-account PAT model); a database read yields nothing replayable.
- **Server-decided scopes.** The grant is a fixed, deployer-configured scope set,
  stamped onto the auth code at mint time -- client-requested DCR/authorize scopes are
  overwritten, not merely validated, so they can never expand it.
- **Single-use, short-lived codes; refresh rotation on every use.** Code exchange and
  refresh rotation are atomic DELETE-then-act, so a replayed code/refresh token fails
  on every replica.
- **The consent page** is served over a secure origin -- the SDK's ``validate_issuer_url``
  rejects a non-HTTPS, non-localhost ``base_url`` at construction, so a plaintext deploy
  cannot be stood up. It renders only for a valid pending authorization transaction,
  compares the secret in constant time, double-submits a CSRF cookie (marked ``Secure``
  on an HTTPS deployment), denies framing, and rate-limits failures per-IP and globally
  (verify-first, so a wrong-secret flood never blocks a correct login).
- **Revocation levers:** rotating the signing key invalidates every token it signed --
  access *and* refresh (both are JWTs under the same key) -- forcing re-consent; deleting
  a refresh-token row stops renewal for that client. Rotating the connect secret gates
  future logins only -- it revokes nothing already issued.
- **Refresh-token reuse detection:** refresh tokens rotate on every use and each carries a
  ``family_id`` shared across its rotation chain. Presenting a token that verifies but has
  no live row (i.e. one already rotated away) is treated as reuse and revokes the whole
  family (OAuth 2.1 / RFC 9700), so a stolen chain and the legitimate client both lose
  access and must re-consent. This bounds silent refresh-token theft without the blunt
  key-rotation kill switch; a stolen access token still lives out its short TTL.
- **Signing key:** env-primary (``AGENTOS_MCP_SIGNING_KEY``). Set it in production so the
  token trust root is env-managed; when unset, a key is generated and persisted in the
  same database (survives redeploy, shared across replicas) -- convenient, but then a
  database read yields the signing material. Keys support a rotation overlap: the newest
  signs, any active key verifies.
