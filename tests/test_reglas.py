"""Lo que fija cada test es su nombre. Nivel 0: sin red, sin claves, sin base."""

from __future__ import annotations

from cerebro.reglas import (
    ABSTENCION,
    abstiene,
    r1_cita,
    r2_abstencion,
    r4_literales,
    r7_estatus,
    r8_sin_relleno,
)


def frag(contenido: str, art: str = "art-uno") -> dict:
    return {"content": contenido, "meta_data": {"artefacto_id": art}}


# --- R1 -------------------------------------------------------------------- #

def test_r1_exige_al_menos_una_cita():
    ok, motivo = r1_cita("El índice no existe.", [frag("x")])
    assert not ok and "no cita" in motivo


def test_r1_rechaza_citar_un_artefacto_que_no_se_recupero():
    """Citar algo que no llegó es alucinar la fuente, que es peor que no citar:
    parece verificable y no lo es."""
    ok, motivo = r1_cita("Sí [[art:otro-id]].", [frag("x", "art-uno")])
    assert not ok and "otro-id" in motivo


def test_r1_acepta_una_cita_de_un_artefacto_recuperado():
    assert r1_cita("Sí [[art:art-uno]].", [frag("x", "art-uno")])[0]


def test_r1_no_aplica_a_una_abstencion():
    """Una abstención no tiene nada que citar; exigirle cita la haría imposible."""
    assert r1_cita(ABSTENCION, [])[0]


# --- R2 -------------------------------------------------------------------- #

def test_r2_exige_la_frase_literal():
    assert r2_abstencion(ABSTENCION, True)[0]
    assert not r2_abstencion("No lo sé.", True)[0]


def test_r2_rechaza_la_frase_con_cualquier_anadido():
    """El añadido es justo el fallo: «no lo tengo, pero puedo decirte que...»
    es la forma en que una abstención se convierte en una invención."""
    ok, motivo = r2_abstencion(f"{ABSTENCION} Pero quizá te sirva otra cosa.", True)
    assert not ok and "añade texto" in motivo


def test_r2_no_aplica_si_la_probe_no_es_fuera_de_alcance():
    assert r2_abstencion("Cualquier respuesta.", False)[0]


# --- R4 -------------------------------------------------------------------- #

def test_r4_detecta_una_version_inventada():
    ok, motivo = r4_literales("Es agno 2.8.5 [[art:a]].", [frag("agno 2.8.6")])
    assert not ok and "2.8.5" in motivo


def test_r4_acepta_una_version_que_si_esta():
    assert r4_literales("Es agno 2.8.6.", [frag("verificado contra agno 2.8.6")])[0]


def test_r4_detecta_un_redondeo():
    """«unos 35%» cuando la fuente dice 34,7% es exactamente el fallo que R4
    existe para atrapar: correcto de espíritu, inservible para actuar."""
    assert not r4_literales("Reduce un 35% los fallos.", [frag("reduce un 34,7%")])[0]


def test_r4_detecta_un_nombre_de_simbolo_inventado():
    ok, motivo = r4_literales("Sube hnsw.ef_query.", [frag("hnsw.ef_search")])
    assert not ok and "hnsw.ef_query" in motivo


# --- R7 -------------------------------------------------------------------- #

def test_r7_exige_marcar_lo_que_el_fragmento_marca_como_no_probado():
    ok, motivo = r7_estatus(
        "Escalará sin problema.", [frag("- Escalará sin problema [extrapolacion]")]
    )
    assert not ok and "no probada" in motivo


def test_r7_se_satisface_con_cualquier_marcador_de_la_lista():
    assert r7_estatus(
        "Escalará, pero es una extrapolación.", [frag("- Escalará [extrapolacion]")]
    )[0]


def test_r7_ignora_las_tildes_al_buscar_el_marcador():
    assert r7_estatus("Es extrapolacion.", [frag("- X [extrapolacion]")])[0]


def test_r7_no_aplica_si_nada_esta_marcado():
    assert r7_estatus("Cualquier cosa.", [frag("un hecho probado")])[0]


# --- R8 -------------------------------------------------------------------- #

def test_r8_detecta_relleno():
    ok, motivo = r8_sin_relleno("Claro, aquí tienes el dato: 42.")
    assert not ok and "relleno" in motivo


def test_r8_cuenta_frases():
    assert not r8_sin_relleno(". ".join(f"Frase {i}" for i in range(12)) + ".")[0]


def test_r8_no_cuenta_las_lineas_de_una_enumeracion():
    """R8 permite enumerar; contar cada viñeta como frase haría imposible
    responder a «lista los tres defectos»."""
    tabla = "Los defectos:\n" + "\n".join(f"- defecto {i}" for i in range(20))
    assert r8_sin_relleno(tabla)[0]


def test_r8_no_aplica_a_una_abstencion():
    assert r8_sin_relleno(ABSTENCION)[0]


# --- abstención ------------------------------------------------------------ #

def test_abstiene_normaliza_espacios():
    assert abstiene(f"  {ABSTENCION}  ")
    assert not abstiene(f"{ABSTENCION} Y algo más.")
