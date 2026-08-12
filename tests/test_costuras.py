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

import os
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


# --------------------------------------------------------------------------- #
# el estudio de mutación ↔ el arnés
# --------------------------------------------------------------------------- #


def test_una_mutacion_de_orden_se_juzga_por_RANGO_y_no_por_recall():
    """`recall@k` es invariante al orden **por definición**: mide qué documentos
    están entre los k, no en qué posición. Juzgar una mutación que solo reordena
    con recall da siempre Δ=0, y el informe diría «ciego» cuando lo correcto es
    «esta métrica no puede verlo, y eso está bien».

    Un estudio de sensibilidad que confunde «no lo detecta» con «no lo mide» es
    el error que el estudio existe para encontrar en otros."""
    from evals.mutar import MUTACIONES

    por_nombre = {m.nombre: m for m in MUTACIONES}
    assert por_nombre["barajar"].metrica == "rango"
    for n in ("recortar", "descartar"):
        assert por_nombre[n].metrica == "recall", n


def test_apagar_un_carril_NO_es_una_mutacion_del_resultado():
    """Filtrar del top-k lo que un carril respaldaba en solitario daba Δ=0,00
    con 15 artefactos y con 55, y parecía insensibilidad brutal del arnés.

    Era un defecto de la mutación: **RRF premia el acuerdo**, así que coloca
    sistemáticamente al fondo lo que solo un carril trae, y filtrarlo del top-k
    quita casi nada POR CONSTRUCCIÓN. La mutación medía una propiedad de RRF y
    la llamaba ceguera.

    Una caída real cambia lo que se FUSIONA. Eso es un cambio de configuración,
    no una mutación del resultado, y el arnés ya sabe compararlo porque
    `carriles` es una palanca."""
    from evals.mutar import CARRILES_APAGADOS, MUTACIONES

    nombres = {m.nombre for m in MUTACIONES}
    assert "apagar_denso" not in nombres
    assert "apagar_lexico" not in nombres

    por_nombre = {n: c for n, _, c in CARRILES_APAGADOS}
    assert por_nombre["apagar_denso"] == ("lexico",)
    assert por_nombre["apagar_lexico"] == ("denso",)


def test_una_deteccion_en_curva_NO_monotona_no_cuenta():
    """Más daño tiene que dar más señal. Si no, lo que se mide es ruido, y un
    único «SÍ» dentro de una curva que sube y baja es la intensidad en la que la
    moneda salió cara."""
    from evals.mutar import _umbral_de_deteccion

    no_monotona = [
        {"mutacion": "x", "intensidad": 0.25, "delta": 0.0, "detectada": False},
        {"mutacion": "x", "intensidad": 0.50, "delta": 1.1, "detectada": True},
        {"mutacion": "x", "intensidad": 0.75, "delta": 0.6, "detectada": False},
        {"mutacion": "x", "intensidad": 1.00, "delta": 0.4, "detectada": False},
    ]
    u = _umbral_de_deteccion(no_monotona)
    assert u["monotonas"]["x"] is False
    assert u["minimo_detectado"] is None
    assert u["detecciones_no_creibles"] == ["x"]


def test_una_curva_monotona_SI_cuenta():
    from evals.mutar import _umbral_de_deteccion

    monotona = [
        {"mutacion": "y", "intensidad": 0.25, "delta": 0.1, "detectada": False},
        {"mutacion": "y", "intensidad": 0.50, "delta": 0.6, "detectada": True},
        {"mutacion": "y", "intensidad": 0.75, "delta": 1.4, "detectada": True},
    ]
    u = _umbral_de_deteccion(monotona)
    assert u["monotonas"]["y"] is True
    assert u["minimo_detectado"] == 0.50


def test_la_mutacion_tiene_semilla_fija():
    """Un estudio de sensibilidad irreproducible no mide la sensibilidad: mide
    la suerte."""
    from evals.mutar import SEMILLA, _descartar

    docs = [{"i": i} for i in range(20)]
    assert _descartar(0.5)(docs) == _descartar(0.5)(docs)
    assert isinstance(SEMILLA, int)


def test_recortar_al_cero_por_ciento_no_toca_nada():
    """La intensidad 0 tiene que ser la identidad, o la línea base del estudio
    no sería la línea base."""
    from evals.mutar import _descartar, _recortar

    docs = [{"i": i} for i in range(12)]
    assert _recortar(0.0)(docs) == docs
    assert _descartar(0.0)(docs) == docs


# --------------------------------------------------------------------------- #
# código que nadie llama
# --------------------------------------------------------------------------- #

