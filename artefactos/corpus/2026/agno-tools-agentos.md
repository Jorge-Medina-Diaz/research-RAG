---
tipo: lectura-paper
titulo: AgentOSTools -- give agents a read-only ops view of the AgentOS they run on
fecha: 2026-08-12
temas: [agno, tools, agentos, asincronia]
dominio: agentes
madurez: maduro
confianza: alta
fuentes:
  - tipo: repo
    ref: agno-agi/agno
    commit: v2.8.6
    acceso: 2026-08-12
---

> Corpus AJENO. Documentación del módulo `tools\agentos.py` de Agno 2.8.6,
> tal cual la escribieron sus autores. No es una nota propia y no está
> verificada: entra al corpus para que el golden set deje de preguntar
> solo por material que ya conoces.

AgentOSTools -- give agents a read-only ops view of the AgentOS they run on.

Answers questions about usage, latency, failures, schedules, eval history and
runtime-built components by reading directly from the AgentOS database.

Cost is not reported: agno only records provider-supplied cost, which almost no
provider returns, and it is not aggregated into the daily metrics rollup.

Typical use:
    from agno.tools.agentos import AgentOSTools

    ops_agent = Agent(
        model=OpenAIResponses(id="gpt-5.5"),
        tools=[AgentOSTools(db=db)],
    )

    ops_agent.print_response("Which agent is slowest, and which tools fail the most?")

The toolkit takes the database, never the AgentOS instance: agents are constructed
before the OS and passed into ``AgentOS(agents=[...])``, so an agent holding an OS
reference would be a construction cycle. Every tool reads only from ``db``.

Enable flags:
    * All surfaces are enabled by default: metrics, traces, schedules, evals,
      components and approvals.
    * Pass e.g. ``schedules=False`` to hide a surface from the agent.
    * ``components`` defaults to False for async databases, which do not support
      ``list_components``. Passing ``components=True`` with an async database
      raises at construction time.
    * Surfaces not supported by the configured database (e.g. schedules on most
      backends) return a clear error payload at call time.

Read-only:
    * No tool mutates platform state. Schedule, approval and component management
      are deliberately not exposed. The one write that does happen is the metrics
      rollup refresh inside get_platform_metrics -- derived data, no user content.
    * Span attributes payloads, approval tool arguments and schedule run
      input/output are never returned -- they can hold full conversation content.
    * Schedule run errors are redacted: an error that came with an HTTP status
      code is reduced to ``HTTP <code>`` (upstream response bodies echo run
      input back, e.g. via a 422), and framework-generated messages are capped
      at their first line, 200 characters.
    * The tools read the database directly, so AgentOS endpoint scopes do not
      apply to them: anyone who can talk to the agent sees platform-wide
      aggregates, and pending approvals include identifiers (user_id, tool_name,
      session_id). Expose the agent carrying this toolkit to operators, and use
      the enable flags to trim surfaces for wider audiences.
