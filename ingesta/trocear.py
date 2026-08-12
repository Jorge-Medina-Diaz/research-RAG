"""
Troceado: la estrategia base más dos decoradores que enriquecen cada fragmento.

Los dos decoradores hacen lo mismo conceptualmente —añadir al fragmento el
contexto que perdió al separarse de su documento— por dos precios muy distintos:

  ConMetadatos       determinista, gratis, siempre encendido
  ContextoSituacional una llamada de LLM por fragmento, apagado por defecto

Los dos están en INDEX_BOUND: cambian el texto que se embebe, así que dos
índices con distinta configuración contienen vectores distintos del mismo
fragmento. Por eso son grada 3 y por eso el nombre de la tabla deriva del hash.
"""

from __future__ import annotations

from typing import Any

from agno.knowledge.chunking.fixed import FixedSizeChunking
from agno.knowledge.chunking.recursive import RecursiveChunking
from agno.knowledge.chunking.strategy import ChunkingStrategy
from agno.knowledge.document.base import Document

from cerebro.config import PALANCAS, Palancas

#: Plantilla del contexto situacional. Su sha entra en la huella del índice:
#: cambiar el texto de esta plantilla cambia cada vector del corpus.
PLANTILLA_CONTEXTO = """\
Este es un fragmento de un artefacto de investigación titulado «{titulo}»
({tipo}, dominio {dominio}).

<artefacto_completo>
{documento}
</artefacto_completo>

<fragmento>
{fragmento}
</fragmento>

Escribe UNA O DOS frases que sitúen el fragmento dentro del artefacto, para
mejorar su recuperación. Nombra de qué trata y a qué parte del argumento
pertenece. Responde solo con esas frases, sin preámbulo."""


def estrategia_base(p: Palancas = PALANCAS) -> ChunkingStrategy:
    """Los imports pesados van dentro a propósito: `semantic` necesita numpy, que
    no viene en la instalación base, y un import en cabecera rompería el arranque
    de quien no lo tenga aunque no use esa estrategia."""
    if p.troceado == "fixed":
        return FixedSizeChunking(chunk_size=p.tam_fragmento, overlap=p.solape)
    if p.troceado == "semantic":
        try:
            from agno.knowledge.chunking.semantic import SemanticChunking
        except ImportError as e:
            raise ImportError(
                "troceado='semantic' necesita numpy y chonkie. Instálalos con "
                "`uv run rag extras`, o usa troceado='recursive'."
            ) from e
        return SemanticChunking(chunk_size=p.tam_fragmento)
    return RecursiveChunking(chunk_size=p.tam_fragmento, overlap=p.solape)


class ConMetadatos(ChunkingStrategy):
    """Antepone a CADA fragmento una cabecera con sus metadatos.

    Es contextual retrieval del pobre, y por eso está encendido por defecto: sin
    él, el fragmento 7 de un artefacto llega al índice sin decir de qué artefacto
    es ni de qué trata, y una consulta que nombra el tema no lo encuentra aunque
    la respuesta esté dentro. Cuesta cero llamadas y unos pocos tokens por
    fragmento.

    Qué campos se anteponen es la palanca `metadatos_prepend`.
    """

    def __init__(
        self,
        base: ChunkingStrategy,
        p: Palancas = PALANCAS,
        meta: dict[str, Any] | None = None,
    ) -> None:
        self.base = base
        self.p = p
        # Los metadatos, POR CONSTRUCCIÓN y no leídos del documento.
        #
        # Leerlos de `document.meta_data` era lo natural y no funcionaba:
        # `TextReader.read()` trocea DENTRO de `read`, y el envoltorio del
        # pipeline le pega los metadatos al documento DESPUÉS. Así que cuando
        # esta clase preguntaba, el diccionario estaba vacío y la cabecera salía
        # vacía — sin excepción, sin aviso, y con la palanca `metadatos_prepend`
        # marcada como GRADA 3: moverla cambiaba el nombre de la tabla, obligaba
        # a re-embeber el corpus entero pagando embeddings, y producía vectores
        # idénticos. La palanca más cara del repositorio no cambiaba un byte.
        self.meta = meta or {}

    def _cabecera(self, meta: dict[str, Any]) -> str:
        partes = []
        for campo in self.p.metadatos_prepend:
            valor = meta.get(campo)
            if not valor:
                continue
            if isinstance(valor, (list, tuple)):
                valor = ", ".join(str(x) for x in valor)
            partes.append(f"{campo}: {valor}")
        return "\n".join(partes)

    def chunk(self, document: Document) -> list[Document]:
        trozos = self.base.chunk(document)
        # El del documento primero por si algún día llega relleno; el de
        # construcción es el que de verdad tiene algo en el camino del pipeline.
        cabecera = self._cabecera({**self.meta, **(document.meta_data or {})})
        if not cabecera:
            return trozos
        for t in trozos:
            t.content = f"{cabecera}\n\n{t.content}"
        return trozos


class ContextoSituacional(ChunkingStrategy):
    """Contexto situacional estilo Anthropic: un LLM antepone a cada fragmento
    una o dos frases que lo sitúan en su artefacto, ANTES de embeber.

    Anthropic reporta ~35 % menos fallos de recuperación (49 % combinado con BM25
    y reordenación). Cifra suya, auto-reportada, sin réplica independiente: entra
    como `reportado`, no como `probado`.

    Coste: una llamada por fragmento. Con caché de prompt sobre el artefacto
    completo, el marginal son lecturas de caché más ~80 tokens de salida. Con
    cientos de artefactos son céntimos; con 10^5 fragmentos deja de serlo.

    **Se fuerza a apagado en modo mock.** Un índice mock que además llevara texto
    generado por un LLM sería irreproducible, y el proveedor está en INDEX_BOUND
    justamente para que las dos cosas no se mezclen nunca.
    """

    def __init__(self, base: ChunkingStrategy, situador, p: Palancas = PALANCAS) -> None:
        self.base = base
        self.situador = situador  # Callable[[str, str, dict], str]
        self.p = p

    def chunk(self, document: Document) -> list[Document]:
        trozos = self.base.chunk(document)
        meta = document.meta_data or {}
        for t in trozos:
            try:
                contexto = self.situador(document.content, t.content, meta)
            except Exception:
                # Un fallo del situador degrada a fragmento sin contexto. Lo que
                # NO puede pasar es que la ingesta entera se caiga a medias y deje
                # el índice con la mitad de los fragmentos contextualizados y la
                # otra mitad no: eso serían dos configuraciones en una tabla.
                raise
            if contexto:
                t.content = f"{contexto.strip()}\n\n{t.content}"
                t.meta_data = {**(t.meta_data or {}), "contextualizado": True}
        return trozos


def construir_troceado(
    p: Palancas = PALANCAS, situador=None, meta: dict[str, Any] | None = None
) -> ChunkingStrategy:
    base: ChunkingStrategy = ConMetadatos(estrategia_base(p), p, meta=meta)
    if p.contextualizar:
        if situador is None:
            raise ValueError(
                "contextualizar=True necesita un situador (un cliente de LLM). "
                "En modo mock esta palanca se fuerza a False."
            )
        base = ContextoSituacional(base, situador, p)
    return base
