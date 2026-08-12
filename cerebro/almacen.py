"""
El almacén propio: artefactos, épocas y los índices que Agno no crea.

Agno posee la tabla de fragmentos (embeddings, FTS, filtros): forkearla para
añadir tres columnas sería pagar mantenimiento para siempre. Lo nuestro va en
`meta_data`, que es lo que PgVector filtra.

Aquí vive lo que Agno no modela: el registro de artefactos con su versión y su
ventana de validez, y las épocas.

**Los índices se crean aquí a mano, y eso no es preferencia.** Verificado en
agno 2.8.6: `PgVector.create()` (pgvector.py:226) crea extensión, esquema y
tabla con cuatro índices btree, y nada más. `_create_vector_index` y
`_create_gin_index` solo se llaman desde `optimize()` (:1273), y **nada en
`agno/knowledge/` ni en `agno/vectordb/pgvector/` llama a `optimize()`** — el
único llamador del paquete es `singlestore.py:116`. Y aunque lo llamases,
`_create_gin_index` (:1462) interpola `content_language` sin comillas y emite
`to_tsvector(spanish, content)`, que Postgres resuelve como columna y falla.

O sea: sin esto, `hnsw_m` y `hnsw_ef_construction` son palancas sobre un índice
que no existe. Es la misma clase de defecto que el `SET`-tras-`MERGE` de AGE.
"""

from __future__ import annotations

import contextlib
import hashlib
from collections.abc import Iterator
from typing import Any

import psycopg
from psycopg.rows import dict_row

from cerebro.config import DB_URL, ESQUEMA, PALANCAS, Palancas, tabla_fragmentos


def dsn(url: str = DB_URL) -> str:
    """SQLAlchemy usa postgresql+psycopg://; psycopg quiere postgresql://."""
    return url.replace("postgresql+psycopg://", "postgresql://")


@contextlib.contextmanager
def conexion(*, autocommit: bool = False) -> Iterator[psycopg.Connection]:
    with psycopg.connect(dsn(), row_factory=dict_row, autocommit=autocommit) as con:
        yield con


@contextlib.contextmanager
def punto_de_guardado(con: psycopg.Connection, etiqueta: str) -> Iterator[None]:
    """Todo lo que pueda lanzar dentro de una transacción va aquí dentro.

    Un `except` sobre trabajo de base de datos SIN savepoint deja la transacción
    abortada y convierte el COMMIT del llamante en un ROLLBACK silencioso. Es el
    fallo exacto que en CVs-SaaS dejó la detección de comunidades reportando
    `{"status": "ok"}` sobre una transacción revertida. Se hace el camino
    ergonómico para que nadie escriba el `try` desnudo.
    """
    with con.transaction():
        yield


# --------------------------------------------------------------------------- #
# Esquema
# --------------------------------------------------------------------------- #

