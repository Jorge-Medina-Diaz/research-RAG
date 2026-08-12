---
tipo: lectura-paper
titulo: LearningMachine Configuration Enums and configuration classes for the unified learning system
fecha: 2026-08-12
temas: [agno, learn, config]
dominio: agentes
madurez: maduro
confianza: alta
fuentes:
  - tipo: repo
    ref: agno-agi/agno
    commit: v2.8.6
    acceso: 2026-08-12
---

> Corpus AJENO. Documentación del módulo `learn\config.py` de Agno 2.8.6,
> tal cual la escribieron sus autores. No es una nota propia y no está
> verificada: entra al corpus para que el golden set deje de preguntar
> solo por material que ya conoces.

LearningMachine Configuration
=============================
Enums and configuration classes for the unified learning system.

Uses dataclasses instead of Pydantic BaseModels to avoid runtime
overhead and validation errors that could break agents mid-run.

Configurations:
- LearningMode: How learning is extracted (ALWAYS, AGENTIC, PROPOSE, HITL)
- UserProfileConfig: Config for user profile learning
- MemoriesConfig: Config for memories learning
- SessionContextConfig: Config for session context learning
- LearnedKnowledgeConfig: Config for learned knowledge
- EntityMemoryConfig: Config for entity memory

Custom `schema` classes serialize by import path; define them in an
importable module, not `__main__`, or they will not survive a
to_dict/from_dict round-trip across processes.
