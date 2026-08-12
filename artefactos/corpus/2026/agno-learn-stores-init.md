---
tipo: lectura-paper
titulo: Learning Stores Storage backends for each learning type
fecha: 2026-08-12
temas: [agno, learn, stores]
dominio: agentes
madurez: maduro
confianza: alta
fuentes:
  - tipo: repo
    ref: agno-agi/agno
    commit: v2.8.6
    acceso: 2026-08-12
---

> Corpus AJENO. Documentación del módulo `learn\stores\__init__.py` de Agno 2.8.6,
> tal cual la escribieron sus autores. No es una nota propia y no está
> verificada: entra al corpus para que el golden set deje de preguntar
> solo por material que ya conoces.

Learning Stores
===============
Storage backends for each learning type.

Each store implements the LearningStore protocol and handles:
- Recall: Retrieving relevant data
- Process: Extracting and saving learnings
- Context: Building agent context strings
- Tools: Providing agent tools

Available Stores:
- UserProfileStore: Long-term user profile fields
- UserMemoryStore: Long-term user memories (unstructured)
- SessionContextStore: Current session state
- LearnedKnowledgeStore: Reusable knowledge/insights
- EntityMemoryStore: Third-party entity facts
- DecisionLogStore: Agent decision logging
