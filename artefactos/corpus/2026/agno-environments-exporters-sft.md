---
tipo: lectura-paper
titulo: "Conversational-SFT JSONL export: one object per line, {'messages': [{'role', 'content'}]}"
fecha: 2026-08-12
temas: [agno, environments, exporters, sft]
dominio: evaluacion
madurez: maduro
confianza: alta
fuentes:
  - tipo: repo
    ref: agno-agi/agno
    commit: v2.8.6
    acceso: 2026-08-12
---

> Corpus AJENO. Documentación del módulo `environments\exporters\sft.py` de Agno 2.8.6,
> tal cual la escribieron sus autores. No es una nota propia y no está
> verificada: entra al corpus para que el golden set deje de preguntar
> solo por material que ya conoces.

Conversational-SFT JSONL export: one object per line, {"messages": [{"role", "content"}]}.

Tinker, Together, Fireworks and OpenAI all accept that core. They diverge on exactly
two axes -- tool representation and loss weighting -- and this exporter emits NEITHER,
so the file is portable by omission rather than by translation. Do not "helpfully" add
a `tools`, `weight`, or `trainable` key: the strictest checked consumer rejects the
entire file on any unknown key (strict set equality; it does not drop the key), so one
extra key breaks every consumer at once. Scores and fingerprints ride in the
`<path>.meta.json` sidecar, because provenance has nowhere else to live.
