"""Búsqueda por palabras (feature 010): normalización, grupos de la pregunta, regla de la mayoría, fusión y notas.
Lógica pura: sin Qdrant, sin red."""

import logging
import math

import pytest

from mia.rag import lexical
from mia.rag.completeness import _INVALID_VALUES_WARNED
from mia.rag.lexical import (
    STOPWORDS,
    Equivalence,
    LexicalCandidate,
    LexicalGroup,
    failure_note,
    hybrid_enabled,
    hybrid_note,
    lexical_lookup,
    merge_hybrid,
    normalize,
    order_lexical,
    pick_candidates,
    query_groups,
    reset_lexical_state,
    warn_lexical_failure,
)
from mia.storage.vector_store import SearchResult

TFG = Equivalence("tfg", "trabajo final de graduacion")


@pytest.fixture(autouse=True)
def estado_limpio():
    reset_lexical_state()
    _INVALID_VALUES_WARNED.clear()
    yield
    reset_lexical_state()
    _INVALID_VALUES_WARNED.clear()


def terms(groups):
    return [g.terms for g in groups]


# --- Base ------------------------------------------------------------------------------------------


def test_normalize_quita_tildes_mayusculas_y_puntos_de_siglas():
    assert normalize("Sandí") == "sandi"
    assert normalize("T.F.G.") == "tfg"
    assert normalize("t.f.g") == "tfg"
    assert normalize("¿Qué es el T.F.G.?") == "¿que es el tfg?"
    assert normalize("") == ""


def test_normalize_no_separa_un_nombre_pegado_a_un_numero():
    assert lexical.words_of("Joseph Obando2023800202") == ["joseph", "obando2023800202"]


@pytest.mark.parametrize("valor", ["on", " ON ", "On"])
def test_hybrid_enabled_encendido(valor):
    assert hybrid_enabled(valor) is True


@pytest.mark.parametrize("valor", ["off", "", "OFF"])
def test_hybrid_enabled_apagado_sin_aviso(valor, caplog):
    with caplog.at_level(logging.WARNING):
        assert hybrid_enabled(valor) is False
    assert not [r for r in caplog.records if "QUERY_HYBRID_SEARCH" in r.getMessage()]


def test_hybrid_enabled_valor_invalido_apagado_y_avisa_una_vez(caplog):
    with caplog.at_level(logging.WARNING):
        assert hybrid_enabled("si") is False
        assert hybrid_enabled("si") is False
    avisos = [r for r in caplog.records if "QUERY_HYBRID_SEARCH" in r.getMessage()]
    assert len(avisos) == 1


def test_stopwords_incluyen_palabras_vacias_y_no_palabras_de_dominio():
    for palabra in ("quien", "que", "cual", "de", "la", "es"):
        assert palabra in STOPWORDS
    for palabra in ("tfg", "obando", "maestria", "curso"):
        assert palabra not in STOPWORDS


# --- Grupos de la pregunta -------------------------------------------------------------------------


def test_grupos_de_una_persona_sin_las_palabras_vacias():
    grupos = query_groups("¿Quién es Joseph Obando Sandí?", [], 8, 3)
    assert terms(grupos) == [("joseph",), ("obando",), ("sandi",)]


def test_grupos_descartan_cortas_duplicadas_y_respetan_el_maximo():
    assert terms(query_groups("tfg TFG de la ti ia plan", [], 8, 3)) == [("tfg",), ("plan",)]
    assert terms(query_groups("alfa beta gamma delta epsilon", [], 3, 3)) == [("alfa",), ("beta",), ("gamma",)]
    assert query_groups("¿Quién es el de la?", [], 8, 3) == []
    assert terms(query_groups("Natalia Soto Solís", [], 8, 3)) == [("natalia",), ("soto",), ("solis",)]
    assert terms(query_groups("¿Qué es el T.F.G.?", [], 8, 3)) == [("tfg",)]


# --- Expansión con equivalencias --------------------------------------------------------------------


