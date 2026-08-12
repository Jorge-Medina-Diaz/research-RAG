---
tipo: lectura-paper
titulo: "Eval suite runner: declare `Case`s, run them with `run_cases`/`arun_cases`, ship a CLI with `cli`"
fecha: 2026-08-12
temas: [agno, eval, suite, asincronia]
dominio: evaluacion
madurez: maduro
confianza: alta
fuentes:
  - tipo: repo
    ref: agno-agi/agno
    commit: v2.8.6
    acceso: 2026-08-12
---

> Corpus AJENO. Documentación del módulo `eval\suite.py` de Agno 2.8.6,
> tal cual la escribieron sus autores. No es una nota propia y no está
> verificada: entra al corpus para que el golden set deje de preguntar
> solo por material que ya conoces.

Eval suite runner: declare `Case`s, run them with `run_cases`/`arun_cases`, ship a CLI with `cli`.

A `Case` is one input to one agent or team plus optional checks (`AgentAsJudgeEval` via
`criteria`, `ReliabilityEval` via `expected_tool_calls`). The runner executes the
selected cases sequentially on a single event loop and returns a `SuiteResult`
whose `to_dict()` payload is a stable contract for CI consumers.

The runner performs no console I/O: presentation flows through the
`on_case_start` / `on_run_event` / `on_case_end` hooks. `cli()` (and its async
twin `acli()`) is a pure consumer of that public API.
