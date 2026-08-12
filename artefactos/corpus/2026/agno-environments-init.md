---
tipo: lectura-paper
titulo: "agno.environments: run an agent many times against a set of tasks, score every attempt, and do something useful with the result"
fecha: 2026-08-12
temas: [agno, environments]
dominio: evaluacion
madurez: maduro
confianza: alta
fuentes:
  - tipo: repo
    ref: agno-agi/agno
    commit: v2.8.6
    acceso: 2026-08-12
---

> Corpus AJENO. Documentación del módulo `environments\__init__.py` de Agno 2.8.6,
> tal cual la escribieron sus autores. No es una nota propia y no está
> verificada: entra al corpus para que el golden set deje de preguntar
> solo por material que ya conoces.

agno.environments: run an agent many times against a set of tasks, score every
attempt, and do something useful with the result.

Two questions, in this order: does my agent actually work (run each task K times and
count -- a real pass rate, not one sampled run), and can I train on the runs that
worked (the passing attempts are, with no further labelling, an SFT dataset).

The fingerprint errors are re-exported from agno.scorer so callers can catch them
without importing scorer.
