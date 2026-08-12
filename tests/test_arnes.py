"""
Lo que fija cada test es su nombre.

Estas son las rutas que sostienen las cuatro propiedades del sistema y que
durante un rato no tuvieron ninguna prueba: la negativa a comparar, el suelo de
estrato, la caducidad de probes y el sello del juez.
"""

from __future__ import annotations

import pytest

from evals.correr import comparables, medible_en_nivel0, palancas_movidas
from evals.entorno import CATEGORIAS, cargar, suelo_de_estrato
from scripts.holdout import quitar_del_yaml

BASE = {"huella_config": "aaa", "epoca": 0, "huella_juez": "jjj"}


# --- la negativa a comparar ------------------------------------------------ #


def test_dos_corridas_identicas_son_comparables():
    assert comparables(BASE, dict(BASE))[0]


@pytest.mark.parametrize(
    ("clave", "otro", "trozo"),
    [
        ("epoca", 1, "sistema y corpus"),
        ("huella_juez", "kkk", "cambiar la regla"),
    ],
)
def test_cambiar_el_instrumento_o_el_objeto_impide_comparar(clave, otro, trozo):
    """La época mueve el objeto medido; el juez mueve la regla. Ninguna de las
    dos es un tratamiento, así que ninguna deja un delta atribuible."""
    ok, motivos = comparables(BASE | {clave: otro}, BASE)
    assert not ok
    assert trozo in " ".join(motivos)


def test_mover_UNA_palanca_si_es_comparable():
    """Es el caso central del bucle: si esto se negara, el bucle no podría
    comparar nunca. Una versión anterior lo negaba sobre el papel y solo
    seguía viva porque la huella no hasheaba `top_k`."""
    a = BASE | {"palancas": {"top_k": 12, "k_rrf": 60}}
    b = BASE | {"palancas": {"top_k": 20, "k_rrf": 60}}
    assert comparables(a, b)[0]
    assert palancas_movidas(a, b) == ["top_k"]


def test_mover_DOS_palancas_no_es_comparable():
    """«Una palanca por ronda» como código de salida, no como convención en un
    markdown que nadie ejecuta."""
    a = BASE | {"palancas": {"top_k": 12, "k_rrf": 60}}
    b = BASE | {"palancas": {"top_k": 20, "k_rrf": 10}}
    ok, motivos = comparables(a, b)
    assert not ok
    assert "k_rrf" in motivos[0] and "top_k" in motivos[0]


def test_el_motivo_dice_QUE_cambio_y_no_solo_que_algo_cambio():
    """Un «no comparable» sin causa obliga a adivinar, y adivinar en la puerta
    de aceptación es exactamente lo que la puerta existe para evitar."""
    _, motivos = comparables(BASE | {"epoca": 3}, BASE)
    assert "1" not in motivos[0] and "3" in motivos[0] and "0" in motivos[0]


# --- qué se puede medir sin LLM -------------------------------------------- #


def test_fuera_de_alcance_no_es_medible_en_nivel0():
    """Pregunta si el sistema se calla, y para eso hace falta que hable."""
    assert not medible_en_nivel0({"categoria": "fuera_de_alcance", "requiere": ["x"]})


def test_una_probe_sin_requiere_no_es_medible_en_nivel0():
    """Su recall sería trivialmente 1,0 y ensuciaría la media."""
    assert not medible_en_nivel0({"categoria": "single_hop", "requiere": []})
    assert not medible_en_nivel0({"categoria": "single_hop"})


def test_una_dependiente_con_requiere_si_es_medible():
    assert medible_en_nivel0({"categoria": "multi_hop", "requiere": ["a", "b"]})


# --- el freno --------------------------------------------------------------- #


def test_el_suelo_de_estrato_es_proporcional_con_minimo():
    """Un suelo fijo de 12 sobre un conjunto de 21 sería el 57 % y empujaría a
    escribir probes de relleno para pasar la puerta, que es peor que no tenerla."""
    assert suelo_de_estrato(60) == 12
    assert suelo_de_estrato(21) == 4
    assert suelo_de_estrato(5) == 4  # nunca por debajo del mínimo