DDL = f"""
create schema if not exists {ESQUEMA};
create extension if not exists vector;

-- Un artefacto, en una versión. Nunca se borra una fila: se cierra su ventana.
create table if not exists {ESQUEMA}.artefacto (
  id              text        not null,
  version         int         not null default 1,
  tipo            text        not null,
  titulo          text        not null,
  dominio         text        not null,
  temas           text[]      not null default '{{}}',
  madurez         text        not null,
  confianza       text        not null,
  fecha           date        not null,
  ruta            text        not null,
  frontmatter     jsonb       not null,
  sha_contenido   text        not null,
  sha_frontmatter text        not null,
  epoca           int         not null,
  -- bi-temporal: "no reviertas, invalida"
  valido_desde    timestamptz not null default now(),
  valido_hasta    timestamptz,
  superado_por    text,
  primary key (id, version)
);
create index if not exists artefacto_vigente
  on {ESQUEMA}.artefacto (id) where valido_hasta is null;
create index if not exists artefacto_epoca on {ESQUEMA}.artefacto (epoca);

-- Una época es un corte del corpus. Medir "a la época E" es filtrar, no copiar.
create table if not exists {ESQUEMA}.epoca (
  numero        int         primary key,
  abierta_en    timestamptz not null default now(),
  cerrada_en    timestamptz,
  corpus_sha    text,
  n_artefactos  int
);

-- Cada consulta que atraviesa el recuperador. Es rag-glue en SQL: el score se
-- captura en el instante de la búsqueda o no existe.
create table if not exists {ESQUEMA}.consulta (
  id             bigserial   primary key,
  ts             timestamptz not null default now(),
  huella_config  text        not null,
  huella_indice  text        not null,
  epoca_filtro   int,
  consulta       text        not null,
  consulta_efectiva text     not null,
  es_probe       boolean     not null default false,
  probe_id       text,
  n_devueltos    int         not null,
  ms_por_etapa   jsonb       not null default '{{}}',
  -- El pool COMPLETO, no los top_k devueltos: los descartados son justo lo que
  -- ningún motor deja ver, y son la mitad del diagnóstico de `ordenacion`.
  hits           jsonb       not null default '[]',
  abstuvo        boolean     not null default false,
  -- la señal más barata que existe, y no se puede añadir retroactivamente
  voto           smallint,
  session_id     text,
  run_id         text
);
create index if not exists consulta_ts on {ESQUEMA}.consulta (ts desc);
create index if not exists consulta_voto on {ESQUEMA}.consulta (ts desc) where voto is not null;

-- ── FASE 3 · el grafo ──────────────────────────────────────────────────────
--
-- Dos tablas, no un motor de grafos. En CVs-SaaS esto era Apache AGE, y AGE 1.5
-- descartaba en silencio un SET que seguía a un MERGE que crea relación: todas
-- las aristas nacieron con properties vacías y el modelo bi-temporal quedó
-- decorativo. Aquí las aristas son filas con columnas, y una columna que no se
-- escribe se ve con un SELECT.
--
-- El nodo es el ARTEFACTO, no el fragmento. Un grafo de fragmentos tendría diez
-- veces más nodos y sus aristas no significarían nada: «este párrafo se parece
-- a ese» no es una relación, es una coincidencia de embedding.
create table if not exists {ESQUEMA}.arista (
  origen        text        not null,
  destino       text        not null,
  tipo          text        not null,
  peso          real        not null default 1.0,
  -- de dónde salió: 'declarada' (el frontmatter la dice), 'derivada' (temas o
  -- dominio compartidos), 'inferida' (co-recuperación en tráfico real).
  procedencia   text        not null,
  epoca         int         not null,
  detalle       jsonb       not null default '{{}}',
  -- bi-temporal, igual que el artefacto: una arista no se borra, se cierra.
  valido_desde  timestamptz not null default now(),
  valido_hasta  timestamptz,
  primary key (origen, destino, tipo)
);
create index if not exists arista_origen on {ESQUEMA}.arista (origen)
  where valido_hasta is null;
create index if not exists arista_destino on {ESQUEMA}.arista (destino)
  where valido_hasta is null;
create index if not exists arista_epoca on {ESQUEMA}.arista (epoca);

-- Las comunidades detectadas sobre el grafo, con su resumen. Se recalculan
-- enteras en cada avance de época: son una VISTA del grafo, no un dato propio,
-- y mantenerlas incrementalmente sería inventar un problema.
create table if not exists {ESQUEMA}.comunidad (
  id            int         not null,
  epoca         int         not null,
  miembros      text[]      not null,
  etiqueta      text,
  resumen       text,
  -- modularidad de ESTA comunidad, no la global: sirve para saber cuáles son
  -- de verdad y cuáles son ruido de la partición.
  cohesion      real,
  calculada_en  timestamptz not null default now(),
  primary key (id, epoca)
);

-- ── FASE 3 · las propuestas ────────────────────────────────────────────────
--
-- Nada que un modelo proponga entra al corpus sin firma. La cola es una tabla y
-- no un fichero porque el estado —pendiente, aceptada, rechazada— es lo que
-- hace que la revisión no se repita, y porque un rechazo con motivo es el dato
-- más caro de conseguir y el primero que se pierde.
create table if not exists {ESQUEMA}.propuesta (
  id            bigserial   primary key,
  ts            timestamptz not null default now(),
  clase         text        not null,   -- 'analogia' | 'arista' | 'probe' | 'instruccion'
  epoca         int         not null,
  sujeto        text        not null,
  objeto        text,
  cuerpo        jsonb       not null,
  -- por qué el sistema cree que esto vale: la distancia, el modelo, el motivo.
  evidencia     jsonb       not null default '{{}}',
  estado        text        not null default 'pendiente',
  resuelta_en   timestamptz,
  motivo        text
);
create index if not exists propuesta_pendiente on {ESQUEMA}.propuesta (ts desc)
  where estado = 'pendiente';

-- ── FASE 4 · la topología, época a época ───────────────────────────────────
--
-- Una foto de la forma del grafo en cada época. No sirve para responder
-- preguntas: sirve para responder «¿en qué está cambiando mi investigación?»,
-- que es la única pregunta que un corpus puede contestar y un documento no.
create table if not exists {ESQUEMA}.topologia (
  epoca         int         primary key,
  n_nodos       int         not null,
  n_aristas     int         not null,
  n_componentes int         not null,
  densidad      real        not null,
  modularidad   real,
  -- los artefactos que unen comunidades que si no estarían separadas
  puentes       jsonb       not null default '[]',
  -- pares de comunidades sin ninguna arista entre ellas: los huecos donde una
  -- analogía tendría más valor, porque nadie la ha escrito todavía
  agujeros      jsonb       not null default '[]',
  medida_en     timestamptz not null default now()
);
"""


