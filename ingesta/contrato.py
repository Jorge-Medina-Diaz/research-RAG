"""
El contrato de artefacto: qué tiene que traer un fichero para entrar al corpus.

Principio de diseño: **lo requerido es lo que no se puede derivar.** Cada campo
obligatorio de más es fricción en cada artefacto que escribas, y la fricción en
la ingesta no se paga una vez, se paga siempre. Cinco campos obligatorios, todos
de una línea; el resto se deriva y se marca como derivado.

El contrario también importa: los campos DERIVADOS se rechazan si vienen a mano.
Un `sha_contenido` escrito por una persona es un hash que no corresponde al
contenido, y eso rompe la idempotencia en silencio — la peor clase de fallo.
"""

from __future__ import annotations

import hashlib
import re
from datetime import date
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# --------------------------------------------------------------------------- #
# Vocabularios
# --------------------------------------------------------------------------- #


class Tipo(StrEnum):
    """Siete tipos. Cada uno existe porque FALLA POR UN MOTIVO DISTINTO en la
    recuperación y exige metadatos distintos — el mismo criterio con el que se
    eligieron las seis categorías de probe."""

    NOTA = "nota-investigacion"
    TEARDOWN = "teardown-repo"
    PAPER = "lectura-paper"
    PATRON = "patron"
    PROBLEMA = "problema-solucion"
    DECISION = "decision"
    BENCHMARK = "benchmark"


class Dominio(StrEnum):
    """Vocabulario CERRADO, y esa es toda su razón de ser.

    `temas` es libre y sirve para filtrar. `dominio` es cerrado y sirve para algo
    que `temas` no puede: definir «contextos dispares» de forma computable. La
    minería de analogías cross-dominio (costura, no construida en v1) necesita un
    eje sobre el que decir «a.dominio != b.dominio». Sin un eje cerrado eso no es
    una consulta, es una intuición.

    Se captura desde el primer artefacto porque un metadato que no capturaste en
    la ingesta no se rellena después sin releerlo todo.
    """

    RECUPERACION = "recuperacion"
    EVALUACION = "evaluacion"
    AGENTES = "agentes"
    DATOS = "datos"
    INFRAESTRUCTURA = "infraestructura"
    ESTADISTICA = "estadistica"
    PRODUCTO = "producto"
    OTRO = "otro"


class Madurez(StrEnum):
    SEMI = "semi"
    MADURO = "maduro"
    # `borrador` no está: se rechaza en admisión. El sistema arranca desde
    # artefactos maduros o semi-maduros, y decirlo con una negativa es más útil
    # que ingerir ruido y avisar después.


class Confianza(StrEnum):
    ALTA = "alta"
    MEDIA = "media"
    BAJA = "baja"


class Estado(StrEnum):
    """El estatus epistémico de una afirmación.

    Es la «Nota de honestidad intelectual» convertida en esquema. Una memoria que
    aplana la distinción entre «lo medí», «lo reportan sus autores» y
    «es extrapolación mía» es peligrosa precisamente porque las tres suenan igual
    de seguras cuando salen de un RAG.
    """

    PROBADO = "probado"
    REPORTADO = "reportado"
    EXTRAPOLACION = "extrapolacion"
    CONJETURA = "conjetura"


TipoFuente = Literal["repo", "paper", "web", "sesion", "libro"]

#: Campos que escribe el pipeline. Si aparecen a mano, se rechaza el artefacto.
DERIVADOS = frozenset(
    {"epoca", "sha_contenido", "sha_frontmatter", "ingerido_en", "version", "vigente"}
)

_ID_VALIDO = re.compile(r"^[a-z0-9][a-z0-9\-]{2,79}$")


# --------------------------------------------------------------------------- #
# Piezas
# --------------------------------------------------------------------------- #