#: Funciones públicas sin llamante en el código de producción, con su motivo.
#:
#: La lista existe por lo mismo que `FUERA_DEL_BUCLE`: sin ella, el test no
#: puede distinguir «se me olvidó conectarla» de «está aquí a propósito», y esa
#: distinción es la que hace que el test sirva de algo. Cada entrada tiene que
#: justificarse; una sin motivo es una función muerta escondida detrás de una
#: excepción.
SIN_LLAMANTE = {
    "cuped": "herramienta de barrido: se niega sola fuera de régimen y no hay "
             "barrido todavía. Sus tests fijan la negativa, que es su contrato",
    "successive_halving": "reparte presupuesto entre muchos candidatos y el "
                          "protocolo es una palanca por ronda: no hay barrido",
    "descomponer_ruido": "separa σ del juez de σ del generador, y hace falta un "
                         "juez real para tener las dos mitades",
    "registrar_decision": "el DecisionLog se escribe cuando el bucle corra una "
                          "ronda de verdad, y no ha corrido ninguna",
    "historial_decisiones": "lee el DecisionLog, que no escribe nadie porque el "
                            "bucle no ha corrido ninguna ronda todavía",
    "listar_vigentes": "API de consulta del almacén, para depurar a mano",
    "resumenes_vigentes": "los sirve el recuperador por su propia consulta; esta "
                          "es la versión para inspeccionar desde fuera",
    "es_mock": "predicado de conveniencia; el código comprueba el proveedor",
    "texto_a_embeber": "quedó superado por ConMetadatos, que hace el mismo "
                       "trabajo dentro del troceado. Candidata a borrarse",
    "json_seguro": "helper que se quedó sin uso al mover el volcado del informe "
                   "a su propio comando. Candidata a borrarse en la limpieza",
    "situador_llm": "lo construye `construir_troceado` cuando contextualizar "
                    "está encendido, y viene apagado",
    "reescribir": "la versión async de la reescritura: la usa el camino con "
                  "modelo, que hoy no corre sin clave",
    "estadisticas": "cuenta los disparos del enrutado sobre tráfico real, y no "
                    "hay tráfico real todavía",
    "comprobar_coherencia": "la llama `construir_embedder`, pero por su nombre "
                            "corto el contador de este test no lo ve",
    "medir_sigma": "punto de entrada de `rag puerta --sigma`",
    "preparar_casos": "punto de entrada de `rag puerta --casos`",
    "informe_texto": "punto de entrada de `rag disparadores`",
}


def test_ninguna_funcion_publica_esta_muerta_sin_motivo_escrito():
    """Una función sin llamante es código que parece vivo y no lo está.

    Es la misma avería que las palancas huérfanas, y el mismo remedio: o la
    llama alguien, o se borra, o se declara aquí con el porqué. Lo que no vale
    es dejarla colgando — cuando llegaron a ser once, ninguna se distinguía de
    las demás y todas parecían intencionadas.
    """
    import re
    from pathlib import Path

    raiz = Path(__file__).resolve().parent.parent
    fuentes = _fuentes()

    muertas = []
    for carpeta in ("cerebro", "evals", "ingesta"):
        for f in sorted((raiz / carpeta).glob("*.py")):
            texto = f.read_text(encoding="utf-8")
            for m in re.finditer(r"^def ([a-z][a-z0-9_]+)\(", texto, re.M):
                nombre = m.group(1)
                if nombre in SIN_LLAMANTE:
                    continue
                if fuentes.count(nombre) <= 1:
                    muertas.append(f"{carpeta}/{f.name}::{nombre}")

    assert not muertas, (
        f"Funciones públicas sin llamante y sin motivo: {muertas}. O las llama "
        "alguien, o se borran, o se declaran en SIN_LLAMANTE con el porqué."
    )


def test_las_excepciones_de_SIN_LLAMANTE_llevan_motivo():
    for nombre, motivo in SIN_LLAMANTE.items():
        assert len(motivo) > 25, f"{nombre}: el motivo es demasiado corto"


def test_no_hay_try_desnudo_sobre_trabajo_de_base_de_datos():
    """CLAUDE.md lo prohíbe como norma —«deja la transacción abortada y
    convierte el COMMIT en un ROLLBACK silencioso»— y el propio repositorio la
    incumplía en `_contar_fragmentos`. Se usa `punto_de_guardado`."""
    from pathlib import Path

    src = (
        Path(__file__).resolve().parent.parent / "ingesta" / "pipeline.py"
    ).read_text(encoding="utf-8")
    i = src.index("def _contar_fragmentos")
    assert "punto_de_guardado" in src[i : i + 1400]


def test_verificar_acepta_todo_proveedor_de_embeddings_que_el_sistema_conoce():
    """`rag verificar` no lleva su propia lista de proveedores: la pregunta.

    La llevaba, y al añadir `local` —el modelo de frases que corre en la
    máquina— el comprobador de coherencia se quedó diciendo «'local' no
    reconocido» sobre la configuración con la que el resto del repositorio
    llevaba días midiendo. La comprobación de arranque era la pieza sin
    comprobar.

    Se comprueba por CONDUCTA, no leyendo el fuente: se inventa un proveedor,
    se mete en `MODELOS`, y se exige que el verificador no lo rechace. Un test
    sobre el texto del fichero pasaría con una lista duplicada escrita de otra
    forma.
    """
    import cerebro.embeddings as emb
    import scripts.verificar as v

    inventado = "un-proveedor-que-no-existia-al-escribir-verificar"
    emb.MODELOS[inventado] = (None, 8)
    fallos: list[str] = []
    ok_linea, ok_env = v.linea, os.environ.get("EMBEDDINGS_PROVIDER")
    try:
        v.linea = lambda estado, txt, det=None: (
            fallos.append(txt) if estado == v.FALLO else None
        )
        os.environ["EMBEDDINGS_PROVIDER"] = inventado
        v.comprobar_proveedores()
    finally:
        v.linea = ok_linea
        del emb.MODELOS[inventado]
        if ok_env is None:
            os.environ.pop("EMBEDDINGS_PROVIDER", None)
        else:
            os.environ["EMBEDDINGS_PROVIDER"] = ok_env

    assert not fallos, (
        f"verificar rechazó un proveedor que `cerebro.embeddings` sí conoce: "
        f"{fallos}. La lista está duplicada otra vez, y el comprobador de "
        "coherencia vuelve a ser la pieza incoherente."
    )
