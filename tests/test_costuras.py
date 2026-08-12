"""
Lo que fija cada test es su nombre. Y todos fijan una COSTURA.

Una auditoría externa encontró trece defectos graves y observó que la suite
—entonces 124 tests, todos en verde— no detectaba ninguno. No por descuido al
escribirlos: cada uno probaba **una pieza aislada**. El enrutador contra unas
palancas, la reescritura contra una cadena, PPR contra un grafo en memoria, RRF
contra listas. Todas correctas, todas verdes.

Los trece defectos vivían en las **junturas**: ingesta↔troceado, ingesta↔grafo,
traza↔grafo, enrutador↔recuperador, config↔recuperador, analogías↔grafo,
GEPA↔estadística. Y la observación que lo remata es que una suite construida así
**garantiza** no encontrarlos: verifica que cada pieza hace lo que promete, y
nunca que la siguiente lo recibe.

Estos tests van al otro lado. Ninguno prueba un algoritmo: cada uno prueba que
lo que una pieza escribe es lo que la siguiente lee. Casi todos fijan un fallo
que ocurrió de verdad, y lo dicen.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from cerebro.config import _GRADAS, DIAGNOSTICO_A_PALANCAS, FUERA_DEL_BUCLE, PALANCAS

# --------------------------------------------------------------------------- #
# config ↔ el resto: palancas que no las lee nadie
# --------------------------------------------------------------------------- #


def _fuentes() -> str:
    """El código del repo, concatenado. Sin tests: un uso solo en un test no es
    un uso — es una palanca que solo existe para su propia prueba."""
    from pathlib import Path

    raiz = Path(__file__).resolve().parent.parent
    partes = []
    for carpeta in ("cerebro", "evals", "ingesta", "scripts"):
        for f in sorted((raiz / carpeta).glob("*.py")):
            partes.append(f.read_text(encoding="utf-8"))
    partes.append((raiz / "tareas.py").read_text(encoding="utf-8"))
    return "\n".join(partes)


#: Palancas que el código consume de forma indirecta y que un grep por nombre no
#: encuentra. Cada excepción lleva su motivo: sin él, esta lista se convertiría
#: en el sitio donde se esconden las palancas muertas.
LEIDAS_INDIRECTAMENTE = {
    # Las consume `huella(p, tuple(sorted(p.dict())))`, que las nombra a todas
    # a la vez, y `tabla_fragmentos` vía INDEX_BOUND.
    "embedder_dim": "entra en la huella del índice y en el vector store",
    "hnsw_ef_construction": "lo consume `crear_indices` desde INDEX_BOUND",
    "hnsw_m": "ídem",
}


def test_toda_palanca_la_lee_ALGUIEN_fuera_de_config():
    """Una palanca que solo aparece en `config.py` no la mueve nadie.

    Es la avería literal que este repositorio persigue —«un parámetro que se lee
    como vivo y no lo está»— y ha ocurrido cuatro veces en el propio fichero que
    existe para impedirla: `grafo_activo`, `comunidades_en_respuesta`,
    `ef_search_eval` y `metadatos_prepend`, esta última de GRADA 3, la más cara
    que hay.
    """
    from dataclasses import fields

    fuentes = _fuentes()
    from pathlib import Path

    solo_config = (
        Path(__file__).resolve().parent.parent / "cerebro" / "config.py"
    ).read_text(encoding="utf-8")
    fuera_de_config = fuentes.replace(solo_config, "")

    huerfanas = [
        f.name
        for f in fields(PALANCAS)
        if f.name not in LEIDAS_INDIRECTAMENTE and f.name not in fuera_de_config
    ]
    assert not huerfanas, (
        f"Palancas que solo existen en config.py: {huerfanas}. O las lee alguien, "
        "o se borran, o se declaran en LEIDAS_INDIRECTAMENTE con su motivo."
    )


def test_toda_palanca_barata_la_puede_mover_el_bucle():
    """El assert de censura doble comprueba la dirección fácil —cada diagnóstico
    tiene alguna palanca barata— y durante un tiempo faltó la difícil. Se
    construyeron doce palancas de grada 2 que ningún diagnóstico abría: con
    grada, con tests, y estructuralmente inalcanzables."""
    from dataclasses import fields

    from cerebro.config import FAMILIA_GENERACION

    alcanzables = {p for ps in DIAGNOSTICO_A_PALANCAS.values() for p in ps}
    baratas = {f.name for f in fields(PALANCAS) if _GRADAS.get(f.name, 4) <= 2}
    huerfanas = baratas - alcanzables - set(FUERA_DEL_BUCLE) - FAMILIA_GENERACION
    assert not huerfanas, sorted(huerfanas)


# --------------------------------------------------------------------------- #
# enrutador ↔ recuperador
# --------------------------------------------------------------------------- #


def test_el_peso_que_pone_el_enrutado_llega_con_la_MISMA_longitud_que_carriles():
    """El enrutado devuelve unas palancas nuevas con `replace()`, y el assert de
    `config.py` solo cubre `PALANCAS` — no sus copias. Un `peso_carril` más
    corto que `carriles` reventaría el `zip(..., strict=True)` del recuperador
    FUERA de cualquier try, matando el turno entero."""
    from cerebro.enrutador import enrutar

    base = replace(
        PALANCAS,
        enrutado="reglas",
        carriles=("denso", "lexico", "grafo"),
        peso_carril=(1.0, 1.0, 1.0),
    )
    for consulta in (
        "¿Qué defectos he encontrado?",
        "¿sigue vigente lo del troceado?",
        "¿qué relación hay entre A y B?",
        "¿ef_search o ef_construction?",
        "una consulta cualquiera",
    ):
        r = enrutar(consulta, base)
        assert len(r.palancas.carriles) == len(r.palancas.peso_carril), (
            f"la regla '{r.regla}' devolvió {len(r.palancas.peso_carril)} pesos "
            f"para {len(r.palancas.carriles)} carriles"
        )


def test_el_enrutado_solo_nombra_carriles_que_existen():
    """La regla `multi_hop` pesaba un carril `grafo` que no estaba en `carriles`,
    y `con_peso` lo descartaba en silencio: el efecto principal de la regla no
    hacía nada."""
    from cerebro.enrutador import enrutar

    base = replace(PALANCAS, enrutado="reglas")
    for consulta in ("¿qué relación hay entre A y B?", "¿Qué he aprendido?"):
        r = enrutar(consulta, base)
        assert set(r.palancas.carriles) <= {"denso", "lexico", "grafo"}


# --------------------------------------------------------------------------- #
# ingesta ↔ troceado
# --------------------------------------------------------------------------- #


def test_metadatos_prepend_antepone_de_verdad_al_trocear():
    """La palanca es de GRADA 3: moverla cambia el nombre de la tabla y obliga a
    re-embeber el corpus entero pagando embeddings. Y no anteponía nada.

    La causa era una costura: `TextReader.read()` trocea DENTRO de `read`, y el
    envoltorio del pipeline pega los metadatos al documento DESPUÉS. Cuando
    `ConMetadatos.chunk` preguntaba, el diccionario estaba vacío. Ninguna prueba
    de la clase aislada podía verlo, porque aislada funciona.
    """
    from agno.knowledge.document.base import Document

    from ingesta.trocear import construir_troceado

    meta = {"titulo": "Un título", "tipo": "patron", "temas": ["rag", "grafos"]}
    estrategia = construir_troceado(PALANCAS, meta=meta)
    trozos = estrategia.chunk(Document(name="x", id="x", content="El cuerpo del texto."))

    assert trozos, "el troceado no devolvió nada"
    assert trozos[0].content.startswith("titulo: Un título"), trozos[0].content[:60]
    assert "temas: rag, grafos" in trozos[0].content


def test_sin_metadatos_el_troceado_no_inventa_una_cabecera_vacia():
    from agno.knowledge.document.base import Document

    from ingesta.trocear import construir_troceado

    t = construir_troceado(PALANCAS, meta={}).chunk(
        Document(name="x", id="x", content="Cuerpo.")
    )
    assert t[0].content.startswith("Cuerpo.")


# --------------------------------------------------------------------------- #
# traza ↔ grafo
# --------------------------------------------------------------------------- #


def test_el_grafo_lee_la_clave_que_la_traza_escribe_de_verdad():
    """`co_recuperado` leía `hit["meta"]["artefacto_id"]`. La traza escribe cada
    hit como `{doc_id, rango_fusion, score_fusion, por_carril, artefacto,
    devuelto}` — no hay clave `meta`. El set salía `{None}` y la quinta clase de
    arista, la única que aprende del tráfico real, no producía nunca nada.

    Este test compara las dos caras de la juntura leyendo el CÓDIGO, porque
    ejecutarlas exige base de datos y el fallo es de nombres, no de lógica.
    """
    from pathlib import Path

    raiz = Path(__file__).resolve().parent.parent
    escribe = (raiz / "cerebro" / "recuperador.py").read_text(encoding="utf-8")
    lee = (raiz / "cerebro" / "grafo.py").read_text(encoding="utf-8")

    # Lo que _guardar_traza mete en cada hit.
    assert '"artefacto":' in escribe, "la traza dejó de escribir `artefacto`"
    # Lo que co_recuperado busca.
    assert 'h.get("artefacto")' in lee, (
        "el grafo no lee `artefacto` de los hits de la traza"
    )
    assert 'h.get("meta"' not in lee, (
        "el grafo vuelve a leer una clave `meta` que la traza no escribe"
    )


# --------------------------------------------------------------------------- #
# analogías ↔ grafo
# --------------------------------------------------------------------------- #


def test_reconstruir_el_grafo_NO_cierra_las_aristas_firmadas():
    """`construir()` recalcula el grafo desde el corpus, y una analogía aceptada
    no está en el corpus: está en tu firma. Cerrarlas todas destruía cada noche
    —vía `rag jobs --nocturno`— el resultado del flujo entero: tres filtros, una
    llamada de LLM, una cola de revisión y una firma humana.

    Es el `SET`-tras-`MERGE` de Apache AGE que este repositorio cita como su
    cicatriz, reproducido dentro del módulo que lo cita.
    """
    from pathlib import Path

    src = (Path(__file__).resolve().parent.parent / "cerebro" / "grafo.py").read_text(
        encoding="utf-8"
    )
    i = src.index("set valido_hasta = now()")
    ventana = src[i : i + 260]
    assert "procedencia <> 'firmada'" in ventana, (
        "el cierre de aristas volvió a incluir las firmadas por una persona"
    )


def test_el_grafo_conoce_el_tipo_de_arista_que_las_analogias_escriben():
    """`analogias.resolver` inserta `tipo='analogia'`. Si `PESO_POR_TIPO` no la
    tiene, pasarla por `anota()` sería un KeyError — y hoy solo no explota
    porque los dos caminos no se cruzan."""
    from cerebro.grafo import PESO_POR_TIPO

    assert "analogia" in PESO_POR_TIPO


# --------------------------------------------------------------------------- #
# GEPA ↔ estadística
# --------------------------------------------------------------------------- #


def test_gepa_puede_promover_un_candidato_en_la_primera_ronda():
    """`mejor` se inicializaba sin `por_probe`, así que la ronda 1 comparaba cada
    candidato contra un dict vacío: `vuelcos({}, …)` da (0,0), McNemar da p=1,0,
    BH no rechaza nada, `mejor` no se actualiza — y como no se actualiza, tampoco
    adquiere `por_probe`. Trescientas líneas atascadas en la ronda 1 para
    siempre, devolviendo `propuesta: None` pasara lo que pasara.

    Aquí se fija la aritmética de la juntura, sin correr GEPA: con una base real
    y un candidato que mejora seis probes, McNemar tiene que detectarlo.
    """
    from evals.estadistica import benjamini_hochberg, mcnemar_exacto, vuelcos

    base = {f"P-{i:02d}": i > 6 for i in range(1, 21)}
    mejor_cand = {k: (v or int(k[2:]) <= 6) for k, v in base.items()}

    b, c, _ = vuelcos(base, mejor_cand)
    assert (b, c) == (0, 6), (b, c)
    p = mcnemar_exacto(b, c)
    assert p < 0.05, p
    rechazos, _ = benjamini_hochberg([p])
    assert rechazos == [True]


def test_comparar_contra_una_base_vacia_NO_detecta_nada_y_ese_era_el_fallo():
    """El caso que ocurría. Se fija para que quede claro que el (0,0) no era un
    empate: era una comparación que nunca se hizo."""
    from evals.estadistica import mcnemar_exacto, vuelcos

    assert vuelcos({}, {"P-01": True, "P-02": True})[:2] == (0, 0)
    assert mcnemar_exacto(0, 0) == 1.0


# --------------------------------------------------------------------------- #
# suelos ↔ juez
# --------------------------------------------------------------------------- #


def test_bajar_un_suelo_cambia_la_huella_del_juez():
    """El agujero más grande que ha tenido este repositorio. La doctrina decía
    que el escalón 6 está impedido porque el sha de `spec.md` entra en el digest
    — y los suelos, que son la función objetivo EJECUTABLE, vivían en
    `evals/correr.py`: ni denegado, ni hasheado. `SUELO_RECALL = 0.80` pasaba la
    puerta y la corrida seguía siendo «comparable»."""
    from pathlib import Path

    from cerebro.scorer import SUELOS_PY, JuezDeSpec

    antes = JuezDeSpec(usar_juez=False).digest()
    original = SUELOS_PY.read_text(encoding="utf-8")
    try:
        SUELOS_PY.write_text(
            original.replace("SUELO_RECALL = 0.85", "SUELO_RECALL = 0.80"),
            encoding="utf-8",
        )
        import importlib

        import cerebro.scorer as sc

        importlib.reload(sc)
        assert sc.JuezDeSpec(usar_juez=False).digest() != antes
    finally:
        SUELOS_PY.write_text(original, encoding="utf-8")
        import importlib

        import cerebro.scorer as sc

        importlib.reload(sc)
    _ = Path  # el import se usa arriba vía SUELOS_PY


def test_los_suelos_no_se_definen_en_el_arnes():
    """Si vuelven a `correr.py`, vuelve el agujero."""
    from pathlib import Path

    src = (Path(__file__).resolve().parent.parent / "evals" / "correr.py").read_text(
        encoding="utf-8"
    )
    # Al principio de línea: el fichero MENCIONA `SUELO_RECALL = 0.80` en el
    # comentario que explica por qué se movieron, y una subcadena suelta lo
    # confundía con una definición. Un detector que dispara con su propia
    # explicación es de la familia que este repositorio persigue.
    for linea in src.splitlines():
        assert not linea.startswith(("SUELO_RECALL", "SUELO_R6", "SUELOS_RECUENTO",
                                     "SUELO_P95_MS")), (
            f"un suelo volvió a definirse en `evals/correr.py`: {linea}"
        )


# --------------------------------------------------------------------------- #
# el modelo ↔ quien lo construye
# --------------------------------------------------------------------------- #


def test_nadie_le_pasa_unas_Palancas_a_construir_modelo():
    """`construir_modelo` toma un ID de modelo. Cuatro módulos le pasaban un
    `Palancas`, y con proveedor real hacía `Palancas.split('-')` → AttributeError.
    En `comunidades`, `analogias` y `gepa` no había try: `rag jobs --mensual` se
    caía entero en cuanto hubiera una clave. En mock no se veía porque
    `construir_modelo` retorna antes de tocar el argumento."""
    fuentes = _fuentes()
    malos = ("construir_modelo(p)", "construir_modelo(PALANCAS)",
             "construir_modelo(self.p)")
    for malo in malos:
        assert malo not in fuentes, f"alguien vuelve a llamar {malo}"


@pytest.mark.parametrize("mod", ["analogias", "comunidades", "reescritura"])
def test_los_modulos_que_usan_modelo_importan_el_ID_y_no_las_palancas(mod):
    from pathlib import Path

    src = (Path(__file__).resolve().parent.parent / "cerebro" / f"{mod}.py").read_text(
        encoding="utf-8"
    )
    assert "SISTEMA" in src


# --------------------------------------------------------------------------- #
# los disparadores ↔ el informe
# --------------------------------------------------------------------------- #


def test_el_disparador_se_lee_por_RECALL_y_no_por_tasa_de_aprobacion():
    """«`multi_hop` por debajo de 0,60» admitía dos lecturas con resultados
    OPUESTOS: tasa 0,43 (saltado) frente a recall 0,86 (no saltado). En un
    repositorio cuya tesis es «el disparador es una categoría cayendo, no una
    corazonada», eso era una corazonada con formato de número.

    Se resuelve por recall porque estas costuras son de RECUPERACIÓN, y la tasa
    de aprobación mezcla recuperación con generación: una probe puede fallar con
    recall 1,0 porque el modelo respondió mal.
    """
    from evals.disparadores import evaluar

    informe = {
        "probes": [
            # tasa de aprobación 0/3, recall perfecto: NO pide un grafo.
            {"id": f"P-{i}", "categoria": "multi_hop", "recall": 1.0,
             "pass_rate": 0.0}
            for i in range(6)
        ]
    }
    fila = next(f for f in evaluar(informe) if f["categoria"] == "multi_hop")
    assert fila["estado"] == "no", fila


def test_un_estrato_pequeno_es_NO_EVALUABLE_y_no_un_aprobado():
    """Con 4 probes, un umbral de 0,60 cae entre dos valores posibles del recall
    medio y el disparador sería un sorteo. Decir «no ha saltado» sería tan falso
    como decir que sí."""
    from evals.disparadores import evaluar

    informe = {
        "probes": [
            {"id": f"P-{i}", "categoria": "aggregation", "recall": 1.0}
            for i in range(4)
        ]
    }
    fila = next(f for f in evaluar(informe) if f["categoria"] == "aggregation")
    assert fila["estado"] == "no evaluable"


def test_la_cobertura_del_set_se_MIDE_y_no_se_estima_por_vocabulario():
    """La primera versión comparaba las palabras de la consulta con el título y
    contaba «saltos reales» cuando no solapaban: daba 10 sobre 7 probes, un
    falso positivo tranquilizador —«fingerprint» no casa con «env_fingerprint»
    aunque el carril denso los una sin dificultad—.

    Lo bueno ya estaba medido: si el recall de una probe sin grafo es 1,0, el
    grafo no puede mejorarla, y punto.
    """
    from evals.disparadores import cobertura_del_set

    todo_perfecto = {
        "probes": [
            {"id": f"P-{i}", "categoria": "multi_hop", "recall": 1.0} for i in range(7)
        ]
    }
    c = cobertura_del_set(todo_perfecto)
    assert c["con_margen"] == []
    assert "NINGUNA" in c["veredicto"]

    con_hueco = {
        "probes": [
            {"id": "P-01", "categoria": "multi_hop", "recall": 0.5},
            {"id": "P-02", "categoria": "multi_hop", "recall": 1.0},
        ]
    }
    assert [x["probe"] for x in cobertura_del_set(con_hueco)["con_margen"]] == ["P-01"]


def test_todo_disparador_dice_COMO_encender_su_costura():
    """«Saltó» sin decir qué tocar no es accionable, y el disparador acaba
    siendo un aviso que nadie sigue."""
    from evals.disparadores import COSTURAS

    for d in COSTURAS:
        assert d.encender and "=" in d.encender, d
        assert d.modulo.endswith(".py")