class Fuente(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tipo: TipoFuente
    ref: str = Field(min_length=1, description="URL, ruta, id de arXiv o DOI")
    #: Un teardown sin commit es inverificable, y ese es su único valor.
    commit: str | None = None
    acceso: date | None = None
    revisado_por_pares: bool | None = None


class Afirmacion(BaseModel):
    """Lo que el artefacto SOSTIENE, con su estatus epistémico.

    Opcional en v1: exigirlas en cada artefacto sería fricción, y la mayoría del
    valor está en las que escribes cuando de verdad quieres fijar algo.
    """

    model_config = ConfigDict(extra="forbid")

    texto: str = Field(min_length=1)
    estado: Estado = Estado.REPORTADO
    #: Cómo se comprobaría. Obligatorio si es extrapolación: una extrapolación
    #: sin forma de comprobarse es una conjetura mal etiquetada.
    verificable_por: str | None = None

    @model_validator(mode="after")
    def _extrapolacion_verificable(self) -> Afirmacion:
        if self.estado is Estado.EXTRAPOLACION and not self.verificable_por:
            raise ValueError(
                "una afirmación marcada 'extrapolacion' necesita 'verificable_por': "
                "sin forma de comprobarla es una conjetura, y ese es otro estado"
            )
        return self


# --------------------------------------------------------------------------- #
# El artefacto
# --------------------------------------------------------------------------- #


class Artefacto(BaseModel):
    """El frontmatter YAML de un fichero de `artefactos/entrada/`.

    `extra="forbid"` a propósito: un campo mal escrito (`tema` por `temas`) se
    ignoraría en silencio y el filtro de recuperación nacería vacío. Los filtros
    de metadatos son la palanca más barata que hay; que nazcan rotos es caro.
    """

    model_config = ConfigDict(extra="forbid", use_enum_values=False)

    # --- requeridos: lo que no se puede derivar -----------------------------
    tipo: Tipo
    titulo: Annotated[str, Field(min_length=3, max_length=200)]
    fecha: date
    temas: Annotated[list[str], Field(min_length=1)]
    dominio: Dominio

    # --- derivables: el normalizador los rellena y lo anota en `_derivado` ---
    id: str | None = None
    madurez: Madurez = Madurez.SEMI
    confianza: Confianza = Confianza.MEDIA

    # --- opcionales ---------------------------------------------------------
    subtitulo: str | None = None
    fuentes: list[Fuente] = Field(default_factory=list)
    afirmaciones: list[Afirmacion] = Field(default_factory=list)
    #: Declarar `supera` ES la firma humana que cierra la ventana de validez del
    #: artefacto anterior. Escribiste el fichero, luego firmaste. Ninguna otra
    #: cosa invalida nada automáticamente.
    supera: list[str] = Field(default_factory=list)
    relacionado_con: list[str] = Field(default_factory=list)

    #: Qué rellenó el pipeline. Lo escribe el normalizador, nunca tú.
    derivado: list[str] = Field(default_factory=list, alias="_derivado")

    # --- validación ---------------------------------------------------------

    @field_validator("temas")
    @classmethod
    def _temas_normalizados(cls, v: list[str]) -> list[str]:
        limpios = [t.strip().lower() for t in v if t and t.strip()]
        if not limpios:
            raise ValueError("'temas' no puede quedar vacío tras normalizar")
        return list(dict.fromkeys(limpios))  # dedup conservando orden

    @field_validator("id")
    @classmethod
    def _id_valido(cls, v: str | None) -> str | None:
        if v is not None and not _ID_VALIDO.match(v):
            raise ValueError(
                f"id inválido: {v!r}. Minúsculas, dígitos y guiones, 3-80 caracteres. "
                "Es la clave de idempotencia y aparece en las citas de las respuestas."
            )
        return v

    @model_validator(mode="after")
    def _fuentes_segun_tipo(self) -> Artefacto:
        """Cada tipo exige lo que lo hace verificable, y nada más."""
        if self.tipo in (Tipo.TEARDOWN, Tipo.PAPER) and not self.fuentes:
            raise ValueError(
                f"un artefacto de tipo '{self.tipo.value}' necesita al menos una fuente: "
                "sin ella no se puede volver al original y la afirmación no es auditable"
            )
        if self.tipo is Tipo.TEARDOWN:
            for f in self.fuentes:
                if f.tipo == "repo" and not f.commit:
                    raise ValueError(
                        f"la fuente repo {f.ref!r} no trae 'commit'. Un teardown sin "
                        "commit es inverificable: el repo cambia y la nota deja de "
                        "poder comprobarse contra nada."
                    )
        if self.supera and self.id and self.id in self.supera:
            raise ValueError("un artefacto no puede superarse a sí mismo")
        return self


# --------------------------------------------------------------------------- #
# Errores de admisión
# --------------------------------------------------------------------------- #


class RechazoAdmision(Exception):
    """El artefacto no entra. El motivo se escribe junto al fichero.

    La bandeja + un `.motivo.txt` hermano ES la dead-letter queue, y se ve con
    `ls` sin abrir psql. Es la respuesta al pipeline de eventos del proyecto
    anterior, que descartaba en silencio de tres formas distintas y no tenía DLQ.
    """


def admitir(frontmatter: dict[str, Any], *, origen: str = "?") -> Artefacto:
    """Valida el frontmatter crudo. Lanza `RechazoAdmision` con el motivo exacto.

    Se comprueba ANTES de trocear y ANTES de embeber: un rechazo aquí no ha
    gastado ni una llamada a modelo.
    """
    if not isinstance(frontmatter, dict):
        raise RechazoAdmision(f"{origen}: el frontmatter no es un mapa YAML")

    if intrusos := sorted(DERIVADOS & frontmatter.keys()):
        raise RechazoAdmision(
            f"{origen}: {', '.join(intrusos)} lo escribe el pipeline, no tú. "
            "Un valor derivado puesto a mano no corresponde al contenido y rompe "
            "la idempotencia en silencio. Bórralo del frontmatter."
        )

    if (m := frontmatter.get("madurez")) == "borrador":
        raise RechazoAdmision(
            f"{origen}: madurez 'borrador'. El corpus arranca en artefactos "
            "semi-maduros o maduros. Termínalo o cámbialo a 'semi'."
        )
    elif m is not None and m not in {e.value for e in Madurez}:
        raise RechazoAdmision(
            f"{origen}: madurez {m!r} no reconocida. Válidas: semi, maduro."
        )

    try:
        return Artefacto.model_validate(frontmatter)
    except Exception as exc:
        raise RechazoAdmision(f"{origen}: {exc}") from exc


def sha_contenido(cuerpo: str) -> str:
    """Hash del CUERPO, normalizado. Separado del hash del frontmatter a propósito:
    si solo cambian los metadatos, se actualizan los filtros y NO se re-embebe.
    Ese ahorro es la razón de tener dos hashes."""
    return hashlib.sha256(cuerpo.strip().encode("utf-8")).hexdigest()[:16]
