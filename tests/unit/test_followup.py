"""Seguimientos y reformulación de la búsqueda con el historial (feature 014): cuándo es un seguimiento y cómo se arma la
pregunta de búsqueda."""

import logging
from unittest.mock import MagicMock, patch

import pytest

from mia.config import settings
from mia.rag import followup
from mia.rag.followup import is_followup, rules_question, search_question, strategy
from mia.rag.history import HistoryTurn
from mia.rag.llm import LLMAnswer

ANALITICA = "¿Cuándo empiezan las lecciones de la maestría en analítica de negocio?"
HISTORIAL = [HistoryTurn(question=ANALITICA, answer="Inician el 5 de octubre de 2026.")]


def test_sin_historial_nunca_es_un_seguimiento():
    assert is_followup("¿y cuánto cuesta?", []) is False
    assert is_followup("¿y cuánto cuesta?", None) is False


@pytest.mark.parametrize(
    "pregunta",
    [
        "¿y cuánto cuesta?",
        "Y el costo",
        "pero cuándo",
        "Entonces, ¿cuánto?",
        "¿Qué requisitos tiene eso?",
        "¿Y esa cuánto dura?",
        "¿Cuándo es lo anterior?",
        "¿y el segundo?",
        "¿Cuál es el primero?",
        "¿cuánto cuesta?",  # corta y sin tema
        "¿Costo?",
    ],
)
def test_es_un_seguimiento_si_es_corta_o_continua_o_se_refiere_a_lo_anterior(pregunta):
    assert is_followup(pregunta, HISTORIAL) is True


@pytest.mark.parametrize(
    "pregunta",
    [
        "¿Cuándo empiezan las lecciones de la maestría en analítica de negocio?",
        "¿Cuántos estudiantes se aceptan en la maestría en ciberseguridad?",
        # Cambio de tema: corta, pero se entiende sola (trae su propio tema y no una referencia).
        "¿Cuándo es la matrícula?",
        "¿Cuál es el plan de estudios?",
        "¿Qué documentos necesito para aplicar?",
    ],
)
def test_una_pregunta_que_se_entiende_sola_no_es_un_seguimiento(pregunta):
    assert is_followup(pregunta, HISTORIAL) is False


def test_rules_junta_las_ultimas_dos_preguntas_anteriores_con_la_actual():
    historial = [HistoryTurn(f"pregunta {n}", f"respuesta {n}") for n in (1, 2, 3)]

    assert rules_question("¿y el costo?", historial) == "pregunta 2 pregunta 3 ¿y el costo?"
    assert rules_question("¿y el costo?", historial[:1]) == "pregunta 1 ¿y el costo?"


def test_rules_acota_a_400_caracteres_recortando_las_anteriores_nunca_la_actual():
    historial = [HistoryTurn("a" * 300, "x"), HistoryTurn("b " * 150, "x")]

    texto = rules_question("¿y el costo?", historial)

    assert len(texto) <= 400 and texto.endswith("¿y el costo?")
    assert (
        "aaa" not in texto
    )  # la pregunta más vieja se cortó por el inicio, sin dejar una palabra a medias
    assert texto.startswith("b b b")
    larga = "c" * 500
    assert (
        rules_question(larga, historial) == larga
    )  # una pregunta tan larga no se reformula: nunca se corta la actual


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [
        ("rules", "rules"),
        ("model", "model"),
        ("off", "off"),
        (" MODEL ", "model"),
        ("", "rules"),
        ("otra", "rules"),
    ],
)
def test_la_estrategia_se_lee_normalizada_y_una_desconocida_es_rules(valor, esperado, monkeypatch):
    assert strategy(valor) == esperado
    monkeypatch.setattr(settings, "history_reformulation", valor)
    assert strategy() == esperado  # sin argumento lee la configuración en cada llamada


# --- Estrategia con el modelo y despachador (US6) -----------------------------------------------------------------


def _proveedor(
    texto="¿Cuánto cuesta la Maestría en Analítica de Negocio?", costo=0.00005, tokens=(300, 20)
):
    proveedor = MagicMock()
    proveedor.rewrite.return_value = LLMAnswer(
        text=texto, model="m", prompt_tokens=tokens[0], completion_tokens=tokens[1], cost_usd=costo
    )
    return proveedor


@pytest.fixture
def con_proveedor(modes_config):
    """Un proveedor simulado en lugar del del modo literal."""

    def _usar(proveedor):
        return patch.object(followup, "get_llm_provider", return_value=proveedor)

    return _usar


