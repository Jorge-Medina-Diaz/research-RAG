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


#: Qué modelo y qué dimensión espera cada proveedor.
#:
#: La dimensión **no es una preferencia, es una propiedad del modelo**, y un
#: desajuste es de la peor clase: no lanza error. Crea una columna `vector(1536)`
#: y la rellena con 384 números —o revienta a mitad de la ingesta, según el
#: driver—, y en el mejor caso acabas con un índice cuyo contenido no significa
#: lo que dice su nombre.
#:
#: `mock` acepta cualquiera: es SHA-256 y produce tantos números como le pidas.
#: Por eso el desajuste no se veía: el único proveedor que se usaba se adaptaba
#: a lo que le dijeran.
MODELOS: dict[str, tuple[str | None, int | None]] = {
    "mock": (None, None),
    "local": ("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2", 384),
    "openai": ("text-embedding-3-small", 1536),
}


def comprobar_coherencia(p: Palancas = PALANCAS) -> None:
    """El modelo y la dimensión de las palancas tienen que casar con el proveedor.

    Se comprueba al construir el embedder y no en un `assert` de import, porque
    el proveedor vive en el entorno y las palancas en el fichero: el mismo
    `config.py` es correcto con `EMBEDDINGS_PROVIDER=mock` e incorrecto con
    `local`, y un assert de import haría imposible tener las dos cosas.
    """
    proveedor = proveedor_embeddings()
    modelo, dim = MODELOS.get(proveedor, (None, None))
    if modelo is None:
        return
    if p.embedder != modelo or p.embedder_dim != dim:
        raise EmbedderMalConfigurado(
            f"EMBEDDINGS_PROVIDER={proveedor!r} espera "
            f"embedder={modelo!r} con embedder_dim={dim}, y las palancas dicen "
            f"embedder={p.embedder!r} con embedder_dim={p.embedder_dim}.\n\n"
            "La dimensión es una propiedad del modelo, no una preferencia: un "
            "desajuste NO lanza error por sí solo, crea un índice cuyo contenido "
            "no significa lo que dice su nombre. Ajusta las dos palancas en "
            "`cerebro/config.py` — son de grada 3, así que hay que reindexar."
        )


#: Un embedder por (proveedor, modelo, dimensión). No es una optimización
#: cosmética: `construir_embedder` se llama una vez por probe, y con el
#: proveedor local eso significaba cargar 470 MB de pesos cuarenta y una veces
#: por corrida. Con `mock` y con `openai` no se notaba —uno es aritmética y el
#: otro es una llamada HTTP— y por eso nadie lo vio hasta encender el local.
#:
#: La clave incluye el modelo y la dimensión, no solo el proveedor: si alguien
#: cambia la palanca a mitad de proceso —el bucle lo hace— tiene que salir un
#: embedder nuevo, no el de antes con otro nombre.
_CACHE: dict[tuple[str, str, int], Embedder] = {}


def construir_embedder(p: Palancas = PALANCAS) -> Embedder:
    proveedor = proveedor_embeddings()
    comprobar_coherencia(p)

    clave = (proveedor, p.embedder, p.embedder_dim)
    if (cacheado := _CACHE.get(clave)) is not None:
        return cacheado
    _CACHE[clave] = embedder = _construir(proveedor, p)
    return embedder


def _construir(proveedor: str, p: Palancas) -> Embedder:

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

    if proveedor == "local":
        # Un modelo de embeddings que corre en CPU, sin clave y sin coste.
        #
        # Es el tercer proveedor y llegó tarde, pero cambia lo que el
        # repositorio puede hacer sin gastar un euro. El `mock` es SHA-256
        # normalizado: sirve para probar la fontanería y sus vectores son casi
        # ortogonales, así que la distancia entre dos artefactos cualesquiera
        # ronda 1,0 **por construcción**. Con eso:
        #
        #   · la minería de analogías no es que no encuentre nada — es que la
        #     pregunta «¿están estos dos a media distancia?» no se puede ni
        #     formular;
        #   · el carril denso devuelve ruido, así que cualquier medición de
        #     recuperación mide la suerte del hash;
        #   · el grafo se apoya en semillas que no significan nada.
        #
        # `paraphrase-multilingual-MiniLM-L12-v2` es de los pocos con español
        # decente a 384 dimensiones. Ocupa ~470 MB la primera vez y después es
        # instantáneo. No es tan bueno como `text-embedding-3-small`, y eso es
        # exactamente lo que hay que decir: es «real» en el sentido de que las
        # distancias significan algo, no en el de que sean las mejores.
        try:
            from agno.knowledge.embedder.sentence_transformer import (
                SentenceTransformerEmbedder,
            )
        except ImportError as e:
            raise EmbedderMalConfigurado(
                "EMBEDDINGS_PROVIDER=local necesita sentence-transformers. "
                "Instálalo con `uv run rag extras`."
            ) from e

        return SentenceTransformerEmbedder(id=p.embedder, dimensions=p.embedder_dim)

    raise EmbedderMalConfigurado(
        f"EMBEDDINGS_PROVIDER={proveedor!r} no reconocido. "
        "Válidos: mock (SHA-256, para la fontanería), local (CPU, sin clave, "
        "distancias reales) y openai (con clave)."
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
