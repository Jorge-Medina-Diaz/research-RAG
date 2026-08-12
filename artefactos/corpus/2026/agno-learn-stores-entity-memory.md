---
tipo: lectura-paper
titulo: Entity Memory Store Storage backend for Entity Memory learning type
fecha: 2026-08-12
temas: [agno, learn, stores, entity-memory]
dominio: agentes
madurez: maduro
confianza: alta
fuentes:
  - tipo: repo
    ref: agno-agi/agno
    commit: v2.8.6
    acceso: 2026-08-12
---

> Corpus AJENO. Documentación del módulo `learn\stores\entity_memory.py` de Agno 2.8.6,
> tal cual la escribieron sus autores. No es una nota propia y no está
> verificada: entra al corpus para que el golden set deje de preguntar
> solo por material que ya conoces.

Entity Memory Store
===================
Storage backend for Entity Memory learning type.

Stores knowledge about external entities - people, companies, projects, products,
concepts, systems, and any other things the agent interacts with that aren't the
user themselves.

Think of it as:
- UserProfile = what you know about THE USER
- EntityMemory = what you know about EVERYTHING ELSE

The agent surface is four tools:
- remember_about: upsert an entity with facts, events and an optional note pointer
- link_entities: record a relationship between two entities
- search_entities: search stored entities, or list them by recency
- forget: retire a fact, or archive a whole entity

Scoping:
- entity_id: derived in the store from the entity's name (slugified)
- entity_type: category (e.g., "company", "person", "project", "product")
- namespace: sharing scope:
    - "user": Private to current user
    - "global": Shared with everyone (default)
    - "<custom>": Custom grouping (e.g., "sales_team")

Supported Modes:
- AGENTIC only. The agent records entities through tools; there is no
  extraction pass. This mirrors how session_context documents itself as
  ALWAYS-only.