def test_con_el_modelo_un_seguimiento_usa_la_pregunta_reescrita_y_devuelve_el_costo(con_proveedor):
    proveedor = _proveedor()
    with con_proveedor(proveedor):
        resultado = search_question("¿y cuánto cuesta?", HISTORIAL, "model")

    proveedor.rewrite.assert_called_once_with("¿y cuánto cuesta?", HISTORIAL)
    assert resultado.text == "¿Cuánto cuesta la Maestría en Analítica de Negocio?"
    assert resultado.used == "model"
    assert (resultado.cost_usd, resultado.prompt_tokens, resultado.completion_tokens) == (
        pytest.approx(0.00005),
        300,
        20,
    )


@pytest.mark.parametrize(
    "salida",
    ["", "   ", "dos\nlíneas", "abc", "x" * 301],
    ids=["vacia", "espacios", "varias_lineas", "muy_corta", "muy_larga"],
)
def test_una_reescritura_invalida_cae_a_las_reglas_con_un_aviso(con_proveedor, salida, caplog):
    with con_proveedor(_proveedor(texto=salida)), caplog.at_level(logging.WARNING):
        resultado = search_question("¿y cuánto cuesta?", HISTORIAL, "model")

    assert resultado.text == rules_question("¿y cuánto cuesta?", HISTORIAL)
    assert resultado.used == "rules"
    assert "reescritura" in caplog.text.lower()


def test_si_el_modelo_falla_o_no_reescribe_cae_a_las_reglas(con_proveedor, caplog):
    fallando = MagicMock()
    fallando.rewrite.side_effect = RuntimeError("timeout")
    sin_soporte = MagicMock()
    sin_soporte.rewrite.side_effect = NotImplementedError("no reescribe")

    for proveedor in (fallando, sin_soporte):
        with con_proveedor(proveedor), caplog.at_level(logging.WARNING):
            resultado = search_question("¿y cuánto cuesta?", HISTORIAL, "model")
        assert resultado.text == rules_question("¿y cuánto cuesta?", HISTORIAL)
        assert resultado.used == "rules" and resultado.cost_usd == 0


def test_una_pregunta_que_se_entiende_sola_no_llama_al_modelo_ni_con_off(con_proveedor):
    sola = "¿Cuántos créditos tiene el plan de la maestría en ciberseguridad?"
    proveedor = _proveedor()
    with con_proveedor(proveedor):
        modelo = search_question(sola, HISTORIAL, "model")
        apagada = search_question("¿y cuánto cuesta?", HISTORIAL, "off")
        sin_historial = search_question("¿y cuánto cuesta?", [], "model")

    proveedor.rewrite.assert_not_called()
    assert modelo.text == sola and modelo.used == "none"
    assert apagada.text == "¿y cuánto cuesta?" and apagada.used == "none"
    assert sin_historial.text == "¿y cuánto cuesta?"


def test_el_cambio_de_la_variable_rige_en_la_consulta_siguiente(con_proveedor, monkeypatch):
    proveedor = _proveedor()
    with con_proveedor(proveedor):
        monkeypatch.setattr(settings, "history_reformulation", "rules")
        reglas = search_question("¿y cuánto cuesta?", HISTORIAL)
        monkeypatch.setattr(settings, "history_reformulation", "model")
        modelo = search_question("¿y cuánto cuesta?", HISTORIAL)

    assert (reglas.used, modelo.used) == ("rules", "model")
    assert proveedor.rewrite.call_count == 1


def test_el_costo_de_la_reescritura_se_estima_si_el_proveedor_no_lo_informa(
    con_proveedor, monkeypatch
):
    monkeypatch.setattr(settings, "llm_price_in_literal", 1.0)
    monkeypatch.setattr(settings, "llm_price_out_literal", 2.0)
    with con_proveedor(_proveedor(costo=None, tokens=(1_000_000, 500_000))):
        resultado = search_question("¿y cuánto cuesta?", HISTORIAL, "model")

    assert resultado.cost_usd == pytest.approx(2.0)


def test_el_aviso_de_una_reescritura_invalida_no_copia_lo_que_dijo_el_modelo(con_proveedor, caplog):
    with (
        con_proveedor(_proveedor(texto="texto-del-modelo-77\nsegunda línea")),
        caplog.at_level(logging.DEBUG),
    ):
        search_question("¿y cuánto cuesta?", HISTORIAL, "model")

    assert "texto-del-modelo-77" not in caplog.text