def test_la_sigla_lleva_su_forma_desarrollada():
    grupos = query_groups("¿Qué líneas de TFG ofrece la maestría?", [TFG], 8, 3)
    assert terms(grupos) == [("lineas",), ("tfg", "trabajo final de graduacion"), ("maestria",)]


def test_la_forma_desarrollada_se_reemplaza_por_un_grupo_con_la_sigla():
    grupos = query_groups("¿Qué líneas de Trabajo Final de Graduación ofrece la maestría?", [TFG], 8, 3)
    assert terms(grupos) == [("lineas",), ("trabajo final de graduacion", "tfg"), ("maestria",)]
    # sus palabras no quedan como grupos sueltos
    assert ("trabajo",) not in terms(grupos) and ("graduacion",) not in terms(grupos)


def test_una_sigla_con_dos_formas_lleva_las_dos():
    otra = Equivalence("tfg", "tesis de grado")
    grupos = query_groups("TFG", [TFG, otra], 8, 3)
    assert terms(grupos) == [("tfg", "trabajo final de graduacion", "tesis de grado")]


def test_las_equivalencias_no_se_encadenan():
    a_b = Equivalence("aaa", "bbb ccc")
    b_c = Equivalence("bbb", "ddd eee")
    assert terms(query_groups("aaa", [a_b, b_c], 8, 3)) == [("aaa", "bbb ccc")]


def test_sin_equivalencia_la_sigla_no_se_relaciona_con_nada():
    assert terms(query_groups("¿Qué es el MGTI?", [TFG], 8, 3)) == [("mgti",)]
    assert terms(query_groups("trabajo final de graduacion", [], 8, 3)) == [
        ("trabajo",), ("final",), ("graduacion",)
    ]


def test_una_forma_parcial_no_activa_la_equivalencia():
    grupos = query_groups("trabajo final de la maestria", [TFG], 8, 3)
    assert ("tfg",) not in terms(grupos) and all("tfg" not in g.terms for g in grupos)
    assert terms(grupos) == [("trabajo",), ("final",), ("maestria",)]


def test_la_sigla_corta_de_una_equivalencia_no_se_filtra_por_largo():
    assert terms(query_groups("¿Qué es el ia?", [Equivalence("ia", "inteligencia artificial")], 8, 4)) == [
        ("ia", "inteligencia artificial")
    ]


# --- Búsqueda y regla de la mayoría -------------------------------------------------------------


def grupo(*terminos, ids=()):
    return LexicalGroup(terms=tuple(terminos), chunk_ids=frozenset(ids))


def ids(prefijo, n):
    return {f"{prefijo}{i}" for i in range(n)}


def test_lexical_lookup_une_las_alternativas_y_pide_un_fragmento_de_mas():
    llamadas = []

    class Almacen:
        def match_chunks(self, domains, text, limit):
            llamadas.append((tuple(domains), text, limit))
            return {"tfg": ["a", "b"], "trabajo final de graduacion": ["b", "c"], "x": []}[text]

    resultado = lexical_lookup(Almacen(), ["d1"], [grupo("tfg", "trabajo final de graduacion"), grupo("x")], 60)
    assert resultado[0].chunk_ids == frozenset({"a", "b", "c"})
    assert resultado[1].chunk_ids == frozenset()
    assert sorted(llamadas) == sorted(
        [(("d1",), "tfg", 61), (("d1",), "trabajo final de graduacion", 61), (("d1",), "x", 61)]
    )
    assert lexical_lookup(Almacen(), ["d1"], [], 60) == []


def test_lexical_lookup_deja_subir_la_excepcion_del_almacen():
    class Roto:
        def match_chunks(self, *args):
            raise RuntimeError("sin índice")

    with pytest.raises(RuntimeError):
        lexical_lookup(Roto(), ["d1"], [grupo("x")], 60)


