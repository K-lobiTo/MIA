"""Reranker (feature 009): fábrica, selección por puntaje, notas, avisos y carga al arrancar. Sin modelos reales."""

import logging
import sys
from unittest.mock import MagicMock, patch

import pytest

from mia.config import settings
from mia.rag import rerank
from mia.rag.rerank import (
    RerankOutcome,
    RerankProvider,
    deadline_for,
    get_rerank_provider,
    rerank_candidates,
    rerank_note,
    sigmoid,
    warm_up_rerank_provider,
)
from mia.storage.vector_store import SearchResult


@pytest.fixture(autouse=True)
def estado_limpio():
    rerank.reset_rerank_state()
    yield
    rerank.reset_rerank_state()


def _r(indice, score=0.85):
    return SearchResult(
        chunk_id=f"c{indice}", document_id=f"d{indice}", domain="dom", text=f"texto {indice}", score=score,
        chunk_index=indice,
    )


# --- sigmoide ----------------------------------------------------------------------------------


def test_sigmoide():
    assert sigmoid(0) == 0.5
    assert sigmoid(10.95) > 0.9999
    assert sigmoid(-9.9) < 0.0001
    assert sigmoid(-1000) == 0.0 and sigmoid(1000) == 1.0  # sin desbordar


# --- fábrica -----------------------------------------------------------------------------------


@pytest.mark.parametrize("nombre", ["none", "", "NONE ", "  None"])
def test_none_no_devuelve_proveedor(nombre):
    assert get_rerank_provider(nombre) is None


def test_none_no_importa_el_modelo_local(monkeypatch):
    monkeypatch.delitem(sys.modules, "mia.rag.providers.local_rerank", raising=False)
    assert get_rerank_provider("none") is None
    assert "mia.rag.providers.local_rerank" not in sys.modules


def test_un_valor_invalido_es_none_y_avisa_una_vez(caplog):
    with caplog.at_level(logging.WARNING):
        assert get_rerank_provider("xyz") is None
        assert get_rerank_provider("xyz") is None
    avisos = [m for m in caplog.messages if "RERANK_PROVIDER" in m]
    assert len(avisos) == 1


def test_local_se_construye_una_vez():
    falso = MagicMock(spec=RerankProvider)
    with patch("mia.rag.providers.local_rerank.LocalRerankProvider", return_value=falso) as construir:
        assert get_rerank_provider("local") is falso
        assert get_rerank_provider("LOCAL") is falso
    assert construir.call_count == 1


def test_si_la_carga_falla_devuelve_none_y_no_reintenta():
    with patch("mia.rag.providers.local_rerank.LocalRerankProvider", side_effect=RuntimeError("sin archivo")) as construir:
        assert get_rerank_provider("local") is None
        assert get_rerank_provider("local") is None
    assert construir.call_count == 1


# --- selección ---------------------------------------------------------------------------------


def test_ordena_por_puntaje_y_reemplaza_el_score_sin_tocar_el_original():
    candidatos = [_r(1), _r(2), _r(3)]
    resultado = rerank_candidates(candidatos, [-3.0, 5.0, 0.5], min_score=0.0, limit=10)
    assert [r.chunk_id for r in resultado.results] == ["c2", "c3", "c1"]
    assert resultado.results[0].score == pytest.approx(sigmoid(5.0))
    assert [c.score for c in candidatos] == [0.85, 0.85, 0.85]  # los originales no cambian


def test_empates_conservan_el_orden_de_coseno():
    candidatos = [_r(1), _r(2), _r(3)]
    resultado = rerank_candidates(candidatos, [1.0, 1.0, 1.0], min_score=0.0, limit=10)
    assert [r.chunk_id for r in resultado.results] == ["c1", "c2", "c3"]


def test_descarta_bajo_el_minimo_y_recorta_al_limite():
    candidatos = [_r(i) for i in range(1, 6)]
    logits = [4.0, 3.0, 2.0, -4.0, -6.0]  # sigmoide: 0.98, 0.95, 0.88, 0.018, 0.002
    resultado = rerank_candidates(candidatos, logits, min_score=0.5, limit=2)
    assert [r.chunk_id for r in resultado.results] == ["c1", "c2"]
    assert resultado.passed == 3 and resultado.scored == 5 and resultado.min_score == 0.5
    assert resultado.best == pytest.approx(sigmoid(4.0)) and resultado.fell_back is False


