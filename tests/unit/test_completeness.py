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


# --- Marca de continuación e instrucción de completitud -------------------------------------


def test_marca_de_continuacion():
    assert completeness.CONTINUES_MARKER == "[...el documento continúa]"
    assert completeness.mark_continuation("Texto.", True) == "Texto.\n[...el documento continúa]"
    assert completeness.mark_continuation("Texto.", False) == "Texto."


def test_instruccion_de_completitud():
    texto = completeness.COMPLETENESS_INSTRUCTIONS
    assert completeness.CONTINUES_MARKER in texto
    assert "lista" in texto and "no escribas" in texto.lower()
    assert chr(0x2014) not in texto


# --- Reintento de respuestas cortadas ----------------------------------------------------------


@pytest.mark.parametrize(
    "motivo, sin_informacion, esperado",
    [("length", False, True), ("other", False, True), ("stop", False, False), (None, False, False),
     ("length", True, False), ("other", True, False)],
)
def test_needs_retry(motivo, sin_informacion, esperado):
    assert completeness.needs_retry(motivo, sin_informacion) is esperado


def test_aviso_de_corte():
    assert completeness.CUT_NOTICE == "Aviso: la respuesta pudo quedar incompleta."
    assert completeness.with_notice("Texto.") == "Texto.\n\nAviso: la respuesta pudo quedar incompleta."
    ya = completeness.with_notice("Texto.")
    assert completeness.with_notice(ya) == ya  # no se repite


def test_merge_attempts_suma_el_uso_y_trata_los_nulos_como_cero():
    from mia.rag.llm import LLMAnswer

    primero = LLMAnswer(text="a", model="m1", prompt_tokens=100, completion_tokens=10, reasoning_tokens=None,
                        cost_usd=0.01, finish_reason="length")
    segundo = LLMAnswer(text="b", model="m2", prompt_tokens=100, completion_tokens=30, reasoning_tokens=5,
                        cost_usd=0.02, finish_reason="stop")
    junto = completeness.merge_attempts(primero, segundo)
    assert junto.text == "b" and junto.model == "m2" and junto.finish_reason == "stop"
    assert (junto.prompt_tokens, junto.completion_tokens, junto.reasoning_tokens) == (200, 40, 5)
    assert junto.cost_usd == pytest.approx(0.03)


def test_merge_attempts_sin_costo_en_ninguno_queda_nulo():
    from mia.rag.llm import LLMAnswer

    junto = completeness.merge_attempts(LLMAnswer(text="a"), LLMAnswer(text="b"))
    assert junto.cost_usd is None and junto.prompt_tokens is None
    uno = completeness.merge_attempts(LLMAnswer(text="a", cost_usd=0.01), LLMAnswer(text="b"))
    assert uno.cost_usd == pytest.approx(0.01)


def test_combine_notes():
    assert completeness.combine_notes(None, None) is None
    assert completeness.combine_notes("A", None) == "A"
    assert completeness.combine_notes("A", "B") == "A; B"
    assert completeness.NOTE_RETRIED == "Respuesta cortada: se reintentó"
    assert completeness.NOTE_NOTICE == "Respuesta cortada: se entregó con aviso"
