import logging

import pytest

from mia.rag import completeness


@pytest.fixture(autouse=True)
def _sin_avisos_previos():
    completeness._INVALID_VALUES_WARNED.clear()
    yield
    completeness._INVALID_VALUES_WARNED.clear()


# --- Opciones de encendido ----------------------------------------------------------------


@pytest.mark.parametrize("valor", ["on", "ON", "true", "True", "1", "yes", " on ", " TRUE\n"])
def test_switch_enabled_encendido(valor):
    assert completeness.switch_enabled(valor, "QUERY_X") is True


@pytest.mark.parametrize("valor", ["off", "OFF", "false", "0", "no", "", "  "])
def test_switch_enabled_apagado_sin_aviso(valor, caplog):
    with caplog.at_level(logging.WARNING, logger=completeness.__name__):
        assert completeness.switch_enabled(valor, "QUERY_X") is False
    assert caplog.records == []


def test_switch_enabled_invalido_apaga_y_avisa_una_vez_por_variable_y_valor(caplog):
    with caplog.at_level(logging.WARNING, logger=completeness.__name__):
        assert completeness.switch_enabled("quizas", "QUERY_A") is False
        assert completeness.switch_enabled("quizas", "QUERY_A") is False
        assert completeness.switch_enabled("quizas", "QUERY_B") is False
    avisos = [r.getMessage() for r in caplog.records]
    assert len(avisos) == 2 and "QUERY_A" in avisos[0] and "QUERY_B" in avisos[1]


def test_envoltorios_nombran_su_variable(caplog):
    with caplog.at_level(logging.WARNING, logger=completeness.__name__):
        assert completeness.complete_context_enabled("on") is True
        assert completeness.retry_cut_enabled("on") is True
        completeness.complete_context_enabled("x")
        completeness.retry_cut_enabled("x")
    nombres = " ".join(r.getMessage() for r in caplog.records)
    assert "QUERY_COMPLETE_CONTEXT" in nombres and "QUERY_RETRY_CUT_ANSWERS" in nombres


# --- Motivo de fin de la generación --------------------------------------------------------


@pytest.mark.parametrize(
    "crudo, tipo, esperado",
    [
        ("stop", "openai", "stop"),
        ("length", "openai", "length"),
        ("content_filter", "openai", "other"),
        ("tool_calls", "openai", "other"),
        ("end_turn", "anthropic", "stop"),
        ("stop_sequence", "anthropic", "stop"),
        ("max_tokens", "anthropic", "length"),
        ("refusal", "anthropic", "other"),
        (None, "openai", None),
        ("", "anthropic", None),
    ],
)
def test_normalize_finish_reason(crudo, tipo, esperado):
    from mia.rag.llm import normalize_finish_reason

    assert normalize_finish_reason(crudo, tipo) == esperado


def test_llm_answer_finish_reason_es_opcional():
    from mia.rag.llm import LLMAnswer

    assert LLMAnswer(text="x").finish_reason is None