def migrar() -> None:
    with conexion(autocommit=True) as con:
        con.execute(DDL)  # type: ignore[arg-type]
        con.execute(f"select 1 from {ESQUEMA}.epoca limit 1")
        if con.execute(f"select count(*) as n from {ESQUEMA}.epoca").fetchone()["n"] == 0:  # type: ignore[index]
            con.execute(f"insert into {ESQUEMA}.epoca (numero) values (0)")


def crear_indices(p: Palancas = PALANCAS, *, recrear: bool = False) -> list[str]:
    """Crea el HNSW y el GIN sobre la tabla de fragmentos de Agno.

    Idempotente. Devuelve qué hizo, para que la ingesta lo pueda imprimir en vez
    de dejarlo como efecto invisible.
    """
    tabla = f'{ESQUEMA}."{tabla_fragmentos(p)}"'
    op = {"cosine": "vector_cosine_ops", "l2": "vector_l2_ops",
          "max_inner_product": "vector_ip_ops"}[p.distancia]
    nombre_hnsw = f"{tabla_fragmentos(p)}_hnsw"
    nombre_gin = f"{tabla_fragmentos(p)}_gin"
    hecho: list[str] = []

    with conexion(autocommit=True) as con:
        existe = con.execute(
            "select 1 from information_schema.tables where table_schema=%s and table_name=%s",
            (ESQUEMA, tabla_fragmentos(p)),
        ).fetchone()
        if not existe:
            return ["la tabla de fragmentos aún no existe: ingiere algo primero"]

        if recrear:
            con.execute(f'drop index if exists {ESQUEMA}."{nombre_hnsw}"')
            con.execute(f'drop index if exists {ESQUEMA}."{nombre_gin}"')

        con.execute(
            f'create index if not exists "{nombre_hnsw}" on {tabla} '
            f"using hnsw (embedding {op}) "
            f"with (m = {int(p.hnsw_m)}, ef_construction = {int(p.hnsw_ef_construction)})"
        )
        hecho.append(
            f"hnsw m={p.hnsw_m} ef_construction={p.hnsw_ef_construction} {p.distancia}"
        )

        # El idioma va como literal entre comillas simples. Agno lo interpola
        # desnudo y por eso su versión falla con content_language="spanish".
        con.execute(
            f'create index if not exists "{nombre_gin}" on {tabla} '
            f"using gin (to_tsvector('{p.idioma_fts}', content))"
        )
        hecho.append(f"gin to_tsvector('{p.idioma_fts}')")
    return hecho


# --------------------------------------------------------------------------- #
# Épocas
# --------------------------------------------------------------------------- #


def epoca_abierta() -> int:
    with conexion() as con:
        fila = con.execute(
            f"select numero from {ESQUEMA}.epoca where cerrada_en is null "
            "order by numero desc limit 1"
        ).fetchone()
        return fila["numero"] if fila else 0  # type: ignore[index]