def test_el_mejor_puntaje_cuenta_aunque_no_pase_el_minimo():
    resultado = rerank_candidates([_r(1), _r(2)], [-6.0, -9.0], min_score=0.5, limit=8)
    assert resultado.results == [] and resultado.passed == 0 and resultado.scored == 2
    assert resultado.best == pytest.approx(sigmoid(-6.0))


def test_lista_vacia_y_longitudes_distintas():
    vacio = rerank_candidates([], [], min_score=0.5, limit=8)
    assert vacio.results == [] and vacio.best is None and vacio.scored == 0
    with pytest.raises(ValueError):
        rerank_candidates([_r(1)], [1.0, 2.0], min_score=0.5, limit=8)


# --- notas -------------------------------------------------------------------------------------


def test_notas_de_uso():
    pasa = RerankOutcome(results=[], best=0.9871, scored=30, passed=3, min_score=0.5)
    assert rerank_note(pasa) == "Reranker: mejor 0.987, 3 de 30 sobre el mínimo 0.50"
    no_pasa = RerankOutcome(results=[], best=0.0031, scored=30, passed=0, min_score=0.5)
    assert rerank_note(no_pasa) == "Reranker: ninguno sobre el mínimo 0.50, mejor 0.003 de 30"
    cae = RerankOutcome(results=[], best=None, scored=0, passed=0, fell_back=True, min_score=0.5)
    assert rerank_note(cae) == "Reranker no disponible: se usó la similitud"
    minimo = RerankOutcome(results=[], best=0.0000004, scored=7, passed=0, min_score=0.5)
    assert "mejor 0.000 de 7" in rerank_note(minimo)
    for nota in (rerank_note(pasa), rerank_note(no_pasa), rerank_note(cae), rerank_note(minimo)):
        assert len(nota) <= 120


# --- tiempo y avisos ---------------------------------------------------------------------------


def test_deadline_segun_el_presupuesto(monkeypatch):
    monkeypatch.setattr(settings, "rerank_budget_ms", 50)
    assert deadline_for(10.0) == pytest.approx(10.05)
    monkeypatch.setattr(settings, "rerank_budget_ms", 0)
    assert deadline_for(10.0) is None


def test_el_aviso_de_fallo_sale_como_maximo_una_vez_por_minuto(caplog, monkeypatch):
    reloj = {"t": 1000.0}
    monkeypatch.setattr(rerank, "_now", lambda: reloj["t"])
    with caplog.at_level(logging.WARNING):
        rerank.warn_rerank_failure(RuntimeError("uno"))
        reloj["t"] += 10
        rerank.warn_rerank_failure(RuntimeError("dos"))
        reloj["t"] += 60
        rerank.warn_rerank_failure(RuntimeError("tres"))
    avisos = [m for m in caplog.messages if "reranker falló" in m]
    assert len(avisos) == 2 and "uno" in avisos[0] and "tres" in avisos[1]


# --- carga al arrancar -------------------------------------------------------------------------


def test_el_arranque_con_none_no_hace_nada(monkeypatch):
    monkeypatch.setattr(settings, "rerank_provider", "none")
    with patch.object(rerank, "get_rerank_provider") as fabrica:
        warm_up_rerank_provider()
    fabrica.assert_not_called()


def test_el_arranque_con_local_carga_y_registra_la_memoria(monkeypatch, caplog):
    monkeypatch.setattr(settings, "rerank_provider", "local")
    with (
        patch.object(rerank, "get_rerank_provider", return_value=MagicMock()) as fabrica,
        patch.object(rerank, "read_memory_mb", side_effect=[(260.0, 270.0), (414.0, 430.0)]),
        caplog.at_level(logging.INFO),
    ):
        warm_up_rerank_provider()
    fabrica.assert_called_once_with("local")
    assert any("Reranker cargado: RSS 260 -> 414 MB, pico 430 MB" in m for m in caplog.messages)


def test_el_arranque_no_lanza_si_la_carga_falla(monkeypatch):
    monkeypatch.setattr(settings, "rerank_provider", "local")
    with patch.object(rerank, "get_rerank_provider", side_effect=RuntimeError("boom")):
        warm_up_rerank_provider()  # no lanza
    with patch("mia.rag.providers.local_rerank.LocalRerankProvider", side_effect=RuntimeError("sin archivo")):
        warm_up_rerank_provider()
        assert get_rerank_provider("local") is None
