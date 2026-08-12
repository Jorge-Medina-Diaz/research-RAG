---
tipo: lectura-paper
titulo: "The rollout grid and the per-attempt report. Private: `summary()` is the programmatic contract, none of this is"
fecha: 2026-08-12
temas: [agno, environments, -render]
dominio: evaluacion
madurez: maduro
confianza: alta
fuentes:
  - tipo: repo
    ref: agno-agi/agno
    commit: v2.8.6
    acceso: 2026-08-12
---

> Corpus AJENO. Documentación del módulo `environments\_render.py` de Agno 2.8.6,
> tal cual la escribieron sus autores. No es una nota propia y no está
> verificada: entra al corpus para que el golden set deje de preguntar
> solo por material que ya conoces.

The rollout grid and the per-attempt report. Private: `summary()` is the
programmatic contract, none of this is.

K attempts is K glyphs: a full block for a pass, a light shade for a scored fail, a
triangle for an unscored attempt. Rendered live through rich during a TTY run, and
statically by `EnvironmentRunResult.__str__`. `build_report` is the layer underneath the
glyphs: one text block per attempt -- verdict, score reason, tool executions, the
answer -- so a red glyph is explainable without walking the result objects by hand.
