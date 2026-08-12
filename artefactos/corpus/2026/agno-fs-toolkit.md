---
tipo: lectura-paper
titulo: "FileSystemTools: the tool surface over FileSystem, built by ``FileSystem.tools()``"
fecha: 2026-08-12
temas: [agno, toolkit]
dominio: otro
madurez: maduro
confianza: alta
fuentes:
  - tipo: repo
    ref: agno-agi/agno
    commit: v2.8.6
    acceso: 2026-08-12
---

> Corpus AJENO. Documentación del módulo `fs\toolkit.py` de Agno 2.8.6,
> tal cual la escribieron sus autores. No es una nota propia y no está
> verificada: entra al corpus para que el golden set deje de preguntar
> solo por material que ya conoces.

FileSystemTools: the tool surface over FileSystem, built by ``FileSystem.tools()``.

To the agent this is just a filesystem: six tools share their names, shapes and
output formats with ``agno.tools.workspace.Workspace`` (``read_file``,
``write_file``, ``list_files``, ``search_content``, ``move_file``,
``delete_file``), plus three additions the durability use cases need:
``append_file`` (line-oriented, with an optional per-line dedupe),
``replace_lines`` (edit a line range without rewriting the file) and
``check_lines`` (batch exact-line membership, the dedupe primitive).

``list_files`` and ``search_content`` return a little more than their Workspace
counterparts: a file's last-modified time, and the line number and total count of
each search hit. Both are what an agent needs to orient in state it wrote days
ago, and neither changes a signature, so Workspace parity holds where it is
tested.

These names deliberately collide with the rest of the file-toolkit family
(Workspace, FileTools, PythonTools, CodingTools, ...). Agno's tool resolver
keeps the first registration per name and drops later duplicates with a logged
warning, so attach at most one file-like toolkit per agent; when an agent
genuinely needs both FileSystem and a local workspace, wrap one in a sub-agent.
