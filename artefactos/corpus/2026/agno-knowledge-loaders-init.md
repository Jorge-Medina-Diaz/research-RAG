---
tipo: lectura-paper
titulo: Remote content loaders for Knowledge
fecha: 2026-08-12
temas: [agno, knowledge, loaders]
dominio: recuperacion
madurez: maduro
confianza: alta
fuentes:
  - tipo: repo
    ref: agno-agi/agno
    commit: v2.8.6
    acceso: 2026-08-12
---

> Corpus AJENO. Documentación del módulo `knowledge\loaders\__init__.py` de Agno 2.8.6,
> tal cual la escribieron sus autores. No es una nota propia y no está
> verificada: entra al corpus para que el golden set deje de preguntar
> solo por material que ya conoces.

Remote content loaders for Knowledge.

This module provides loaders for various cloud storage providers:
- S3Loader: AWS S3
- GCSLoader: Google Cloud Storage
- SharePointLoader: Microsoft SharePoint
- GitHubLoader: GitHub repositories
- AzureBlobLoader: Azure Blob Storage

All loaders inherit from BaseLoader which provides common utilities for
computing content names, creating content entries, and merging metadata.
