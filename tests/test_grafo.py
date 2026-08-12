"""
Lo que fija cada test es su nombre.

El carril de grafo, las comunidades y la topología son la fase 3 y 4, y llegan
apagados. Un módulo apagado sin pruebas es peor que uno inexistente: parece que
está y no se sabe si funciona. Estas pruebas corren **sin base de datos** —
`Grafo` es una lista de adyacencia en memoria— así que fijan el algoritmo, que
es la parte que se puede equivocar en silencio.
"""

from __future__ import annotations

import pytest

from cerebro.comunidades import propagar_etiquetas
from cerebro.grafo import (
    Grafo,
    camino,
    componentes,
    describir,
    distancia_media,
    entropia_grado,
    modularidad,
    ppr,
)
from cerebro.topologia import agujeros, puentes


def _grafo(*pares: tuple[str, str, float]) -> Grafo:
    """Construye un grafo NO dirigido: cada par mete las dos direcciones."""
    g = Grafo()
    for o, d, w in pares:
        g.vecinos.setdefault(o, {})[d] = w
        g.vecinos.setdefault(d, {})[o] = w
    return g


# --- PPR -------------------------------------------------------------------- #


def test_ppr_sin_semillas_devuelve_vacio_y_no_un_pagerank_global():
    """Un PageRank sin personalizar es un ranking de POPULARIDAD, y devolverlo
    cuando no hay semillas convertiría el carril en «los artefactos más
    conectados», que es relevancia falsa: la misma respuesta para toda consulta."""
    g = _grafo(("a", "b", 1.0), ("b", "c", 1.0))
    assert ppr(g, {}) == {}


def test_ppr_excluye_las_semillas_de_su_propio_resultado():
    """Las semillas ya las trajo el carril denso. Devolverlas aquí las contaría
    dos veces en la fusión RRF por un motivo que no es de contenido."""
    g = _grafo(("a", "b", 1.0), ("b", "c", 1.0))
    r = ppr(g, {"a": 1.0})
    assert "a" not in r
    assert set(r) <= {"b", "c"}


def test_ppr_puntua_mas_alto_lo_que_esta_mas_cerca_de_la_semilla():
    g = _grafo(("a", "b", 1.0), ("b", "c", 1.0), ("c", "d", 1.0))
    r = ppr(g, {"a": 1.0})
    assert r["b"] > r["c"] > r["d"]


def test_alfa_alto_se_queda_cerca_de_la_semilla_y_alfa_bajo_se_aleja():
    """`grafo_alfa` es la palanca que decide cuánto se aleja el paseo. Si esta
    prueba dejara de cumplirse, la palanca no estaría haciendo nada — que es
    exactamente el defecto que este repositorio persigue."""
    g = _grafo(("a", "b", 1.0), ("b", "c", 1.0), ("c", "d", 1.0), ("d", "e", 1.0))
    cerca = ppr(g, {"a": 1.0}, alfa=0.9)
    lejos = ppr(g, {"a": 1.0}, alfa=0.05)
    # Con alfa alto la masa se queda al lado; con alfa bajo llega más al fondo.
    assert lejos["e"] / lejos["b"] > cerca["e"] / cerca["b"]


def test_un_nodo_sin_salida_devuelve_su_masa_a_las_semillas_y_no_al_grafo():
    """Repartir la masa colgante entre todos los nodos inventaría aristas que no
    existen y rompería la personalización, que es el punto del algoritmo."""
    g = Grafo(vecinos={"a": {"b": 1.0}, "b": {}, "z": {}})
    r = ppr(g, {"a": 1.0})
    assert r.get("z", 0.0) == pytest.approx(0.0, abs=1e-9)


# --- estructura -------------------------------------------------------------- #


def test_componentes_trata_el_grafo_como_no_dirigido():
    g = Grafo(vecinos={"a": {"b": 1.0}, "b": {}, "c": {}})
    comps = componentes(g)
    assert {frozenset(c) for c in comps} == {frozenset({"a", "b"}), frozenset({"c"})}


def test_camino_encuentra_el_salto_intermedio_y_es_lo_que_permite_explicar():
    """Un resultado de PPR sin camino es un número. Con camino es una frase, y
    esa frase es la diferencia entre poder diagnosticar el carril y no poder."""
    g = _grafo(("a", "b", 1.0), ("b", "c", 1.0))
    assert camino(g, "a", "c") == ["a", "b", "c"]
    assert camino(g, "a", "z") is None


def test_modularidad_es_alta_con_dos_grupos_separados_y_casi_cero_en_un_grafo_completo():
    dos = _grafo(("a", "b", 1.0), ("b", "c", 1.0), ("a", "c", 1.0),
                 ("x", "y", 1.0), ("y", "z", 1.0), ("x", "z", 1.0),
                 ("c", "x", 0.1))
    part = {"a": 0, "b": 0, "c": 0, "x": 1, "y": 1, "z": 1}
    assert modularidad(dos, part) > 0.35

    completo = _grafo(*[(a, b, 1.0) for a in "abcd" for b in "abcd" if a < b])
    assert modularidad(completo, {"a": 0, "b": 0, "c": 1, "d": 1}) < 0.1


