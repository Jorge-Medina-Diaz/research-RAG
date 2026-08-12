"""
Lo que fija cada test es su nombre.

Reescritura, enrutado y las tres funciones de barrido. Las tres piezas de la
fase 2 y del estado del arte diferido tienen la misma propiedad y por eso van
juntas: **todas se niegan a hacer algo cuando su condición no se cumple**, y esa
negativa es lo que las hace usables. Una reescritura que degrada en silencio,
una regla de enrutado que dispara siempre y un CUPED aplicado con n pequeño son
la misma avería con tres caras.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from cerebro.config import PALANCAS
from cerebro.enrutador import enrutar
from cerebro.reescritura import Reescrita, _expandir_lexico, reescribir_sinc
from evals.estadistica import benjamini_hochberg, cuped, successive_halving

RUTAS = replace(PALANCAS, enrutado="reglas")


# --- reescritura -------------------------------------------------------------- #


def test_la_expansion_ANADE_sinonimos_y_nunca_sustituye_el_termino_original():
    """Sustituir es el fallo más difícil de detectar que puede tener una
    reescritura: la búsqueda deja de encontrar lo que el usuario escribió y
    sigue devolviendo resultados plausibles."""
    fuera = _expandir_lexico("cuántos fragmentos devuelve")
    assert "fragmentos" in fuera
    assert "chunk" in fuera


def test_la_expansion_no_duplica_un_sinonimo_que_ya_estaba():
    assert _expandir_lexico("fragmento chunk").count("chunk") == 1


def test_con_reescritura_apagada_los_dos_carriles_reciben_lo_mismo():
    r = reescribir_sinc("una consulta", replace(PALANCAS, reescritura="none"))
    assert r.para_denso == r.para_lexico == "una consulta"
    assert r.modo == "none"


def test_los_modos_hyde_se_marcan_DIFERIDO_en_el_camino_sincrono():
    """Abrir un bucle de eventos dentro del recuperador rompería el que Agno ya
    tiene abierto. Que el modo diga `diferido` y no `none` importa: `none`
    significaría que la palanca no hizo nada, y no es eso lo que pasó."""
    r = reescribir_sinc("x", replace(PALANCAS, reescritura="hyde"))
    assert r.modo == "diferido"


def test_la_reescrita_lleva_su_modo_para_que_la_traza_no_mienta():
    r = Reescrita("a", "b", "expansion")
    assert r.modo == "expansion"


# --- enrutado ------------------------------------------------------------------ #


def test_con_el_enrutado_apagado_no_se_toca_nada():
    r = enrutar("lo que sea", PALANCAS)
    assert r.regla == "none"
    assert r.palancas is PALANCAS


def test_una_pregunta_de_agregacion_dobla_top_k():
    r = enrutar("¿Qué defectos he encontrado?", RUTAS)
    assert r.regla == "agregacion"
    assert r.palancas.top_k > PALANCAS.top_k


def test_una_pregunta_por_vigencia_APAGA_el_filtro_de_vigentes():
    """R6 pide nombrar el artefacto que superó a otro, y para nombrarlo hay que
    poder verlo. Con `solo_vigentes` puesto, el superado no llega y la regla es
    imposible de cumplir por construcción."""
    r = enrutar("¿sigue vigente lo que decía sobre el troceado?", RUTAS)
    assert r.regla == "temporal"
    assert r.palancas.solo_vigentes is False


def test_dos_simbolos_literales_hacen_mandar_al_carril_lexico_y_en_modo_AND():
    r = enrutar("¿ef_search o ef_construction?", RUTAS)
    assert r.regla == "lexico_exacto"
    assert r.palancas.fts_modo == "and"
    carriles = dict(zip(r.palancas.carriles, r.palancas.peso_carril, strict=False))
    assert carriles["lexico"] > carriles["denso"]


def test_una_consulta_normal_no_dispara_ninguna_regla():
    """Una regla que dispara siempre es un valor por defecto disfrazado."""
    assert enrutar("qué es una época", RUTAS).regla == "por_defecto"


def test_la_ruta_lleva_su_motivo_escrito():
    """Un enrutado sin motivo obliga a adivinar cuál de las cinco reglas fue."""
    r = enrutar("¿Qué he aprendido sobre medir?", RUTAS)
    assert r.porque and len(r.porque) > 10


# --- barridos ------------------------------------------------------------------ #


def test_bh_con_una_sola_comparacion_es_no_corregir():
    """Aplicar la corrección con n=1 solo añade una capa que hay que explicar."""
    rechazos, umbral = benjamini_hochberg([0.04])
    assert rechazos == [True]
    assert umbral == pytest.approx(0.05)


def test_bh_rechaza_menos_que_no_corregir_cuando_hay_muchas_comparaciones():
    ps = [0.001, 0.01, 0.04, 0.045, 0.049, 0.5]
    sin_corregir = sum(1 for x in ps if x <= 0.05)
    rechazos, _ = benjamini_hochberg(ps)
    assert sum(rechazos) < sin_corregir


def test_bh_nunca_rechaza_un_p_mayor_que_el_umbral_nominal():
    rechazos, _ = benjamini_hochberg([0.2, 0.3, 0.9])
    assert not any(rechazos)


def test_cuped_se_NIEGA_con_n_pequeno_y_dice_por_que():
    """Con n pequeño, theta sale confiadamente equivocado y ajustar con él
    AUMENTA la varianza mientras el número parece más limpio. Peor que no
    ajustar, porque no se nota."""
    y = [1.0, 2.0, 3.0, 4.0]
    x = [1.0, 2.0, 3.0, 4.0]
    fuera, theta, motivo = cuped(y, x)
    assert fuera == y
    assert theta == 0.0
    assert "n=4" in motivo


def test_cuped_se_niega_tambien_con_una_metrica_binaria():
    y = [0.0, 1.0] * 100
    x = [0.0, 1.0] * 100
    _, theta, motivo = cuped(y, x)
    assert theta == 0.0
    assert "binaria" in motivo


def test_cuped_reduce_la_varianza_cuando_su_condicion_SI_se_cumple():
    n = 200
    x = [float(i % 17) for i in range(n)]
    y = [2.0 * xi + (1.0 if i % 3 else -1.0) for i, xi in enumerate(x)]
    ajustada, theta, motivo = cuped(y, x)
    assert motivo == "aplicado"
    assert theta == pytest.approx(2.0, abs=0.2)

    def var(v):
        m = sum(v) / len(v)
        return sum((z - m) ** 2 for z in v) / (len(v) - 1)

    assert var(ajustada) < var(y)


def test_successive_halving_deja_UN_superviviente_y_es_el_mejor():
    notas = {"a": 0.1, "b": 0.9, "c": 0.4, "d": 0.5, "e": 0.2, "f": 0.7,
             "g": 0.3, "h": 0.6, "i": 0.8}
    fuera = successive_halving(
        list(notas), lambda c, n: notas[c], presupuesto=500, factor=3
    )
    assert fuera[0][0] == "b"


def test_successive_halving_nunca_evalua_por_debajo_del_suelo_de_deteccion():
    """Descartar con menos probes de las que hacen falta para detectar algo no
    es descartar: es sortear."""
    from evals.estadistica import vuelcos_minimos_detectables

    vistos: list[int] = []

    def evaluar(c, n):
        vistos.append(n)
        return 0.5

    successive_halving(list("abcdefghi"), evaluar, presupuesto=1, factor=3)
    assert min(vistos) >= vuelcos_minimos_detectables()


def test_successive_halving_con_la_lista_vacia_no_revienta():
    assert successive_halving([], lambda c, n: 0.0, presupuesto=10) == []
