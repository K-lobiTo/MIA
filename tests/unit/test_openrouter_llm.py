from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from mia.rag.llm import RagContext
from mia.rag.providers import openrouter_llm


def _provider(client, **ajustes):
    valores = {"openrouter_model": "proveedor/modelo", "openrouter_reasoning_effort": "", **ajustes}
    with (
        patch.multiple(openrouter_llm.settings, **valores),
        patch.object(openrouter_llm, "OpenAI", return_value=client),
    ):
        return openrouter_llm.OpenRouterLLMProvider()


def _client(texto="Respuesta."):
    client = MagicMock()
    client.chat.completions.create.return_value = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=texto))]
    )
    return client


def test_envia_modelo_contexto_y_excluye_proveedores_que_entrenan():
    client = _client("Tiene 14 horas.")
    provider = _provider(client)

    with patch.multiple(
        openrouter_llm.settings,
        openrouter_model="proveedor/modelo",
        openrouter_reasoning_effort="",
        openrouter_zdr=False,
    ):
        answer = provider.answer(
            "¿Cuántas horas?", [RagContext(domain="Planes", document="MC3010.docx", excerpt="14")]
        )

    assert answer == "Tiene 14 horas."
    kwargs = client.chat.completions.create.call_args.kwargs
    assert kwargs["model"] == "proveedor/modelo"
    assert "MC3010.docx" in kwargs["messages"][1]["content"]
    assert kwargs["extra_body"] == {"provider": {"data_collection": "deny", "zdr": False}}


def test_con_esfuerzo_y_zdr_los_envia():
    client = _client()
    provider = _provider(client)

    with patch.multiple(
        openrouter_llm.settings,
        openrouter_model="proveedor/modelo",
        openrouter_reasoning_effort="medium",
        openrouter_zdr=True,
    ):
        provider.answer("¿?", [])

    extra = client.chat.completions.create.call_args.kwargs["extra_body"]
    assert extra["reasoning"] == {"effort": "medium"}
    assert extra["provider"]["zdr"] is True


def test_sin_modelo_configurado_falla_con_mensaje_claro():
    with pytest.raises(ValueError, match="OPENROUTER_MODEL"):
        _provider(_client(), openrouter_model="")