@pytest.mark.parametrize(
    ("n", "necesita"), [(1, 1), (2, 2), (3, 2), (4, 3), (5, 3)]
)
def test_un_fragmento_pasa_con_mas_de_la_mitad_de_los_grupos_especificos(n, necesita):
    # El fragmento "ok" contiene exactamente `necesita` grupos; "corto" uno menos.
    grupos = [grupo(f"g{i}", ids=[f"x{i}"] + (["ok"] if i < necesita else []) + (["corto"] if i < necesita - 1 else []))
              for i in range(n)]
    candidatos = [c.chunk_id for c in pick_candidates(grupos, 60, 20).candidates]
    assert "ok" in candidatos
    assert "corto" not in candidatos


def test_un_grupo_ausente_cuenta_como_especifico_sin_coincidencias():
    # joseph (9), obando (3), sandi (0): el fragmento con joseph y obando alcanza 2 de 3.
    grupos = [grupo("joseph", ids=ids("j", 9) | {"carátula"}), grupo("obando", ids={"carátula", "k1", "k2"}),
              grupo("sandi")]
    resultado = pick_candidates(grupos, 60, 20)
    assert resultado.specific == 3
    assert [c.chunk_id for c in resultado.candidates] == ["carátula"]


def test_una_persona_inventada_no_deja_candidatos():
    # zacarias (0), fernandez (13), pizarro (0): nadie junta 2 de 3.
    grupos = [grupo("zacarias"), grupo("fernandez", ids=ids("f", 13)), grupo("pizarro")]
    resultado = pick_candidates(grupos, 60, 20)
    assert resultado.specific == 3 and resultado.candidates == []


def test_una_palabra_comun_queda_fuera_del_calculo():
    # luis aparece en 154 fragmentos: es común y no cuenta; quedan diego, cubillo y guevara.
    grupos = [grupo("luis", ids=ids("l", 61)), grupo("diego", ids={"c1", "d2"}), grupo("cubillo", ids={"c1"}),
              grupo("guevara", ids={"c1", "g2"})]
    resultado = pick_candidates(grupos, 60, 20)
    assert resultado.specific == 3
    assert [c.chunk_id for c in resultado.candidates] == ["c1"]
    assert resultado.groups[0].specific is False


def test_sin_grupos_especificos_no_hay_candidatos():
    resultado = pick_candidates([grupo("maestria", ids=ids("m", 100))], 60, 20)
    assert resultado.specific == 0 and resultado.candidates == []
    assert pick_candidates([], 60, 20).candidates == []


def test_orden_por_grupos_coincidentes_luego_peso_y_recorte_al_limite():
    grupos = [grupo("a", ids={"x", "y", "z"}), grupo("b", ids={"x", "y"}), grupo("c", ids={"x"})]
    resultado = pick_candidates(grupos, 60, 2)
    assert [c.chunk_id for c in resultado.candidates] == ["x", "y"]
    assert resultado.candidates[0].matched == 3 and resultado.candidates[1].matched == 2
    # el grupo más raro pesa más
    peso_raro = math.log(1 + 61 / 1)
    assert resultado.candidates[0].weight == pytest.approx(
        math.log(1 + 61 / 3) + math.log(1 + 61 / 2) + peso_raro
    )


def resultado(chunk_id, score=0.5, doc=None):
    return SearchResult(
        chunk_id=chunk_id, document_id=doc or f"doc-{chunk_id}", domain="d1", text=f"texto {chunk_id}",
        score=score, chunk_index=0,
    )


def test_order_lexical_desempata_por_coseno_y_descarta_lo_que_no_volvio():
    candidatos = [LexicalCandidate("a", 2, 1.0), LexicalCandidate("b", 2, 1.0), LexicalCandidate("fuera", 3, 5.0)]
    ordenados = order_lexical(candidatos, [resultado("a", 0.7), resultado("b", 0.9)])
    assert [r.chunk_id for r in ordenados] == ["b", "a"]


# --- Fusión --------------------------------------------------------------------------------------------