def epoca_medicion() -> int:
    """La época contra la que se mide: la última CERRADA.

    Si no hay ninguna cerrada todavía, es la abierta — al principio no hay nada
    que estabilizar. En cuanto cierras una, la medición deja de moverse aunque
    sigas ingiriendo, que es el punto entero del mecanismo.
    """
    with conexion() as con:
        fila = con.execute(
            f"select numero from {ESQUEMA}.epoca where cerrada_en is not null "
            "order by numero desc limit 1"
        ).fetchone()
        return fila["numero"] if fila else epoca_abierta()  # type: ignore[index]


def avanzar_epoca() -> tuple[int, int]:
    """Cierra la época abierta y abre la siguiente. Devuelve (cerrada, nueva).

    Es un acto deliberado y fechado, y está en la lista de nunca-automatizado:
    avanzar la época mueve la línea base de todas las mediciones futuras.
    """
    with conexion(autocommit=True) as con:
        abierta = epoca_abierta()
        sha, n = _sha_corpus(con)
        con.execute(
            f"update {ESQUEMA}.epoca set cerrada_en = now(), corpus_sha = %s, "
            "n_artefactos = %s where numero = %s",
            (sha, n, abierta),
        )
        con.execute(f"insert into {ESQUEMA}.epoca (numero) values (%s)", (abierta + 1,))
        return abierta, abierta + 1


def _sha_corpus(con: psycopg.Connection) -> tuple[str, int]:
    filas = con.execute(
        f"select id, sha_contenido from {ESQUEMA}.artefacto "
        "where valido_hasta is null order by id"
    ).fetchall()
    h = hashlib.sha256()
    for f in filas:
        h.update(f"{f['id']}:{f['sha_contenido']}".encode())  # type: ignore[index]
    return h.hexdigest()[:12], len(filas)


def sha_corpus() -> tuple[str, int]:
    with conexion() as con:
        return _sha_corpus(con)


# --------------------------------------------------------------------------- #
# Artefactos
# --------------------------------------------------------------------------- #


def artefacto_vigente(con: psycopg.Connection, artefacto_id: str) -> dict[str, Any] | None:
    return con.execute(  # type: ignore[return-value]
        f"select * from {ESQUEMA}.artefacto where id = %s and valido_hasta is null",
        (artefacto_id,),
    ).fetchone()


def invalidar(con: psycopg.Connection, artefacto_id: str, *, por: str | None = None) -> bool:
    """Cierra la ventana de validez. NO borra.

    Hay un motivo operativo además del doctrinal: una probe atada a una época
    anterior tiene que poder explicar por qué decía lo que decía. Un `DELETE`
    convierte esa explicación en un misterio.
    """
    r = con.execute(
        f"update {ESQUEMA}.artefacto set valido_hasta = now(), superado_por = %s "
        "where id = %s and valido_hasta is null",
        (por, artefacto_id),
    )
    return r.rowcount > 0


def vaciar_indice(p: Palancas = PALANCAS) -> None:
    """Borra la tabla de fragmentos Y el registro de artefactos.

    Se hace con SQL directo y no con `Knowledge.remove_all_content()`, que exige
    un `contents_db` que aquí no hace falta para nada más.

    Solo se llama desde `ingerir --recrear`, y eso es lo que hay que correr tras
    tocar una palanca de grada 3. No se dispara solo: reindexar cuesta dinero, y
    una reindexación accidental a mitad de una ronda deja el archivo con dos
    configuraciones mezcladas y ningún error que lo diga.
    """
    with conexion(autocommit=True) as con:
        tabla = f'{ESQUEMA}."{tabla_fragmentos(p)}"'
        con.execute(f"drop table if exists {tabla} cascade")
        con.execute(f"delete from {ESQUEMA}.artefacto")


def listar_vigentes() -> list[dict[str, Any]]:
    with conexion() as con:
        return con.execute(  # type: ignore[return-value]
            f"select id, tipo, titulo, dominio, temas, epoca, fecha "
            f"from {ESQUEMA}.artefacto where valido_hasta is null order by fecha desc, id"
        ).fetchall()
