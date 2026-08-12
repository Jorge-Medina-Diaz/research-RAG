"""
Las palancas del cerebro, en un solo sitio.

Esta es la pieza que hace tratable el bucle de auto-mejora: el agente que mejora
el sistema edita ESTE fichero y nada más. Todo lo demás lo lee de aquí.

Cada palanca lleva su GRADA:

    grada 1  barata y reversible en trivial      -> el bucle la toca solo
    grada 2  media, reversible con facilidad     -> el bucle la toca solo
    grada 3  cara y/o exige reindexar todo       -> requiere firma humana
    grada 4  cambia la topología del pipeline    -> no automatizado

Y su clase de REINDEXADO, que es una propiedad distinta de la grada y hay que
declararla aparte: hay palancas de grada 3 que solo reconstruyen el índice ANN
(CPU, sin llamadas de embedding) y otras que obligan a re-embeber el corpus
entero. Confundirlas cuesta dinero en una dirección y corrección en la otra.

Verificado contra agno 2.8.6.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any, Literal

RAIZ = Path(__file__).resolve().parent.parent


def cargar_env(ruta: Path | None = None) -> None:
    """Lee `.env` al importar la configuración. Cinco líneas, una dependencia menos.

    Que esto viva AQUÍ y no en un script no es cosmético. Durante el desarrollo
    esto no existía —solo `verificar.py` leía el `.env`— y el resultado fue que
    todo el sistema corría con los valores por defecto mientras `.env` decía otra
    cosa. Cambiar `DATABASE_URL` no tenía ningún efecto y nada lo avisaba.

    Es la misma familia de defecto que los índices que Agno no crea: un parámetro
    que se lee como vivo y no lo está. Se descubrió porque una comprobación de
    permisos que DEBÍA fallar devolvió una lista vacía.
    """
    ruta = ruta or (RAIZ / ".env")
    if not ruta.exists():
        return
    for cruda in ruta.read_text(encoding="utf-8").splitlines():
        linea = cruda.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, _, valor = linea.partition("=")
        # setdefault: el entorno real gana sobre el fichero, para poder correr
        # una comparación con otra configuración sin editar nada.
        os.environ.setdefault(clave.strip(), valor.strip())


cargar_env()

DB_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://ai:ai@localhost:5533/ai")
ESQUEMA = "investigacion"


# --------------------------------------------------------------------------- #
# Los tres modelos, y por qué tienen que ser de familias distintas
# --------------------------------------------------------------------------- #

#: Genera las probes semilla. El que menos corre: solo al sembrar el golden set.
GENERADOR_PROBES = os.getenv("MODELO_GENERADOR", "gemini-2.5-pro")
#: El cerebro. Responde.
SISTEMA = os.getenv("MODELO_SISTEMA", "claude-sonnet-4-5-20250929")
#: El juez. Corre en cada ronda, así que usa el proveedor cuya clave ya hace
#: falta para los embeddings.
JUEZ = os.getenv("MODELO_JUEZ", "gpt-5.2")


def familia(modelo: str) -> str:
    m = modelo.lower()
    if m.startswith("claude"):
        return "anthropic"
    if m.startswith(("gpt", "o1", "o3", "o4")):
        return "openai"
    if m.startswith("gemini"):
        return "google"
    return m.split("-")[0]


# --------------------------------------------------------------------------- #
# Palancas
# --------------------------------------------------------------------------- #


@dataclass
class Palancas:
    # ---------------------------------------------------------------- grada 1
    # Baratas de probar y triviales de revertir. No tocan el índice.

    #: Cuántos fragmentos ve el modelo. En Agno es Knowledge.max_results,
    #: NO un parámetro del Agent (error común y verificado).
    top_k: int = 12

    #: Carriles activos. En v1 hay dos; el registro admite más sin tocar nada.
    carriles: tuple[str, ...] = ("denso", "lexico")

    #: Cuántos pide cada carril ANTES de fusionar. Más ancho que top_k a
    #: propósito: el reordenador solo se gana su latencia si puede DESCARTAR.
    top_k_por_carril: int = 30

    #: Peso de cada carril dentro de la fusión RRF. Mismo orden que `carriles`.
    peso_carril: tuple[float, ...] = (1.0, 1.0)

    #: La constante de RRF. 60 es el canónico (Cormack, Clarke & Buettcher 2009)
    #: y el que usan Weaviate, Vespa y OpenSearch. Qdrant usa 2 por defecto y con
    #: otra fórmula, así que cualquier umbral copiado de un ejemplo está sesgado
    #: si no se fija esto explícitamente.
    k_rrf: int = 60

    #: Ancho del pool que llega al reordenador.
    pool_fusion: int = 40

    #: Descarta lo que no llegue a este parecido. Subirlo reduce ruido y aumenta
    #: el riesgo de dejar fuera el fragmento bueno.
    umbral_similitud: float | None = None

    #: Idioma del full-text search. En español importa: sin esto el stemming es
    #: el inglés y "calibración" no casa con "calibrar".
    idioma_fts: str = "spanish"

    #: or | and. Cómo se unen los términos de la consulta léxica.
    #:
    #: `plainto_tsquery` hace AND: una consulta de seis palabras solo casa el
    #: fragmento que contenga las seis, así que cuanto más informativa es la
    #: pregunta, menos recupera. Con OR, `ts_rank_cd` ordena por cuántos
    #: términos casan y cómo de juntos, que es lo que RRF consume.
    #:
    #: Es la palanca de la categoría `lexical_exact` y del diagnóstico
    #: `cobertura` en el carril léxico.
    fts_modo: Literal["or", "and"] = "or"

    #: Solo sirve lo vigente. Un artefacto superado sigue en la tabla —nunca se
    #: borra— pero sale de la búsqueda. "No reviertas: invalida", como un filtro.
    solo_vigentes: bool = True

    #: Filtros de metadatos. None = sin filtrar. Son la palanca más barata que
    #: existe y por eso el contrato de artefacto es estricto: nacen de ahí.
    filtro_tipo: tuple[str, ...] | None = None
    filtro_dominio: tuple[str, ...] | None = None

    #: ef_search de HNSW. Separado el de evaluación porque el filtro de época
    #: estrecha el conjunto visitable y baja el recall efectivo: en evaluación se
    #: abre la ventana para no confundir sesgo de filtrado con recall malo.
    ef_search: int = 64
    ef_search_eval: int = 256

    # ---------------------------------------------------------------- grada 2
    # Reversibles con facilidad, algo más caras de probar.

    #: none | local | cohere. "local" descarga un modelo la primera vez y corre
    #: en CPU (`uv run rag extras`); "cohere" necesita COHERE_API_KEY.
    reranker: Literal["none", "local", "cohere"] = "none"
    reranker_top_n: int = 12

    #: none | expansion | hyde | hyde_lexico. Ver `cerebro/reescritura.py`.
    #: `expansion` no gasta llamadas; los dos modos HyDE gastan una por consulta.
    #: `hyde_lexico` es el reparto asimétrico: señuelo para el denso, literal
    #: para el léxico, que es lo que cada carril hace bien.
    reescritura: Literal["none", "expansion", "hyde", "hyde_lexico"] = "none"

    #: none | reglas. Ajusta los pesos de fusión según la FORMA de la consulta,
    #: por reglas auditables y sin llamadas. Ver `cerebro/enrutador.py`.
    enrutado: Literal["none", "reglas"] = "none"

    # ---- fase 3 · el grafo. Todo esto viene apagado y su disparador está
    # ---- escrito: `multi_hop` por debajo de 0,60 tras agotar grada 1 y 2.

    #: El tercer carril se enciende AÑADIÉNDOLO A `carriles`, no con un booleano
    #: aparte. Hubo un `grafo_activo: bool` y era un segundo interruptor para lo
    #: mismo: `carriles` decía dos y el booleano decía tres, y el peso que el
    #: enrutado asignaba a «grafo» se descartaba en silencio porque `grafo` no
    #: estaba en `carriles`. Dos fuentes de verdad para un hecho es la forma más
    #: barata de fabricar un parámetro muerto.
    #:
    #:     carriles    = ("denso", "lexico", "grafo")
    #:     peso_carril = (1.0, 1.0, 1.0)

    #: Probabilidad de teletransporte del PPR. Alto = casi las semillas;
    #: bajo = el paseo se va al centro del grafo y devuelve siempre lo popular.
    grafo_alfa: float = 0.15

    #: Cuántos vecinos aporta el carril de grafo a la fusión.
    grafo_top_k: int = 10

    #: Cuántos resultados del carril denso siembran el PPR. El grafo no busca:
    #: AMPLÍA lo que el denso encontró.
    grafo_semillas: int = 5

    #: Sirve el resumen de la comunidad en vez de sus miembros cuando la
    #: consulta pide agregación. Necesita `rag comunidades --resumir`.
    comunidades_en_respuesta: bool = False

    #: La ventana de distancia coseno donde se buscan analogías. Por debajo del
    #: mínimo es un duplicado; por encima del máximo, ruido de embedding.
    analogia_min: float = 0.25
    analogia_max: float = 0.55

    #: Learning Machines de Agno: LearnedKnowledge (AGENTIC) + DecisionLog.
    #: Lo aprendido NUNCA se cita en una respuesta —eso rompería R1— y
    #: `run_rollouts` corta sus escrituras durante los evals, así que medirse
    #: no contamina la medición. Ver `cerebro/aprendizaje.py`.
    aprendizaje: bool = False

    #: Las instrucciones del cerebro. Es la palanca de casi todos los fallos de
    #: generación.
    #:
    #: OJO: es de GENERACIÓN, y un golden set mayoritariamente sintético no
    #: ordena bien arquitecturas de generación. El bucle la PROPONE; la firmas tú.
    instrucciones: tuple[str, ...] = (
        "Responde solo con lo que aparezca en el contexto recuperado.",
        "Cita el identificador del artefacto de cada afirmación, así: [[art:mi-id]].",
        "Si el contexto no contiene la respuesta, responde exactamente: "
        "«No lo tengo en la memoria.» y nada más.",
        "Reproduce cifras, versiones e identificadores tal cual figuran. "
        "No redondees, no normalices, no abrevies.",
        "Si dos artefactos dicen cosas distintas, preséntalos como dos, con sus "
        "fuentes y sus fechas. No los fundas en una síntesis que ninguno sostiene.",
        "Si un artefacto posterior supera al que responde, da el vigente y nombra "
        "el que lo superó.",
        "Marca el estatus epistémico cuando la afirmación no esté probada: di "
        "«extrapolación», «auto-reportado» o «sin verificar» según corresponda.",
        "Empieza por el dato. Sin introducción ni resumen final. Máximo ocho "
        "frases, salvo que te pidan enumerar.",
    )

    # ---------------------------------------------------------------- grada 3
    # Exigen reindexar. Firma humana antes de aplicar.

    #: recursive | fixed | semantic. `semantic` importa numpy: `uv run rag extras`.
    troceado: Literal["recursive", "fixed", "semantic"] = "recursive"
    tam_fragmento: int = 1200
    solape: int = 150

    #: Contexto situacional estilo Anthropic: un LLM antepone a cada fragmento
    #: una frase que lo sitúa en su artefacto, ANTES de embeber. Reduce fallos de
    #: recuperación ~35% según Anthropic (cifra suya, auto-reportada, sin réplica
    #: independiente). Cuesta una llamada por fragmento.
    #:
    #: Por defecto APAGADO: existe para que el bucle tenga una palanca de grada 3
    #: real que ganarse, no para encenderla el primer día. Y se fuerza a False en
    #: modo mock, para que un índice mock no se confunda jamás con uno real.
    contextualizar: bool = False

    #: Qué metadatos se anteponen al texto antes de embeber.
    metadatos_prepend: tuple[str, ...] = ("titulo", "tipo", "temas")

    #: NUNCA es una palanca automática. Cambiarla obliga a re-embeber el corpus
    #: entero: el vector store debe contener vectores de exactamente una
    #: configuración, y un re-embedding parcial no lanza ningún error, solo hace
    #: que las distancias dejen de significar lo mismo.
    embedder: str = "text-embedding-3-small"
    embedder_dim: int = 1536

    distancia: Literal["cosine", "l2", "max_inner_product"] = "cosine"
    hnsw_m: int = 16
    hnsw_ef_construction: int = 200

    # ------------------------------------------------------------------------

    def dict(self) -> dict[str, Any]:
        return asdict(self)

    def diferencias(self, otra: Palancas) -> dict[str, tuple[Any, Any]]:
        """Qué cambió entre dos configuraciones. Lo usa el reporte del bucle."""
        a, b = self.dict(), otra.dict()
        return {k: (a[k], b[k]) for k in a if a[k] != b[k]}

    def grada_de(self, palanca: str) -> int:
        """Grada de una palanca. El defecto es 4 —no automatizable— y el assert
        del final impide que ese defecto se aplique por olvido."""
        return _GRADAS.get(palanca, 4)

    def reindexa(self, palanca: str) -> str:
        return _REINDEXA.get(palanca, "todo")


# --------------------------------------------------------------------------- #
# Gradas, reindexado y diagnósticos
# --------------------------------------------------------------------------- #

_GRADAS: dict[str, int] = {
    **dict.fromkeys(
        (
            "top_k", "carriles", "top_k_por_carril", "peso_carril", "k_rrf",
            "pool_fusion", "umbral_similitud", "idioma_fts", "solo_vigentes",
            "filtro_tipo", "filtro_dominio", "ef_search", "ef_search_eval",
            "fts_modo",
        ),
        1,
    ),
    **dict.fromkeys(
        (
            "reranker", "reranker_top_n", "reescritura", "instrucciones",
            "enrutado", "grafo_alfa", "grafo_top_k",
            "grafo_semillas", "comunidades_en_respuesta",
            "analogia_min", "analogia_max", "aprendizaje",
        ),
        2,
    ),
    **dict.fromkeys(
        (
            "troceado", "tam_fragmento", "solape", "contextualizar",
            "metadatos_prepend", "embedder", "embedder_dim", "distancia",
            "hnsw_m", "hnsw_ef_construction",
        ),
        3,
    ),
}

#: no    — no toca el índice
#: ann   — reconstruye el grafo HNSW (CPU, sin llamadas de embedding)
#: todo  — re-embebe el corpus entero (dinero)
_REINDEXA: dict[str, str] = {
    **dict.fromkeys([k for k, g in _GRADAS.items() if g <= 2], "no"),
    **dict.fromkeys(("hnsw_m", "hnsw_ef_construction", "distancia"), "ann"),
    **dict.fromkeys(
        (
            "troceado", "tam_fragmento", "solape", "contextualizar",
            "metadatos_prepend", "embedder", "embedder_dim",
        ),
        "todo",
    ),
}

#: Qué palancas abre cada diagnóstico del juez. Es el mapa que convierte
#: «algo va mal» en «toca esto».
DIAGNOSTICO_A_PALANCAS: dict[str, tuple[str, ...]] = {
    "cobertura": ("top_k", "top_k_por_carril", "reescritura", "fts_modo",
                  "filtro_tipo", "filtro_dominio", "troceado", "tam_fragmento",
                  # El carril de grafo es una respuesta a `cobertura`: el
                  # fragmento no llegó porque está a un salto, no porque el
                  # embedding fallara. Sin estas cinco aquí, el bucle no podía
                  # encender el grafo NUNCA — doce palancas construidas y
                  # ninguna alcanzable, que es la avería que este mapa existe
                  # para impedir, colada en el mapa mismo.
                  "carriles", "grafo_top_k", "grafo_semillas",
                  "enrutado", "comunidades_en_respuesta"),
    "ordenacion": ("peso_carril", "k_rrf", "reranker", "reranker_top_n",
                   "umbral_similitud", "pool_fusion", "grafo_alfa", "enrutado"),
    "sintesis": ("instrucciones", "pool_fusion", "filtro_tipo",
                 "comunidades_en_respuesta"),
    "prompt": ("instrucciones", "aprendizaje"),
}

#: Palancas que el bucle NO puede mover aunque sean baratas, con el motivo. Sin
#: esta lista, el assert de alcanzabilidad no distingue «se me olvidó
#: conectarla» de «está fuera a propósito», y esa distinción es justo la que
#: hace que el assert sirva de algo.
FUERA_DEL_BUCLE: dict[str, str] = {
    "analogia_min": "la ventana de analogías se calibra con rechazos firmados, "
                    "no optimizando una métrica de recuperación que no la mide",
    "analogia_max": "ídem",
    "idioma_fts": "cambiarlo obliga a recrear el índice GIN, y no es un ajuste "
                  "sino una decisión sobre el idioma del corpus",
    "solo_vigentes": "lo decide el enrutado por la FORMA de la consulta; "
                     "fijarlo global rompería R6 para todas",
    "ef_search": "afecta a la latencia de producción, no a la calidad medida",
    "ef_search_eval": "es la palanca gemela, solo para medir: subirla al medir "
                      "es lo que separa el sesgo del post-filtrado por época "
                      "del recall malo, y eso no se optimiza, se fija",
}

#: Palancas de GENERACIÓN. Un golden set sintético no ordena bien arquitecturas
#: de generación, así que estas el bucle las propone y las firma una persona.
FAMILIA_GENERACION = frozenset({"instrucciones"})

#: Qué entra en la huella del índice. Cambiar cualquiera de estas obliga a
#: reconstruir, y el nombre de la tabla deriva de este hash: servir contra un
#: índice desalineado deja de ser posible por construcción, no por disciplina.
INDEX_BOUND = (
    "troceado", "tam_fragmento", "solape", "contextualizar", "metadatos_prepend",
    "embedder", "embedder_dim", "distancia", "proveedor_embeddings",
)

#: La huella del ANN. Los mismos vectores, otro grafo.
GRAFO_BOUND = INDEX_BOUND + ("hnsw_m", "hnsw_ef_construction")


#: La configuración viva. El bucle edita ESTA línea y las de arriba.
PALANCAS = Palancas()


# --------------------------------------------------------------------------- #
# Huellas
# --------------------------------------------------------------------------- #


def proveedor_embeddings() -> str:
    """Entra en INDEX_BOUND a propósito: un índice construido en mock NUNCA
    puede confundirse con uno real."""
    return (os.getenv("EMBEDDINGS_PROVIDER") or "mock").strip().lower()


def huella(p: Palancas, campos: tuple[str, ...]) -> str:
    """sha256 sobre los campos nombrados, en orden canónico.

    Idea de rag-glue (`identidad.py`), reimplementada aquí en veinte líneas en
    vez de como dependencia de ruta a otro repo: una path dependency se rompe
    en cuanto una de las dos carpetas se mueve.

    Corrige el tercer fallo que rag-glue documenta de sí mismo: una clave
    AUSENTE no se descarta en silencio. Si `campos` nombra algo que no existe,
    revienta — un `tam_fragmneto` mal escrito dejaría la huella intacta mientras
    el troceado cambia, que es exactamente el fallo silencioso que la huella
    existe para impedir.
    """
    d = p.dict() | {"proveedor_embeddings": proveedor_embeddings()}
    if ausentes := [c for c in campos if c not in d]:
        raise KeyError(
            f"la huella nombra campos que no existen: {ausentes}. "
            "Descartarlos en silencio dejaría el hash intacto mientras la "
            "configuración cambia."
        )
    payload = json.dumps({c: d[c] for c in campos}, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()[:12]


def tabla_fragmentos(p: Palancas = PALANCAS) -> str:
    """El nombre de la tabla DERIVA de la huella del índice.

    Consecuencia deliberada: tocar una palanca de grada 3 apunta a una tabla que
    no existe todavía, así que el sistema no puede servir consultas contra un
    índice construido con otra configuración. Y la tabla anterior sigue viva,
    que es el rollback blue-green sin escribir una línea de rollback.
    """
    return f"fragmento_{huella(p, INDEX_BOUND)}"


# --------------------------------------------------------------------------- #
# Los asserts: fallos silenciosos convertidos en errores de import
# --------------------------------------------------------------------------- #

_CAMPOS = {f.name for f in fields(Palancas)}

_sin_grada = _CAMPOS - set(_GRADAS)
assert not _sin_grada, (
    f"Palancas sin grada asignada: {sorted(_sin_grada)}. Sin esto, grada_de() "
    "devuelve 4 por defecto y la palanca queda fuera del alcance del bucle EN "
    "SILENCIO, que es el fallo difícil de encontrar."
)

_sin_reindexa = _CAMPOS - set(_REINDEXA)
assert not _sin_reindexa, (
    f"Palancas sin clase de reindexado: {sorted(_sin_reindexa)}. El defecto sería "
    "'todo', y una palanca barata marcada como cara nunca se prueba."
)

_fantasmas = set(INDEX_BOUND) - _CAMPOS - {"proveedor_embeddings"}
assert not _fantasmas, (
    f"INDEX_BOUND nombra palancas inexistentes: {sorted(_fantasmas)}."
)

_familias = {familia(GENERADOR_PROBES), familia(SISTEMA), familia(JUEZ)}
assert len(_familias) == 3, (
    f"Los tres papeles usan {len(_familias)} familia(s) de modelo: {sorted(_familias)}. "
    "Tienen que ser tres distintas. El auto-reconocimiento CAUSA la "
    "auto-preferencia (Panickssery et al., NeurIPS 2024): si el juez y el sistema "
    "comparten modelo, el circuito se cierra sobre sí mismo y cada ronda confirma "
    "lo que a ese modelo le gusta de sí mismo. atlas-rai tiene este defecto por "
    "defecto (modelo == modelo_juez); aquí no arranca."
)

for _diag, _palancas in DIAGNOSTICO_A_PALANCAS.items():
    assert any(_GRADAS.get(p, 4) <= 2 for p in _palancas), (
        f"CENSURA DOBLE: el diagnóstico '{_diag}' no tiene ninguna palanca de "
        "grada 1 o 2. El bucle lo medirá ronda tras ronda sin poder corregirlo, "
        "agotará las cinco y concluirá «problema estructural». Instala la palanca "
        "que falta ANTES de correr."
    )
    _inexistentes = set(_palancas) - _CAMPOS
    assert not _inexistentes, (
        f"El diagnóstico '{_diag}' abre palancas que no existen: {sorted(_inexistentes)}. "
        "El bucle propondría cambios que nadie puede aplicar y los contaría como "
        "trabajo hecho."
    )

assert len(PALANCAS.carriles) == len(PALANCAS.peso_carril), (
    "peso_carril tiene que tener un valor por carril, en el mismo orden. Y con "
    f"{len(PALANCAS.carriles)} carril(es) y {len(PALANCAS.peso_carril)} peso(s) "
    "el `zip` descartaría el sobrante en silencio, que es cómo un carril acaba "
    "pesando 1,0 sin que nadie lo haya decidido."
)

_CARRILES_VALIDOS = {"denso", "lexico", "grafo"}
_carriles_raros = set(PALANCAS.carriles) - _CARRILES_VALIDOS
assert not _carriles_raros, (
    f"`carriles` nombra carriles que no existen: {sorted(_carriles_raros)}. "
    f"Los implementados son {sorted(_CARRILES_VALIDOS)}. Un carril inventado se "
    "salta en el bucle de recuperación sin decir nada y su peso queda huérfano."
)

# --- alcanzabilidad: toda palanca barata tiene que poder moverla el bucle ---
#
# El assert de censura doble comprueba la dirección fácil: que cada diagnóstico
# tenga alguna palanca barata. Este comprueba la difícil, y es la que faltaba:
# que cada palanca barata esté abierta por ALGÚN diagnóstico.
#
# Sin él se pueden construir doce palancas de grada 2 —el carril de grafo, el
# enrutado, las comunidades, el aprendizaje— y que el bucle no pueda tocar
# ninguna, porque nadie se acordó de añadirlas al mapa. Estarían en la tabla de
# palancas, tendrían grada, tendrían tests, y serían inalcanzables. Es
# exactamente «un parámetro que se lee como vivo y no lo está», dentro del
# fichero que existe para impedirlo. Pasó, y por eso este assert existe.
_alcanzables = {p for ps in DIAGNOSTICO_A_PALANCAS.values() for p in ps}
_baratas = {c for c in _CAMPOS if _GRADAS.get(c, 4) <= 2}
_huerfanas = _baratas - _alcanzables - set(FUERA_DEL_BUCLE) - FAMILIA_GENERACION
assert not _huerfanas, (
    f"Palancas de grada 1-2 que ningún diagnóstico abre: {sorted(_huerfanas)}. "
    "El bucle no puede moverlas nunca, así que construirlas no sirvió de nada. "
    "O las añades a DIAGNOSTICO_A_PALANCAS, o las declaras en FUERA_DEL_BUCLE "
    "con el motivo escrito. Lo que no vale es dejarlas colgando."
)

_fuera_inexistentes = set(FUERA_DEL_BUCLE) - _CAMPOS
assert not _fuera_inexistentes, (
    f"FUERA_DEL_BUCLE excluye palancas que no existen: {sorted(_fuera_inexistentes)}. "
    "Una exclusión sobre nada oculta que la palanca real sigue huérfana."
)

# --- la dirección inversa de las gradas: entradas fantasma ---
#
# `_sin_grada` comprueba que toda palanca tenga grada. Faltaba lo contrario: que
# toda grada corresponda a una palanca. Al borrar `grafo_activo` su entrada
# sobrevivió en `_GRADAS` y en `_REINDEXA` sin que nada se quejara — un
# parámetro fantasma en el único fichero cuyo propósito declarado es no tener
# ninguno.
_gradas_fantasma = set(_GRADAS) - _CAMPOS
assert not _gradas_fantasma, (
    f"_GRADAS asigna grada a palancas que no existen: {sorted(_gradas_fantasma)}."
)
_reindexa_fantasma = set(_REINDEXA) - _CAMPOS
assert not _reindexa_fantasma, (
    f"_REINDEXA nombra palancas que no existen: {sorted(_reindexa_fantasma)}."
)


# --------------------------------------------------------------------------- #
# Lo que NO existe aquí
# --------------------------------------------------------------------------- #
#
# Palancas que aparecen en la literatura de auto-mejora de RAG y que este repo
# NO tiene. Están escritas para que nadie las dé por disponibles al leer la
# lista de arriba: un bucle que cree tener palancas inexistentes produce
# propuestas inaplicables y las cuenta como trabajo hecho.
#
# ATENCIÓN AL LEER ESTE BLOQUE. Durante una sesión dijo «no hay grafo», «no hay
# comunidades» y «HyDE sin implementar» mientras las tres cosas existían 350
# líneas más arriba, en este mismo fichero. Y `.claude/commands/extender-rag.md`
# manda leerlo «en especial» para decidir qué construir: el comando que existe
# para decidir apuntaba al párrafo que mentía. Es la avería simétrica a la que el
# bloque previene —hacer creer que NO tienes una palanca que sí tienes— y es peor,
# porque lleva a reconstruir lo construido.
#
# Lo que de verdad no existe hoy:
#
# - RERANKER EJECUTADO. `reranker` tiene tres valores y solo se ha corrido con
#   `none`. El código de `local` y `cohere` está escrito y nunca ha corrido.
#
# - CONTEXTO SITUACIONAL FUNCIONANDO. `contextualizar=True` exige un `situador`
#   que no construye nadie: encender la palanca hoy es un ValueError en la
#   ingesta. Ver `ingesta/trocear.py`.
#
# - MULTI-CONSULTA. Descomponer una pregunta en varias y fusionar. `reescritura`
#   tiene el hook, y ningún modo lo hace.
#
# - COLBERT / interacción tardía multi-vector. Fuera de alcance a esta escala.
#
# - ROUTING APRENDIDO. `enrutado` es por REGLAS escritas a mano. Un clasificador
#   entrenado necesita meses de tráfico que un usuario no produce.
#
# Lo que SÍ existe y este bloque llegó a negar: carril de grafo con PPR propio
# (`cerebro/grafo.py`), comunidades por propagación de etiquetas
# (`cerebro/comunidades.py`), analogías cross-dominio (`cerebro/analogias.py`),
# topología (`cerebro/topologia.py`), HyDE en dos modos (`cerebro/reescritura.py`),
# enrutado por reglas (`cerebro/enrutador.py`) y aprendizaje
# (`cerebro/aprendizaje.py`). Todo ello descrito, con su medición y su estado de
# encendido, en `docs/06-fases-2-3-4.md`.
