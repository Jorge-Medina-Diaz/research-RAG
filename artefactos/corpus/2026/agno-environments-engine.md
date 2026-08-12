---
tipo: lectura-paper
titulo: "The private rollout engine: run a subject K times per input, isolated, and collect results"
fecha: 2026-08-12
temas: [agno, environments, -engine, asincronia]
dominio: evaluacion
madurez: maduro
confianza: alta
fuentes:
  - tipo: repo
    ref: agno-agi/agno
    commit: v2.8.6
    acceso: 2026-08-12
---

> Corpus AJENO. Documentación del módulo `environments\_engine.py` de Agno 2.8.6,
> tal cual la escribieron sus autores. No es una nota propia y no está
> verificada: entra al corpus para que el golden set deje de preguntar
> solo por material que ya conoces.

The private rollout engine: run a subject K times per input, isolated, and collect results.

Private means async-only (the sync door is `run_rollouts`) and this interface may change
without deprecation. The result types (`AttemptResult`, `StopReason`) are public,
re-exported from `agno.environments`, because they appear on every `TaskResult`.

There is no single-run door: `Agent.run` already is one, and scoring one run is
`scorer.score(agent.run(x), expected)`.
