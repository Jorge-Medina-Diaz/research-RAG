---
tipo: lectura-paper
titulo: The vendored Tinker acceptance check -- a private test oracle, not public API
fecha: 2026-08-12
temas: [agno, environments, exporters, -validate]
dominio: evaluacion
madurez: maduro
confianza: alta
fuentes:
  - tipo: repo
    ref: agno-agi/agno
    commit: v2.8.6
    acceso: 2026-08-12
---

> Corpus AJENO. Documentación del módulo `environments\exporters\_validate.py` de Agno 2.8.6,
> tal cual la escribieron sus autores. No es una nota propia y no está
> verificada: entra al corpus para que el golden set deje de preguntar
> solo por material que ya conoces.

The vendored Tinker acceptance check -- a private test oracle, not public API.

Mirrors rl-tutor's `_parse_conversations` / `_dataset_size_error` (tutor/
tinker_tools.py): exactly {"messages"} at top level and exactly {"role", "content"}
per message -- strict set equality, an unknown key REJECTS THE FILE, it is not
dropped; roles {system, user, assistant}; content a non-blank string; at least one
user message; last message assistant; 320 conversations; 1 MiB utf-8.
