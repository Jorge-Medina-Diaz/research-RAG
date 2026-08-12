---
tipo: lectura-paper
titulo: LearningMachine Schemas Dataclasses for each learning type
fecha: 2026-08-12
temas: [agno, learn, schemas]
dominio: agentes
madurez: maduro
confianza: alta
fuentes:
  - tipo: repo
    ref: agno-agi/agno
    commit: v2.8.6
    acceso: 2026-08-12
---

> Corpus AJENO. Documentación del módulo `learn\schemas.py` de Agno 2.8.6,
> tal cual la escribieron sus autores. No es una nota propia y no está
> verificada: entra al corpus para que el golden set deje de preguntar
> solo por material que ya conoces.

LearningMachine Schemas
=======================
Dataclasses for each learning type.

Uses pure dataclasses to avoid runtime overhead.
All parsing is done via from_dict() which never raises.

Classes are designed to be extended - from_dict() and to_dict()
automatically handle subclass fields via dataclasses.fields().

Field Descriptions
When extending schemas, use field metadata to provide descriptions
that will be shown to the LLM:

    @dataclass
    class MyUserProfile(UserProfile):
        company: Optional[str] = field(
            default=None,
            metadata={"description": "Where they work"}
        )

The LLM will see this description when deciding how to update fields.

Schemas:
- UserProfile: Long-term user memory
- SessionContext: Current session state
- LearnedKnowledge: Reusable knowledge/insights
- EntityMemory: Third-party entity facts
- DecisionLog: Decision logs
