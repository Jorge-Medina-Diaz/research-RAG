---
tipo: lectura-paper
titulo: Helpers for per-user data isolation at the route layer
fecha: 2026-08-12
temas: [agno, middleware, user-scope, asincronia]
dominio: infraestructura
madurez: maduro
confianza: alta
fuentes:
  - tipo: repo
    ref: agno-agi/agno
    commit: v2.8.6
    acceso: 2026-08-12
---

> Corpus AJENO. Documentación del módulo `os\middleware\user_scope.py` de Agno 2.8.6,
> tal cual la escribieron sus autores. No es una nota propia y no está
> verificada: entra al corpus para que el golden set deje de preguntar
> solo por material que ya conoces.

Helpers for per-user data isolation at the route layer.

This module exposes a small set of helpers that routers call explicitly to
honour the opt-in ``AuthorizationConfig(user_isolation=True)`` contract:

    from agno.os.middleware.user_scope import (
        get_scoped_user_id,    # who, if anyone, are we scoping to?
        resolve_db_and_scope,  # fetch DB + the user_id to thread on reads
        enforce_owner_on_entity,  # coerce/validate user_id on writes
    )

The framework no longer wraps the DB in an adapter. Each router endpoint
threads ``user_id`` through the underlying ``BaseDb`` / ``AsyncBaseDb`` call
itself. The trade is fewer moving parts and clearer dispatch, at the cost
of a per-endpoint convention: every user-scoped read passes ``user_id``,
every write goes through ``enforce_owner_on_entity`` before persisting.

.. important::

   **Adding a new router endpoint that handles user-owned data?**

   You MUST call one of the scoping helpers (``get_scoped_user_id``,
   ``resolve_db_and_scope``, or ``apply_scope_to_kwargs``) and thread the
   resulting ``user_id`` into every DB read/write. Omitting this will
   silently bypass user isolation with no runtime error.

   Pattern for reads::

       scoped_user_id = get_scoped_user_id(request)
       db.get_sessions(user_id=scoped_user_id, ...)

   Pattern for writes::

       enforce_owner_on_entity(entity, request)
       db.upsert_session(entity)

Admin users (with the configured ``admin_scope``) and callers running with
isolation disabled get ``None`` from ``get_scoped_user_id`` — both helpers
become no-ops in that case, preserving the legacy unscoped behaviour.
