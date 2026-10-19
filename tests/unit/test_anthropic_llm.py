from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from mia.rag.llm import RagContext
from mia.rag.providers import anthropic_llm


def _respuesta(stop_reason, texto="Respuesta."):
    return SimpleNamespace(
        content=[SimpleNamespace(type="text", text=texto)],
        stop_reason=stop_reason,
        usage=SimpleNamespace(input_tokens=100, output_tokens=20),
    )


def _provider(mensaje):
    client = MagicMock()
    client.messages.create.return_value = mensaje
    with patch.object(anthropic_llm.anthropic, "Anthropic", return_value=client):
        return anthropic_llm.AnthropicLLMProvider(), client


@pytest.mark.parametrize(
    "motivo, esperado",
    [
        ("end_turn", "stop"),
        ("stop_sequence", "stop"),
        ("max_tokens", "length"),
        ("refusal", "other"),
        ("pause_turn", "other"),
        (None, None),
    ],
)
def test_informa_el_motivo_de_fin_de_la_generacion(motivo, esperado):
    provider, _ = _provider(_respuesta(motivo))
    assert provider.answer("¿?", []).finish_reason == esperado


def test_sin_el_campo_de_motivo_queda_desconocido():
    mensaje = SimpleNamespace(content=[SimpleNamespace(type="text", text="Ok.")], usage=None)
    provider, _ = _provider(mensaje)
    assert provider.answer("¿?", []).finish_reason is None


def test_envia_el_contexto_numerado_y_devuelve_el_uso():
    provider, client = _provider(_respuesta("end_turn", "Tiene 14 horas."))
    answer = provider.answer(
        "¿Cuántas horas?", [RagContext(domain="Planes", document="MC3010.docx", excerpt="14", reference=2)]
    )
    contenido = client.messages.create.call_args.kwargs["messages"][0]["content"]
    assert "[Fuente 2: dominio=Planes, documento=MC3010.docx]" in contenido
    assert (answer.text, answer.prompt_tokens, answer.completion_tokens) == ("Tiene 14 horas.", 100, 20)