def test_sin_candidatos_lexicos_devuelve_la_misma_lista():
    vectores = [resultado("a", 0.9), resultado("b", 0.85)]
    asi = merge_hybrid(vectores, [], 8, 3, 60)
    assert asi is vectores
    assert [r.score for r in asi] == [0.9, 0.85]


def test_un_fragmento_en_las_dos_listas_aparece_una_vez_y_arriba():
    vectores = [resultado("a", 0.9), resultado("b", 0.85), resultado("c", 0.84)]
    lexicos = [resultado("c", 0.84)]
    final = merge_hybrid(vectores, lexicos, 8, 3, 60)
    assert [r.chunk_id for r in final] == ["c", "a", "b"]
    assert final[0].score == pytest.approx(1 / 61 + 1 / 63)


def test_los_solo_lexicos_ocupan_a_lo_sumo_las_ranuras_y_el_total_no_pasa_el_limite():
    vectores = [resultado(f"v{i}") for i in range(8)]
    lexicos = [resultado(f"l{i}") for i in range(5)]
    final = merge_hybrid(vectores, lexicos, 8, 3, 60)
    assert len(final) == 8
    assert len([r for r in final if r.chunk_id.startswith("l")]) <= 3
    sin_ranuras = merge_hybrid(vectores, lexicos, 8, 0, 60)
    assert [r.chunk_id for r in sin_ranuras] == [f"v{i}" for i in range(8)]


def test_la_fusion_devuelve_copias_con_el_valor_de_fusion_y_no_toca_los_originales():
    original = resultado("a", 0.9)
    lexico = resultado("l", 0.7)
    final = merge_hybrid([original], [lexico], 8, 3, 60)
    assert original.score == 0.9 and lexico.score == 0.7
    assert {r.chunk_id for r in final} == {"a", "l"}
    assert all(r is not original and r is not lexico for r in final)


def test_los_empates_conservan_el_orden_de_significado():
    vectores = [resultado("a"), resultado("b")]
    # b es el primero léxico (mismo aporte que a como primero de significado) pero a va antes por significado
    final = merge_hybrid(vectores, [resultado("b")], 8, 3, 60)
    assert [r.chunk_id for r in final] == ["b", "a"]
    final = merge_hybrid([resultado("a")], [resultado("l")], 8, 3, 60)
    assert [r.chunk_id for r in final] == ["a", "l"]


def test_sin_resultados_de_significado_entran_los_lexicos_hasta_las_ranuras():
    final = merge_hybrid([], [resultado("l1"), resultado("l2")], 8, 3, 60)
    assert [r.chunk_id for r in final] == ["l1", "l2"]


# --- Notas y avisos ----------------------------------------------------------------------------------------


def test_nota_con_candidatos_y_sin_ellos():
    outcome = lexical.LexicalOutcome(candidates=[LexicalCandidate("a", 2, 1.0), LexicalCandidate("b", 2, 1.0)])
    assert hybrid_note(outcome, 1) == "Búsqueda híbrida: 2 por palabras, 1 nuevos"
    assert hybrid_note(lexical.LexicalOutcome(), 0) is None
    assert failure_note() == "Búsqueda por palabras no disponible: se usó el significado"


def test_el_aviso_de_fallo_sale_a_lo_sumo_una_vez_por_minuto(caplog, monkeypatch):
    reloj = {"t": 1000.0}
    monkeypatch.setattr(lexical, "_now", lambda: reloj["t"])
    with caplog.at_level(logging.WARNING):
        warn_lexical_failure(RuntimeError("uno"))
        warn_lexical_failure(RuntimeError("dos"))
        reloj["t"] += 61
        warn_lexical_failure(RuntimeError("tres"))
    mensajes = [r.getMessage() for r in caplog.records if "búsqueda por palabras falló" in r.getMessage()]
    assert len(mensajes) == 2 and "uno" in mensajes[0] and "tres" in mensajes[1]
