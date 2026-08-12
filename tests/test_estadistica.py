"""Casos conocidos. Lo que fija cada test es su nombre."""

from __future__ import annotations

import math

import pytest

from evals.estadistica import (
    LINEA_ROJA,
    bootstrap_ic,
    descomponer_ruido,
    krippendorff_alpha,
    mcnemar_exacto,
    ruido,
    vuelcos,
    vuelcos_minimos_detectables,
)

# --- ruido ----------------------------------------------------------------- #


def test_corridas_identicas_dan_ruido_cero():
    r = ruido([0.8, 0.8, 0.8], n_probes=15)
    # approx, no ==: 0.8 no es exacto en binario y la varianza sale en 1e-16.
    assert r.sigma == pytest.approx(0.0, abs=1e-12) and r.aceptable


def test_el_umbral_de_aceptacion_nunca_baja_de_la_resolucion():
    """Con 15 probes la resolución es 0,067: un delta de 0,03 es indistinguible
    de cero por muchos decimales que tenga."""
    r = ruido([0.80, 0.80, 0.80], n_probes=15)
    assert r.umbral_de_aceptacion == pytest.approx(1 / 15)


def test_la_linea_roja_esta_en_2_sigma_y_vale_008():
    r = ruido([0.70, 0.80, 0.90], n_probes=100)
    assert r.dos_sigma == pytest.approx(2 * 0.1)
    assert not r.aceptable and LINEA_ROJA == 0.08


def test_una_sola_corrida_no_estima_ruido():
    with pytest.raises(ValueError):
        ruido([0.8], n_probes=10)


def test_descomponer_ruido_resta_en_cuadratura_y_no_baja_de_cero():
    gen, juez = descomponer_ruido(0.05, 0.03)
    assert gen == pytest.approx(math.sqrt(0.05**2 - 0.03**2))
    assert descomponer_ruido(0.02, 0.05)[0] == 0.0  # nunca negativo


# --- McNemar --------------------------------------------------------------- #


def test_sin_discordantes_no_hay_evidencia():
    assert mcnemar_exacto(0, 0) == 1.0


def test_mcnemar_es_simetrico():
    assert mcnemar_exacto(2, 7) == mcnemar_exacto(7, 2)


def test_un_solo_vuelco_no_es_significativo():
    """Un probe de quince no es señal. Es la regla del bucle, hecha número."""
    assert mcnemar_exacto(0, 1) == 1.0


def test_seis_vuelcos_limpios_si_lo_son():
    assert mcnemar_exacto(0, 6) == pytest.approx(2 * 0.5**6)
    assert mcnemar_exacto(0, 6) < 0.05


def test_el_minimo_detectable_son_seis_vuelcos():
    """El suelo honesto: por debajo de esto ninguna corrección lo cambia."""
    assert vuelcos_minimos_detectables(0.05) == 6


def test_vuelcos_ignora_lo_que_no_cambia():
    base = {"a": True, "b": False, "c": True, "d": False}
    cand = {"a": True, "b": True, "c": False, "d": False}
    b, c, mejoran = vuelcos(base, cand)
    assert (b, c) == (1, 1) and mejoran == ["b"]


# --- Krippendorff ---------------------------------------------------------- #


def test_acuerdo_perfecto_da_alpha_uno():
    u = [[1, 1], [0, 0], [1, 1], [0, 0]]
    assert krippendorff_alpha(u) == pytest.approx(1.0)


def test_desacuerdo_total_da_alpha_negativo():
    """Peor que el azar. Un α negativo no es un cero: es una señal de que el
    juez está sistemáticamente al revés."""
    u = [[1, 0], [0, 1], [1, 0], [0, 1]]
    assert krippendorff_alpha(u) < 0


def test_alpha_en_torno_a_cero_es_azar():
    u = [[1, 1], [1, 0], [0, 1], [0, 0]]
    assert abs(krippendorff_alpha(u)) < 0.4


def test_las_unidades_con_un_solo_valor_se_ignoran():
    """No informan sobre acuerdo; contarlas inflaría el n efectivo."""
    con_huecos = [[1, 1], [0, 0], [1, None], [None, 0]]
    sin_huecos = [[1, 1], [0, 0]]
    assert krippendorff_alpha(con_huecos) == pytest.approx(krippendorff_alpha(sin_huecos))


def test_sin_unidades_valorables_revienta_en_vez_de_devolver_un_numero():
    with pytest.raises(ValueError):
        krippendorff_alpha([[1, None], [None, 0]])


def test_todos_coinciden_en_un_unico_valor_da_alpha_uno():
    """Sin variación no hay desacuerdo esperado; dividir por cero daría NaN y
    un NaN en la puerta de la Fase 0 se lee como «no bloquea»."""
    assert krippendorff_alpha([[1, 1], [1, 1]]) == 1.0


# --- bootstrap ------------------------------------------------------------- #


def test_el_bootstrap_es_reproducible():
    """Dos corridas del informe tienen que dar el mismo intervalo, o el ruido de
    medición incluye el del propio bootstrap."""
    u = [[1, 1], [0, 0], [1, 0], [0, 0], [1, 1]]
    a = bootstrap_ic(u, krippendorff_alpha, n=200)
    b = bootstrap_ic(u, krippendorff_alpha, n=200)
    assert a == b


def test_el_intervalo_contiene_al_estimador_puntual():
    u = [[1, 1], [0, 0], [1, 1], [0, 0], [1, 0], [0, 1], [1, 1], [0, 0]]
    lo, hi = bootstrap_ic(u, krippendorff_alpha, n=500)
    assert lo <= krippendorff_alpha(u) <= hi
