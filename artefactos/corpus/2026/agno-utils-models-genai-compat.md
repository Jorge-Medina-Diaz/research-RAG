---
tipo: lectura-paper
titulo: "Compatibility layer for google-genai <2.9.0 and >=2.9.0"
fecha: 2026-08-12
temas: [agno, utils, models, -genai-compat]
dominio: agentes
madurez: maduro
confianza: alta
fuentes:
  - tipo: repo
    ref: agno-agi/agno
    commit: v2.8.6
    acceso: 2026-08-12
---

> Corpus AJENO. Documentación del módulo `utils\models\_genai_compat.py` de Agno 2.8.6,
> tal cual la escribieron sus autores. No es una nota propia y no está
> verificada: entra al corpus para que el golden set deje de preguntar
> solo por material que ya conoces.

Compatibility layer for google-genai <2.9.0 and >=2.9.0.

The streaming delta types in `google.genai.interactions` were relocated and
renamed in 2.9.0: they moved from the `step_delta` submodule (named `Delta<X>`)
to the top-level `interactions` namespace (renamed `<X>Delta`). This module
detects the installed SDK version once and exposes a stable set of `Delta*`
aliases so consumer modules can simply do:

    from agno.utils.models._genai_compat import DeltaText, DeltaArgumentsDelta, ...

If google-genai is not installed, this module can still be imported without
error. Actual ImportError is raised only when the exported symbols are accessed.

When 2.8.0 support is dropped, delete the `else` branch and the version check.

`attr-defined` / `no-redef` are disabled at module scope: only one of the two
import branches is visible to mypy at a time (whichever matches the installed
SDK), so the names from the other branch always look undefined or redefined.
