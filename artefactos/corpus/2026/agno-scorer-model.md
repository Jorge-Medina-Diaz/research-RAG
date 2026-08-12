---
tipo: lectura-paper
titulo: Model identity payload -- private; shared with agno.environments
fecha: 2026-08-12
temas: [agno, scorer, -model]
dominio: evaluacion
madurez: maduro
confianza: alta
fuentes:
  - tipo: repo
    ref: agno-agi/agno
    commit: v2.8.6
    acceso: 2026-08-12
---

> Corpus AJENO. Documentación del módulo `scorer\_model.py` de Agno 2.8.6,
> tal cual la escribieron sus autores. No es una nota propia y no está
> verificada: entra al corpus para que el golden set deje de preguntar
> solo por material que ya conoces.

Model identity payload -- private; shared with agno.environments.

The judge is part of the scoring rule, and the policy fingerprint identifies the
model under test: both need the same answer to "which model is this?", so the payload
is built once here. agno.environments imports it -- the allowed direction; scorer
imports neither eval nor environments.

The payload enumerates the model's public attributes and excludes what provably is
not policy: ~50 provider classes each carry their own request-shaping fields
(verbosity, logit_bias, reasoning, ...), an open set no fixed allowlist can track.
The exclusion groups below
are pinned by a drift test over the shipped OpenAI classes, so a new upstream field
must be classified before it ships.
