"""
Cada test lleva por nombre la afirmación que fija.

La suite crece por un motivo concreto, nunca persiguiendo cobertura. Es la
lección de las 918 pruebas podadas a 165 en el proyecto anterior, de las que
seis estaban fallando y sus defectos siguen sin arreglar: una suite que se poda
en bloque es una suite en la que nadie sabía qué aseveraba cada test.
"""

from __future__ import annotations

import pytest

from ingesta.contrato import Dominio, Madurez, RechazoAdmision, Tipo, admitir, sha_contenido

MINIMO = {
    "tipo": "nota-investigacion",
    "titulo": "Una nota cualquiera",
    "fecha": "2026-08-12",
    "temas": ["rag"],
    "dominio": "recuperacion",
}


def test_los_cinco_campos_requeridos_bastan():
    a = admitir(dict(MINIMO))
    assert a.tipo is Tipo.NOTA
    assert a.dominio is Dominio.RECUPERACION
    assert a.madurez is Madurez.SEMI  # el defecto es el conservador
    assert a.id is None  # lo deriva el normalizador


@pytest.mark.parametrize("falta", sorted(MINIMO))
def test_quitar_cualquier_campo_requerido_rechaza(falta):
    fm = {k: v for k, v in MINIMO.items() if k != falta}
    with pytest.raises(RechazoAdmision):
        admitir(fm)


def test_borrador_se_rechaza_en_admision():
    with pytest.raises(RechazoAdmision, match="borrador"):
        admitir(MINIMO | {"madurez": "borrador"})


def test_campo_derivado_puesto_a_mano_se_rechaza():
    """Un sha escrito por una persona no corresponde al contenido, y eso rompe
    la idempotencia sin lanzar ningún error."""
    with pytest.raises(RechazoAdmision, match="sha_contenido"):
        admitir(MINIMO | {"sha_contenido": "deadbeef"})
    with pytest.raises(RechazoAdmision, match="epoca"):
        admitir(MINIMO | {"epoca": 3})


def test_campo_mal_escrito_se_rechaza_en_vez_de_ignorarse():
    """`tema` por `temas` haría nacer el filtro vacío en silencio."""
    with pytest.raises(RechazoAdmision):
        admitir(MINIMO | {"tema": ["rag"]})


def test_teardown_sin_fuente_se_rechaza():
    with pytest.raises(RechazoAdmision, match="fuente"):
        admitir(MINIMO | {"tipo": "teardown-repo"})


def test_teardown_con_repo_sin_commit_se_rechaza():
    """Un teardown sin commit es inverificable, que es justo lo único que aporta."""
    fm = MINIMO | {
        "tipo": "teardown-repo",
        "fuentes": [{"tipo": "repo", "ref": "HKUDS/LightRAG"}],
    }
    with pytest.raises(RechazoAdmision, match="commit"):
        admitir(fm)


def test_teardown_con_commit_pasa():
    fm = MINIMO | {
        "tipo": "teardown-repo",
        "fuentes": [{"tipo": "repo", "ref": "HKUDS/LightRAG", "commit": "a1b2c3d"}],
    }
    assert admitir(fm).fuentes[0].commit == "a1b2c3d"


def test_extrapolacion_sin_verificable_por_se_rechaza():
    """Una extrapolación que no sabe cómo comprobarse es una conjetura, y esa
    es otra etiqueta. La distinción es la disciplina entera del corpus."""
    fm = MINIMO | {
        "afirmaciones": [{"texto": "esto escalará", "estado": "extrapolacion"}]
    }
    with pytest.raises(RechazoAdmision, match="verificable_por"):
        admitir(fm)


def test_extrapolacion_con_verificable_por_pasa():
    fm = MINIMO | {
        "afirmaciones": [
            {
                "texto": "esto escalará",
                "estado": "extrapolacion",
                "verificable_por": "p95 con 10x el corpus",
            }
        ]
    }
    assert admitir(fm).afirmaciones[0].verificable_por


def test_temas_se_normalizan_y_deduplican():
    a = admitir(MINIMO | {"temas": ["RAG", " rag ", "Grafos"]})
    assert a.temas == ["rag", "grafos"]


def test_id_con_mayusculas_o_espacios_se_rechaza():
    """El id aparece en las citas de las respuestas y es la clave de idempotencia."""
    for malo in ("Con Mayúsculas", "con espacios", "ab", "x" * 81):
        with pytest.raises(RechazoAdmision):
            admitir(MINIMO | {"id": malo})


def test_un_artefacto_no_puede_superarse_a_si_mismo():
    fm = MINIMO | {"id": "nota-uno", "supera": ["nota-uno"]}
    with pytest.raises(RechazoAdmision, match="superarse"):
        admitir(fm)


def test_el_sha_del_cuerpo_ignora_espacio_en_los_bordes():
    """Reindexar por un salto de línea de más es coste sin cambio."""
    assert sha_contenido("hola\n") == sha_contenido("  hola  ")
    assert sha_contenido("hola") != sha_contenido("adios")
