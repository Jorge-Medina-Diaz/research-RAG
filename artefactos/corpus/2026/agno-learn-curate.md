---
tipo: lectura-paper
titulo: Curator Memory maintenance for LearningMachine
fecha: 2026-08-12
temas: [agno, learn, curate]
dominio: agentes
madurez: maduro
confianza: alta
fuentes:
  - tipo: repo
    ref: agno-agi/agno
    commit: v2.8.6
    acceso: 2026-08-12
---

> Corpus AJENO. Documentación del módulo `learn\curate.py` de Agno 2.8.6,
> tal cual la escribieron sus autores. No es una nota propia y no está
> verificada: entra al corpus para que el golden set deje de preguntar
> solo por material que ya conoces.

Curator
=======
Memory maintenance for LearningMachine.

Keeps memories tidy through:
- Pruning: Remove old memories
- Deduplication: Remove exact/near-exact duplicates

Usage:
    >>> learning = LearningMachine(db=db, model=model, user_profile=True)
    >>>
    >>> # Remove memories older than 90 days, keep max 100
    >>> removed = learning.curator.prune(user_id="alice", max_age_days=90, max_count=100)
    >>>
    >>> # Remove duplicate memories
    >>> deduped = learning.curator.deduplicate(user_id="alice")
