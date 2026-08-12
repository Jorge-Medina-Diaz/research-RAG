---
tipo: lectura-paper
titulo: "FileSystem: a durable, private filesystem for agents"
fecha: 2026-08-12
temas: [agno]
dominio: otro
madurez: maduro
confianza: alta
fuentes:
  - tipo: repo
    ref: agno-agi/agno
    commit: v2.8.6
    acceso: 2026-08-12
---

> Corpus AJENO. Documentación del módulo `fs\fs.py` de Agno 2.8.6,
> tal cual la escribieron sus autores. No es una nota propia y no está
> verificada: entra al corpus para que el golden set deje de preguntar
> solo por material que ya conoces.

FileSystem: a durable, private filesystem for agents.

To the agent it looks exactly like a normal filesystem toolkit; underneath it is
a pluggable ``BaseFS`` backend, database by default. Use it for the agent's own
durable notes: decisions with their reasoning, running documents, working state
it will need again.

Attach the tools, and compose its instructions into your own:

    from agno.agent import Agent
    from agno.db.sqlite import SqliteDb
    from agno.fs import FileSystem

    fs = FileSystem(SqliteDb(db_file="agent.db"))
    agent = Agent(
        tools=[fs.tools()],
        instructions=["my instructions", fs.instructions()],
    )
