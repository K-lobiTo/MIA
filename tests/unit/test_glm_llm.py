from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from mia.rag.llm import RagContext
from mia.rag.providers import glm_llm


def test_glm_envia_contexto_y_pregunta_y_devuelve_el_texto():
    completion = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="Suman 12 créditos."))]
    )
    client = MagicMock()
    client.chat.completions.create.return_value = completion

    with patch.object(glm_llm, "OpenAI", return_value=client):
        provider = glm_llm.GLMLLMProvider()
        answer = provider.answer(
            "¿Cuántos créditos suman?",
            [RagContext(domain="Currículum", document="MC6102.pdf", excerpt="Créditos: 4")],
        )

    assert answer.text == "Suman 12 créditos."
    assert answer.model == "glm-5.3"
    kwargs = client.chat.completions.create.call_args.kwargs
    assert kwargs["model"] == "glm-5.3"
    assert kwargs["messages"][0]["role"] == "system"
    assert "MC6102.pdf" in kwargs["messages"][1]["content"]
    assert "¿Cuántos créditos suman?" in kwargs["messages"][1]["content"]
    assert kwargs["extra_body"] == {"thinking": {"type": "enabled"}}


def test_glm_usa_la_instruccion_recibida_como_mensaje_de_sistema():
    completion = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="Ok."))])
    client = MagicMock()
    client.chat.completions.create.return_value = completion

    with patch.object(glm_llm, "OpenAI", return_value=client):
        glm_llm.GLMLLMProvider().answer(
            "¿Cuánto?",
            [RagContext(domain="Planes", document="MC1.docx", excerpt="4")],
            instructions="Instrucción propia de la prueba.",
        )

    mensajes = client.chat.completions.create.call_args.kwargs["messages"]
    assert mensajes[0] == {"role": "system", "content": "Instrucción propia de la prueba."}


def test_glm_informa_el_motivo_de_fin_de_la_generacion():
    for motivo, esperado in (("stop", "stop"), ("length", "length"), (None, None)):
        completion = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="Ok."), finish_reason=motivo)]
        )
        client = MagicMock()
        client.chat.completions.create.return_value = completion
        with patch.object(glm_llm, "OpenAI", return_value=client):
            answer = glm_llm.GLMLLMProvider().answer("¿?", [RagContext(domain="P", document="D.docx", excerpt="x")])
        assert answer.finish_reason == esperado
