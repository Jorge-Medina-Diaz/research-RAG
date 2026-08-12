"""
El pipeline de ingesta: bandeja → corpus.

Sin cola, sin outbox, sin Redis, sin worker. Un script síncrono sobre una
carpeta. La complejidad de eventos del proyecto anterior existía por un SaaS
multi-usuario; aquí un solo usuario ingiere unos pocos ficheros a la semana y
no hay nada que la pague.

**El sistema de ficheros ES la dead-letter queue**, y se ve con `ls` sin abrir
psql: un artefacto rechazado se queda en `artefactos/entrada/rechazado/` con un
`.motivo.txt` hermano. Es la respuesta directa al pipeline que descartaba
eventos de tres formas en silencio y no tenía DLQ.

**Orden de operaciones, y por qué es idempotente en los dos modos de fallo:**

  1. COMMIT de la transacción (artefacto + fragmentos).
  2. Mover el fichero de `entrada/` a `corpus/`.

Si (2) falla, la reingesta encuentra el mismo `sha_contenido` y no hace nada.
Si (1) falla, el fichero sigue en la bandeja y se reintenta. Los dos son seguros.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from cerebro.almacen import (
    ESQUEMA,
    artefacto_vigente,
    conexion,
    crear_indices,
    epoca_abierta,
    invalidar,
    migrar,
)
from cerebro.config import PALANCAS, Palancas, tabla_fragmentos
from ingesta.contrato import Artefacto, RechazoAdmision, admitir, sha_contenido
from ingesta.trocear import construir_troceado

RAIZ = Path(__file__).resolve().parent.parent
BANDEJA = RAIZ / "artefactos" / "entrada"
CORPUS = RAIZ / "artefactos" / "corpus"
RECHAZADO = BANDEJA / "rechazado"

#: Si más de esta fracción de un lote se rechaza, el lote entero se para.
#: No es que un fichero esté mal: es que cambiaste la plantilla y estás a punto
#: de ingerir lo que no es.
UMBRAL_LOTE = 0.5


@dataclass
class Resultado:
    ruta: Path
    estado: str  # nuevo | actualizado | sin-cambios | rechazado
    artefacto_id: str | None = None
    fragmentos: int = 0
    motivo: str = ""


# --------------------------------------------------------------------------- #
# Parseo y normalización
# --------------------------------------------------------------------------- #


def partir(texto: str) -> tuple[dict[str, Any], str]:
    """Separa el frontmatter YAML del cuerpo. Sin dependencias de frontmatter."""
    if not texto.lstrip().startswith("---"):
        raise RechazoAdmision("no empieza con un bloque de frontmatter `---`")
    resto = texto.lstrip()[3:]
    corte = resto.find("\n---")
    if corte == -1:
        raise RechazoAdmision("el bloque de frontmatter no se cierra con `---`")
    crudo, cuerpo = resto[:corte], resto[corte + 4 :]
    datos = yaml.safe_load(crudo) or {}
    if not cuerpo.strip():
        raise RechazoAdmision("el cuerpo está vacío: un artefacto sin texto no es un artefacto")
    return datos, cuerpo


def derivar_id(a: Artefacto, ruta: Path) -> str:
    """`fecha-nombre-de-fichero`. Estable, legible y aparece en las citas."""
    tallo = ruta.stem.lower().replace("_", "-").replace(" ", "-")
    tallo = "".join(c for c in tallo if c.isalnum() or c == "-").strip("-")
    return f"{a.fecha.isoformat()}-{tallo}"[:80]


def normalizar(a: Artefacto, ruta: Path) -> Artefacto:
    """Rellena lo derivable y lo ANOTA. Un campo derivado que no se distingue de
    uno escrito a mano es una mentira barata que cuesta cara al depurar."""
    derivado = list(a.derivado)
    if a.id is None:
        a.id = derivar_id(a, ruta)
        derivado.append("id")
    a.derivado = derivado
    return a


def texto_indexable(a: Artefacto, cuerpo: str) -> str:
    """El texto que se trocea y se embebe: las afirmaciones MÁS el cuerpo.

    Descubierto midiendo, no razonando: con solo el cuerpo, buscar
    «MismatchError» no devolvía nada aunque el artefacto tratara exactamente de
    eso, porque el término solo aparecía en las `afirmaciones` del frontmatter.

    Y es el peor sitio donde perderlo: las afirmaciones son la parte MÁS densa
    del artefacto — la tesis destilada, con su estatus epistémico al lado. Un
    corpus que las descarta indexa la prosa y tira el resumen.

    El estatus va en el texto, no solo en los metadatos, para que la regla del
    estatus epistémico sea comprobable contra los fragmentos recuperados y no
    contra una columna que el juez no ve.
    """
    if not a.afirmaciones:
        return cuerpo.strip()
    lineas = ["## Afirmaciones", ""]
    for af in a.afirmaciones:
        marca = "" if af.estado.value == "probado" else f" [{af.estado.value}]"
        lineas.append(f"- {af.texto.strip()}{marca}")
        if af.verificable_por:
            lineas.append(f"  Verificable por: {af.verificable_por.strip()}")
    return "\n".join(lineas) + "\n\n" + cuerpo.strip()


def metadatos(a: Artefacto, epoca: int) -> dict[str, Any]:
    """Lo que va a `meta_data` de cada fragmento. Son los filtros de grada 1.

    Todo se guarda como string o int: `_dsl_to_sqlalchemy` de PgVector castea
    con `.astext`, y un booleano nativo de JSONB no casa con `'true'`.
    """
    return {
        "artefacto_id": a.id,
        "tipo": a.tipo.value,
        "dominio": a.dominio.value,
        "temas": list(a.temas),
        "titulo": a.titulo,
        "fecha": a.fecha.isoformat(),
        "madurez": a.madurez.value,
        "confianza": a.confianza.value,
        "epoca": epoca,
        "vigente": "true",
    }


# --------------------------------------------------------------------------- #
# Ingesta
# --------------------------------------------------------------------------- #


def _marcar_no_vigente(con, artefacto_id: str, p: Palancas) -> int:
    """Saca los fragmentos de un artefacto de la búsqueda SIN borrarlos.

    Siguen en la tabla porque una probe atada a una época anterior tiene que
    poder explicar por qué decía lo que decía. Un DELETE convierte esa
    explicación en un misterio.
    """
    tabla = f'{ESQUEMA}."{tabla_fragmentos(p)}"'
    r = con.execute(
        f"update {tabla} set meta_data = jsonb_set(meta_data, '{{vigente}}', '\"false\"') "  # noqa: S608
        "where meta_data->>'artefacto_id' = %s",
        (artefacto_id,),
    )
    return r.rowcount


def ingerir_fichero(
    ruta: Path, knowledge, p: Palancas = PALANCAS, *, epoca: int | None = None
) -> Resultado:
    texto = ruta.read_text(encoding="utf-8")
    datos, cuerpo = partir(texto)
    a = normalizar(admitir(datos, origen=ruta.name), ruta)
    assert a.id is not None
    sha = sha_contenido(cuerpo)
    ep = epoca if epoca is not None else epoca_abierta()

    with conexion() as con:
        previo = artefacto_vigente(con, a.id)
        # «Sin cambios» exige DOS cosas: que el contenido no haya cambiado Y que
        # el artefacto esté de verdad en la tabla de fragmentos ACTUAL.
        #
        # La segunda faltaba, y el agujero es exactamente el que este mecanismo
        # existe para evitar. El nombre de la tabla deriva de las palancas de
        # índice, así que cambiar `embedder` apunta a una tabla nueva y vacía —
        # eso es el blue-green y está bien—. Pero la idempotencia miraba solo el
        # hash del contenido: el contenido no había cambiado, así que la ingesta
        # decía «sin cambios» y no poblaba nada. El sistema quedaba sirviendo
        # contra un índice VACÍO, sin una sola excepción.
        #
        # Se descubrió al encender el embedder local: `rag ingerir` dijo
        # «14 artefactos» y la tabla tenía cero fragmentos.
        if previo and previo["sha_contenido"] == sha and _contar_fragmentos(a.id, p):
            return Resultado(ruta, "sin-cambios", a.id)

        version = (previo["version"] + 1) if previo else 1
        if previo:
            # Versión nueva: la vieja cierra su ventana y sus fragmentos salen de
            # la búsqueda. Nunca se borra nada.
            invalidar(con, a.id, por=f"{a.id}@v{version}")
            _marcar_no_vigente(con, a.id, p)

        # Lo que este artefacto declara superar. Declararlo ES la firma humana:
        # escribiste el fichero, luego firmaste. Nada más cierra una ventana.
        for superado in a.supera:
            if invalidar(con, superado, por=a.id):
                _marcar_no_vigente(con, superado, p)

        con.execute(
            f"insert into {ESQUEMA}.artefacto "
            "(id, version, tipo, titulo, dominio, temas, madurez, confianza, fecha, "
            " ruta, frontmatter, sha_contenido, sha_frontmatter, epoca) "
            "values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                a.id, version, a.tipo.value, a.titulo, a.dominio.value, list(a.temas),
                a.madurez.value, a.confianza.value, a.fecha,
                str(ruta.relative_to(RAIZ)).replace("\\", "/"),
                # jsonb: JSON, no YAML. `default=str` para las fechas.
                json.dumps(datos, default=str, ensure_ascii=False), sha,
                sha_contenido(json.dumps(datos, sort_keys=True, default=str)), ep,
            ),
        )
        con.commit()

    meta = metadatos(a, ep)
    knowledge.insert(
        name=a.id,
        description=a.titulo,
        text_content=texto_indexable(a, cuerpo),
        metadata=meta,
        reader=_reader(p, meta),
        upsert=True,
    )
    return Resultado(
        ruta,
        "actualizado" if version > 1 else "nuevo",
        a.id,
        _contar_fragmentos(a.id, p),
    )


def _reader(p: Palancas, meta: dict[str, Any]):
    from agno.knowledge.reader.text_reader import TextReader

    class _R(TextReader):
        """El reader hereda los metadatos del artefacto para que la cabecera de
        `ConMetadatos` sepa qué anteponer a cada fragmento."""

        def read(self, *args, **kwargs):  # type: ignore[override]
            docs = super().read(*args, **kwargs)
            for d in docs:
                d.meta_data = {**(d.meta_data or {}), **meta}
            return docs

    # `meta=meta`: el troceado necesita los metadatos AL TROCEAR, y el
    # envoltorio de abajo se los pega al documento después. Pasarlos por
    # construcción es lo único que hace que `metadatos_prepend` anteponga
    # algo de verdad.
    return _R(chunking_strategy=construir_troceado(p, meta=meta))


def _actualizar_ruta(artefacto_id: str | None, destino) -> None:
    """La ruta del artefacto, después de moverlo al corpus."""
    if not artefacto_id:
        return
    with conexion() as con:
        con.execute(
            f"update {ESQUEMA}.artefacto set ruta = %s "
            "where id = %s and valido_hasta is null",
            (str(destino.relative_to(RAIZ)).replace("\\", "/"), artefacto_id),
        )
        con.commit()


def _contar_fragmentos(artefacto_id: str, p: Palancas) -> int:
    tabla = f'{ESQUEMA}."{tabla_fragmentos(p)}"'
    with conexion() as con:
        try:
            fila = con.execute(
                f"select count(*) as n from {tabla} "  # noqa: S608
                "where meta_data->>'artefacto_id' = %s and "
                "coalesce(meta_data->>'vigente','true') = 'true'",
                (artefacto_id,),
            ).fetchone()
            return int(fila["n"]) if fila else 0
        except Exception:
            return 0


def ingerir_bandeja(p: Palancas = PALANCAS, *, mover: bool = True) -> list[Resultado]:
    """Procesa `artefactos/entrada/*.md`. Devuelve un resultado por fichero."""
    migrar()
    BANDEJA.mkdir(parents=True, exist_ok=True)
    CORPUS.mkdir(parents=True, exist_ok=True)

    ficheros = sorted(f for f in BANDEJA.glob("*.md") if f.is_file())
    if not ficheros:
        return []

    from cerebro.agente import construir_knowledge

    knowledge = construir_knowledge(p)
    resultados: list[Resultado] = []

    for f in ficheros:
        try:
            r = ingerir_fichero(f, knowledge, p)
        except RechazoAdmision as exc:
            r = Resultado(f, "rechazado", motivo=str(exc))
        except Exception as exc:  # noqa: BLE001
            r = Resultado(f, "rechazado", motivo=f"{type(exc).__name__}: {exc}")
        resultados.append(r)

    rechazados = [r for r in resultados if r.estado == "rechazado"]
    if len(rechazados) > UMBRAL_LOTE * len(resultados):
        raise SystemExit(
            f"\n  PUERTA DE LOTE: {len(rechazados)} de {len(resultados)} rechazados.\n"
            "  Eso no es que un fichero esté mal: es que cambiaste la plantilla y\n"
            "  estás a punto de ingerir lo que no es. No se ha movido nada.\n\n"
            + "\n".join(f"    {r.ruta.name}: {r.motivo}" for r in rechazados)
            + "\n"
        )

    if mover:
        RECHAZADO.mkdir(parents=True, exist_ok=True)
        for r in resultados:
            if r.estado == "rechazado":
                destino = RECHAZADO / r.ruta.name
                shutil.move(str(r.ruta), destino)
                destino.with_suffix(".motivo.txt").write_text(r.motivo + "\n", encoding="utf-8")
            else:
                anio = str(date.today().year)
                (CORPUS / anio).mkdir(parents=True, exist_ok=True)
                destino = CORPUS / anio / r.ruta.name
                shutil.move(str(r.ruta), destino)
                # Y se ACTUALIZA la ruta en la tabla. Sin esto, `artefacto.ruta`
                # se queda apuntando a `artefactos/entrada/…`, donde el fichero
                # ya no está: 14 de 14 rutas inexistentes.
                #
                # Consecuencia concreta y silenciosa: `grafo.construir()` abre
                # el fichero para buscar citas, se come un OSError por cada
                # artefacto, hace `continue`, y la clase de arista `cita` —una
                # de las tres que el módulo llama HECHOS frente a inferencias—
                # no produce ni una fila. Nunca. En el corpus actual serían 18.
                _actualizar_ruta(r.artefacto_id, destino)

    if any(r.estado in ("nuevo", "actualizado") for r in resultados):
        for linea in crear_indices(p):
            print(f"  índice · {linea}")

    return resultados
