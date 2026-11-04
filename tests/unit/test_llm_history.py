"""El mensaje al modelo con historial (feature 014): igual para todos los proveedores y idéntico al de siempre sin historial."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from mia.rag.history import HistoryTurn
from mia.rag.llm import (
    HISTORY_INSTRUCTIONS,
    RAG_SYSTEM_PROMPT,
    REASONING_SYSTEM_PROMPT,
    RagContext,
    build_user_message,
    format_context,
    instructions_with_history,
)
from mia.rag.providers import anthropic_llm, gemini_llm, glm_llm, openrouter_llm

CONTEXTO = [
    RagContext(
        domain="Admisión",
        document="Admision.txt",
        excerpt="Inicio de lecciones: 5 de octubre",
        reference=1,
    )
]
HISTORIAL = [
    HistoryTurn(
        question="¿Cuándo empiezan las lecciones?",
        answer="Inician el 5 de octubre.",
        mode="literal",
    ),
    HistoryTurn(
        question="¿Cuántos créditos suman los bloques 1 y 2?",
        answer="14 créditos.",
        mode="razonamiento",
    ),
]
PREGUNTA = "¿y cuánto cuesta?"


def test_sin_historial_el_mensaje_es_exactamente_el_de_siempre():
    bloque = format_context(CONTEXTO)

    esperado = f"Contexto:\n{bloque}\n\nPregunta: {PREGUNTA}"
    assert build_user_message(PREGUNTA, bloque, None) == esperado
    assert build_user_message(PREGUNTA, bloque, []) == esperado


def test_con_historial_el_bloque_va_antes_del_contexto_y_la_pregunta_al_final():
    bloque = format_context(CONTEXTO)

    mensaje = build_user_message(PREGUNTA, bloque, HISTORIAL)

    assert mensaje.startswith(
        "Conversación anterior (solo para entender la pregunta; no es una fuente de datos):"
    )
    assert (
        mensaje.index("Conversación anterior")
        < mensaje.index("Contexto:")
        < mensaje.index(f"Pregunta: {PREGUNTA}")
    )
    assert mensaje.endswith(f"Pregunta: {PREGUNTA}")
    assert "Inicio de lecciones: 5 de octubre" in mensaje.split("Contexto:")[1]
    assert (
        "Inicio de lecciones" not in mensaje.split("Contexto:")[0]
    )  # el historial no se mezcla con el contexto


@pytest.mark.parametrize("base", [RAG_SYSTEM_PROMPT, REASONING_SYSTEM_PROMPT])
def test_la_instruccion_con_historial_agrega_la_regla_de_que_no_es_fuente(base):
    con = instructions_with_history(base, HISTORIAL)

    assert con.startswith(base) and con.endswith(HISTORY_INSTRUCTIONS)
    for fragmento in ("solo sirve para entender", "nunca es fuente de datos", "únicamente"):
        assert fragmento in HISTORY_INSTRUCTIONS
    assert instructions_with_history(base, None) == base
    assert instructions_with_history(base, []) == base


def _openrouter(client):
    with (
        patch.multiple(
            openrouter_llm.settings, openrouter_model="m/m", openrouter_reasoning_effort=""
        ),
        patch.object(openrouter_llm, "OpenAI", return_value=client),
    ):
        return openrouter_llm.OpenRouterLLMProvider()


def _chat_client():
    client = MagicMock()
    client.chat.completions.create.return_value = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="Ok"), finish_reason="stop")]
    )
    return client


def _glm(client):
    with patch.object(glm_llm, "OpenAI", return_value=client):
        return glm_llm.GLMLLMProvider()


def _anthropic(client):
    with patch.object(anthropic_llm.anthropic, "Anthropic", return_value=client):
        return anthropic_llm.AnthropicLLMProvider()


def _gemini(client):
    with patch.object(gemini_llm.genai, "Client", return_value=client):
        return gemini_llm.GeminiLLMProvider()


def _mensajes_enviados(proveedor, historial):
    """El mensaje de usuario y la instrucción de sistema que cada proveedor manda al modelo."""
    nombre = type(proveedor).__name__
    if nombre == "OpenRouterLLMProvider":
        client = proveedor._client
        kwargs = client.chat.completions.create.call_args.kwargs
        return kwargs["messages"][1]["content"], kwargs["messages"][0]["content"]
    if nombre == "GLMLLMProvider":
        kwargs = proveedor._client.chat.completions.create.call_args.kwargs
        return kwargs["messages"][1]["content"], kwargs["messages"][0]["content"]
    if nombre == "AnthropicLLMProvider":
        kwargs = proveedor._client.messages.create.call_args.kwargs
        return kwargs["messages"][0]["content"], kwargs["system"]
    kwargs = proveedor._client.interactions.create.call_args.kwargs
    return kwargs["input"], kwargs["system_instruction"]


def _proveedores():
    openrouter_client = _chat_client()
    glm_client = _chat_client()
    anthropic_client = MagicMock()
    anthropic_client.messages.create.return_value = SimpleNamespace(
        content=[SimpleNamespace(type="text", text="Ok")], stop_reason="end_turn", usage=None
    )
    gemini_client = MagicMock()
    gemini_client.interactions.create.return_value = SimpleNamespace(output_text="Ok", usage=None)
    return [
        _openrouter(openrouter_client),
        _glm(glm_client),
        _anthropic(anthropic_client),
        _gemini(gemini_client),
    ]


def test_los_cuatro_proveedores_mandan_el_mismo_mensaje_con_historial_y_el_de_siempre_sin_el():
    bloque = format_context(CONTEXTO)
    esperado_con = build_user_message(PREGUNTA, bloque, HISTORIAL)
    esperado_sin = build_user_message(PREGUNTA, bloque, None)

    for proveedor in _proveedores():
        proveedor.answer(PREGUNTA, CONTEXTO, instructions=RAG_SYSTEM_PROMPT, history=HISTORIAL)
        mensaje, sistema = _mensajes_enviados(proveedor, HISTORIAL)
        assert mensaje == esperado_con, type(proveedor).__name__
        assert sistema == instructions_with_history(RAG_SYSTEM_PROMPT, HISTORIAL), type(
            proveedor
        ).__name__

    for proveedor in _proveedores():
        proveedor.answer(PREGUNTA, CONTEXTO, instructions=RAG_SYSTEM_PROMPT)
        mensaje, sistema = _mensajes_enviados(proveedor, None)
        assert mensaje == esperado_sin, type(proveedor).__name__
        assert sistema == RAG_SYSTEM_PROMPT, type(proveedor).__name__


def test_los_esqueletos_openai_y_local_aceptan_el_parametro_y_siguen_sin_implementar():
    from mia.rag.providers.local_llm import LocalLLMProvider
    from mia.rag.providers.openai_llm import OpenAILLMProvider

    for clase in (LocalLLMProvider, OpenAILLMProvider):
        with pytest.raises(NotImplementedError):
            clase().answer(PREGUNTA, CONTEXTO, history=HISTORIAL)
