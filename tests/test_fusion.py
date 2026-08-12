"""Lo que fija cada test es su nombre."""

from __future__ import annotations

from cerebro.fusion import Hit, a_dicts, rrf


def hits(carril: str, ids: list[str], tipo: str = "cosine") -> list[Hit]:
    return [
        Hit(doc_id=d, contenido=f"texto de {d}", score=1.0 - i / 10,
            score_tipo=tipo, rango=i + 1, carril=carril, meta={"artefacto_id": d})
        for i, d in enumerate(ids)
    ]


def test_rrf_premia_lo_que_aparece_en_varios_carriles():
    """Es la propiedad entera del método: el consenso entre carriles gana a un
    primer puesto solitario."""
    fus = rrf([hits("denso", ["a", "b"]), hits("lexico", ["b", "c"])], top_k=3)
    assert fus[0].doc_id == "b"  # 2º y 1º, contra el 1º solitario de "a"


def test_la_constante_k_es_60_por_defecto():
    """Qdrant usa 2 y con otra fórmula: un umbral copiado de un ejemplo está
    sesgado si k no se fija explícitamente."""
    fus = rrf([hits("denso", ["a"])], top_k=1)
    assert fus[0].score_fusion == 1 / 61


def test_un_rango_cero_no_contribuye():
    """1/(k+0) daría a un no-resultado el peso del primer puesto."""
    h = Hit(doc_id="x", contenido="", score=None, score_tipo="cosine",
            rango=0, carril="denso")
    assert rrf([[h]], top_k=5) == []


def test_el_peso_por_carril_cambia_el_orden():
    dense = hits("denso", ["a", "b"])
    lex = hits("lexico", ["b", "a"], tipo="ts_rank_cd")
    sin_peso = rrf([dense, lex], top_k=2)
    con_peso = rrf([dense, lex], top_k=2, pesos={"lexico": 5.0})
    assert sin_peso[0].doc_id == "a"  # empate resuelto por doc_id
    assert con_peso[0].doc_id == "b"  # el léxico lo tenía primero


def test_se_conserva_el_rango_y_el_score_de_cada_carril():
    """Sin esto no se puede decir «la léxica lo tenía en el 3 y la vectorial en
    el 180», que es la única frase que distingue cobertura de ordenación."""
    fus = rrf([hits("denso", ["a", "b"]), hits("lexico", ["b"], tipo="ts_rank_cd")], top_k=2)
    b = next(r for r in fus if r.doc_id == "b")
    assert b.por_carril["denso"]["rango"] == 2
    assert b.por_carril["lexico"]["rango"] == 1
    assert b.por_carril["lexico"]["tipo"] == "ts_rank_cd"


def test_un_score_ausente_se_conserva_como_none_y_no_como_cero():
    """Un cero haría creer que el fragmento no se parecía en nada, cuando lo que
    pasó es que ese carril no puntúa."""
    h = Hit(doc_id="a", contenido="", score=None, score_tipo="ppr", rango=1, carril="grafo")
    fus = rrf([[h]], top_k=1)
    assert fus[0].por_carril["grafo"]["score"] is None


def test_el_orden_es_estable_ante_empates():
    """Dos corridas idénticas tienen que dar el mismo orden, o el ruido de
    medición incluye el desempate y contamina cada delta."""
    a = rrf([hits("denso", ["a", "b", "c"])], top_k=3)
    b = rrf([hits("denso", ["a", "b", "c"])], top_k=3)
    assert [x.doc_id for x in a] == [x.doc_id for x in b]


def test_a_dicts_expone_el_desglose_por_carril_al_juez():
    fus = rrf([hits("denso", ["a"])], top_k=1)
    d = a_dicts(fus)[0]
    assert d["meta_data"]["rango"] == 1
    assert d["meta_data"]["score_tipo"] == "rrf"
    assert "denso" in d["meta_data"]["por_carril"]