# --- el golden set del repo ------------------------------------------------- #


def test_el_golden_set_carga_y_respeta_su_propio_contrato():
    probes = cargar()
    assert len(probes) >= 15
    assert {p["categoria"] for p in probes} == set(CATEGORIAS)


def test_toda_probe_fuera_de_alcance_declara_su_clave_negativa():
    """Sin ella no hay forma de detectar que ha caducado, y una probe caducada
    de esa categoría empuja al sistema a ser más evasivo."""
    for p in cargar():
        if p["categoria"] == "fuera_de_alcance":
            assert p.get("clave_negativa"), p["id"]


def test_el_estrato_de_freno_cumple_su_propio_suelo():
    probes = cargar()
    n = sum(1 for p in probes if p["categoria"] == "fuera_de_alcance")
    assert n >= suelo_de_estrato(len(probes))


# --- el sello del juez ------------------------------------------------------ #


def test_tocar_la_spec_cambia_el_digest_del_juez(tmp_path, monkeypatch):
    """Es el escalón 6 impedido por el tipo de dato: si el digest cambia, la
    huella cambia, y comparar con lo medido antes queda marcado como ilegal."""
    from cerebro import scorer as mod

    antes = mod.JuezDeSpec(usar_juez=False).digest()

    falsa = tmp_path / "spec.md"
    falsa.write_text("# spec relajada\n", encoding="utf-8")
    monkeypatch.setattr(mod, "SPEC", falsa)

    assert mod.JuezDeSpec(usar_juez=False).digest() != antes


def test_tocar_los_comprobadores_deterministas_tambien_cambia_el_digest(tmp_path, monkeypatch):
    """Cinco de las ocho reglas las decide `reglas.py`. Relajarlas sin que la
    huella se entere sería la puerta trasera del escalón 6."""
    from cerebro import scorer as mod

    antes = mod.JuezDeSpec(usar_juez=False).digest()
    falso = tmp_path / "reglas.py"
    falso.write_text("# comprobadores relajados\n", encoding="utf-8")
    monkeypatch.setattr(mod, "REGLAS_PY", falso)
    assert mod.JuezDeSpec(usar_juez=False).digest() != antes


# --- mover una probe al holdout --------------------------------------------- #

YAML_EJEMPLO = """\
# Un comentario que explica el fichero entero.
probes:
  # ---- categoría A ----
  - id: P-01
    categoria: single_hop
    consulta: primera

  - id: P-02
    categoria: temporal
    consulta: segunda
    reglas: [R1]

  # ---- el freno ----
  - id: P-03
    categoria: fuera_de_alcance
    consulta: tercera
"""


def test_mover_una_probe_conserva_los_comentarios():
    """`yaml.safe_dump` sobre el fichero entero los perdería todos, y aquí los
    comentarios son la mitad del valor: explican por qué existe cada categoría."""
    nuevo, quitadas = quitar_del_yaml(YAML_EJEMPLO, {"P-02"})
    assert quitadas == ["P-02"]
    assert "# Un comentario que explica el fichero entero." in nuevo
    assert "# ---- el freno ----" in nuevo
    assert "P-02" not in nuevo
    assert "P-01" in nuevo and "P-03" in nuevo


def test_mover_una_probe_se_lleva_su_bloque_entero_y_nada_mas():
    nuevo, _ = quitar_del_yaml(YAML_EJEMPLO, {"P-02"})
    assert "segunda" not in nuevo
    assert "reglas: [R1]" not in nuevo
    assert "primera" in nuevo and "tercera" in nuevo


def test_el_resultado_sigue_siendo_yaml_valido():
    import yaml

    nuevo, _ = quitar_del_yaml(YAML_EJEMPLO, {"P-01", "P-03"})
    datos = yaml.safe_load(nuevo)
    assert [p["id"] for p in datos["probes"]] == ["P-02"]


def test_pedir_una_probe_inexistente_no_toca_nada():
    nuevo, quitadas = quitar_del_yaml(YAML_EJEMPLO, {"P-99"})
    assert quitadas == [] and nuevo == YAML_EJEMPLO
