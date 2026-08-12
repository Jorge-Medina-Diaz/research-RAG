"""
Los embedders. Dos, y el mock no es un juguete.

`MockEmbedder` produce pseudo-embeddings derivados de SHA-256, deterministas y
L2-normalizados para que el coseno siga siendo un producto escalar. No tienen
ningún significado semántico — dos textos parecidos no dan vectores parecidos —
pero SÍ hacen que el pipeline entero funcione de punta a punta sin una sola
clave: ingesta, indexado, recuperación, fusión y evaluación de nivel 0.

Eso es lo que permite que la señal determinista corra en CI y que un clon nuevo
arranque con `uv run rag up` sin configurar nada. Extraído de
`CVs-SaaS/backend/src/shared/embeddings.py`, adaptado al `Embedder` de Agno.

**Y la diferencia importante con el original:** allí, pedir OpenAI sin clave
degradaba a determinista con un `logger.warning`. Aquí revienta. Un índice mock
y uno real no son el mismo índice, y mezclarlos hace que las distancias dejen de
significar lo mismo sin lanzar ningún error. El proveedor entra en INDEX_BOUND
precisamente para que las dos tablas ni siquiera se llamen igual.
"""

from __future__ import annotations

import hashlib
import math
import os
from dataclasses import dataclass
from typing import Any

from agno.knowledge.embedder.base import Embedder

from cerebro.config import PALANCAS, Palancas, proveedor_embeddings


@dataclass
class MockEmbedder(Embedder):
    """Pseudo-embeddings SHA-256, deterministas y dimensión-estables."""

    dimensions: int = 1536
    enable_batch: bool = True
    batch_size: int = 512

    def _vector(self, texto: str) -> list[float]:
        normalizado = (texto or "<vacio>").strip().lower()
        bytes_necesarios = self.dimensions * 4
        crudo = bytearray()
        contador = 0
        semilla = normalizado.encode("utf-8")
        while len(crudo) < bytes_necesarios:
            crudo.extend(hashlib.sha256(semilla + contador.to_bytes(4, "big")).digest())
            contador += 1
        crudo = crudo[:bytes_necesarios]
        v = [
            (int.from_bytes(crudo[i : i + 4], "big") / 0xFFFFFFFF) * 2 - 1
            for i in range(0, bytes_necesarios, 4)
        ]
        norma = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / norma for x in v]

    # --- interfaz de Agno ---------------------------------------------------

    def get_embedding(self, text: str) -> list[float]:
        return self._vector(text)

    def get_embedding_and_usage(self, text: str) -> tuple[list[float], dict | None]:
        return self._vector(text), None

    async def async_get_embedding(self, text: str) -> list[float]:
        return self._vector(text)

    async def async_get_embedding_and_usage(self, text: str) -> tuple[list[float], dict | None]:
        return self._vector(text), None

    def get_embeddings_batch_and_usage(
        self, texts: list[str]
    ) -> tuple[list[list[float]], list[dict | None]]:
        return [self._vector(t) for t in texts], [None] * len(texts)

    async def async_get_embeddings_batch_and_usage(
        self, texts: list[str]
    ) -> tuple[list[list[float]], list[dict | None]]:
        return [self._vector(t) for t in texts], [None] * len(texts)


class EmbedderMalConfigurado(RuntimeError):
    """Se pidió un proveedor real sin su clave. No se degrada en silencio."""


def construir_embedder(p: Palancas = PALANCAS) -> Embedder:
    proveedor = proveedor_embeddings()

    if proveedor == "mock":
        return MockEmbedder(dimensions=p.embedder_dim)

    if proveedor == "openai":
        if not (os.getenv("OPENAI_API_KEY") or "").strip():
            raise EmbedderMalConfigurado(
                "EMBEDDINGS_PROVIDER=openai sin OPENAI_API_KEY. Esto NO degrada a "
                "mock: un índice construido con vectores deterministas y otro con "
                "vectores reales no son el mismo índice, y servir contra el "
                "equivocado no lanza ningún error, solo devuelve resultados sin "
                "sentido. Pon la clave o pon EMBEDDINGS_PROVIDER=mock."
            )
        from agno.knowledge.embedder.openai import OpenAIEmbedder

        return OpenAIEmbedder(id=p.embedder, dimensions=p.embedder_dim)

    raise EmbedderMalConfigurado(
        f"EMBEDDINGS_PROVIDER={proveedor!r} no reconocido. Válidos: mock, openai."
    )


def es_mock() -> bool:
    return proveedor_embeddings() == "mock"


def texto_a_embeber(contenido: str, meta: dict[str, Any], p: Palancas = PALANCAS) -> str:
    """Antepone los metadatos declarados en `metadatos_prepend` al texto.

    Es una palanca de grada 3 (está en INDEX_BOUND) porque cambia el texto que
    se embebe: dos índices con distinto prepend contienen vectores distintos del
    mismo fragmento.
    """
    cabecera = []
    for campo in p.metadatos_prepend:
        valor = meta.get(campo)
        if not valor:
            continue
        if isinstance(valor, (list, tuple)):
            valor = ", ".join(str(x) for x in valor)
        cabecera.append(f"{campo}: {valor}")
    return ("\n".join(cabecera) + "\n\n" + contenido) if cabecera else contenido