def test_entropia_de_grado_baja_cuando_un_nodo_lo_concentra_todo():
    """Un grafo concentrado hace que PPR devuelva siempre lo mismo, y esta cifra
    lo detecta antes de que lo haga el golden set."""
    estrella = _grafo(("c", "a", 1.0), ("c", "b", 1.0), ("c", "d", 1.0), ("c", "e", 1.0))
    regular = _grafo(("a", "b", 1.0), ("b", "c", 1.0), ("c", "d", 1.0), ("d", "a", 1.0))
    assert entropia_grado(estrella) < entropia_grado(regular)


def test_distancia_media_crece_con_la_cadena():
    corta = _grafo(("a", "b", 1.0), ("b", "c", 1.0), ("a", "c", 1.0))
    larga = _grafo(("a", "b", 1.0), ("b", "c", 1.0), ("c", "d", 1.0), ("d", "e", 1.0))
    assert distancia_media(larga) > distancia_media(corta)


def test_las_dos_cuentas_de_arista_no_son_la_misma_y_se_llaman_distinto():
    """`rag grafo` decía 108 y `rag topologia` decía 72 del mismo grafo: uno
    contaba filas (origen, destino, tipo) y el otro pares fusionados. Que las dos
    existan está bien; que se llamaran igual, no."""
    g = _grafo(("a", "b", 1.0), ("b", "c", 1.0))
    assert g.n_arcos == 4      # dirigidas
    assert g.n_aristas == 2    # no dirigidas
    assert describir(g)["densidad"] == pytest.approx(2 / 3)


# --- comunidades -------------------------------------------------------------- #


def test_la_particion_es_DETERMINISTA_entre_dos_llamadas_identicas():
    """La versión aleatoria de la propagación de etiquetas da particiones
    distintas en cada ejecución, y una comunidad que cambia entre dos corridas
    idénticas no se puede usar para medir nada."""
    g = _grafo(("a", "b", 1.0), ("b", "c", 1.0), ("a", "c", 1.0),
               ("x", "y", 1.0), ("y", "z", 1.0), ("x", "z", 1.0),
               ("c", "x", 0.1))
    assert propagar_etiquetas(g) == propagar_etiquetas(g)


def test_dos_grupos_separados_salen_como_dos_comunidades():
    g = _grafo(("a", "b", 1.0), ("b", "c", 1.0), ("a", "c", 1.0),
               ("x", "y", 1.0), ("y", "z", 1.0), ("x", "z", 1.0))
    part = propagar_etiquetas(g)
    assert part["a"] == part["b"] == part["c"]
    assert part["x"] == part["y"] == part["z"]
    assert part["a"] != part["x"]


def test_la_comunidad_cero_es_siempre_la_mayor():
    """Sin renumerar de forma estable, los identificadores bailarían entre
    corridas aunque la partición fuera idéntica, y el informe mentiría al
    comparar dos épocas."""
    g = _grafo(("a", "b", 1.0), ("b", "c", 1.0), ("a", "c", 1.0), ("c", "d", 1.0),
               ("x", "y", 1.0))
    part = propagar_etiquetas(g)
    tam: dict[int, int] = {}
    for c in part.values():
        tam[c] = tam.get(c, 0) + 1
    assert tam[0] == max(tam.values())


# --- topología ---------------------------------------------------------------- #


def test_un_puente_es_el_nodo_cuya_retirada_parte_el_grafo():
    g = _grafo(("a", "b", 1.0), ("b", "c", 1.0))
    assert [p["artefacto"] for p in puentes(g)] == ["b"]


def test_un_triangulo_no_tiene_puentes():
    g = _grafo(("a", "b", 1.0), ("b", "c", 1.0), ("a", "c", 1.0))
    assert puentes(g) == []


def test_un_agujero_es_un_par_de_comunidades_sin_ninguna_arista_entre_ellas():
    """Es donde una analogía valdría más, porque nadie la ha escrito todavía."""
    g = _grafo(("a", "b", 1.0), ("x", "y", 1.0))
    part = {"a": 0, "b": 0, "x": 1, "y": 1}
    ags = agujeros(g, part)
    assert len(ags) == 1
    assert ags[0]["comunidades"] == [0, 1]


def test_dos_comunidades_conectadas_no_son_un_agujero():
    g = _grafo(("a", "b", 1.0), ("x", "y", 1.0), ("b", "x", 0.1))
    assert agujeros(g, {"a": 0, "b": 0, "x": 1, "y": 1}) == []
