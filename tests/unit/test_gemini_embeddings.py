from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from google.genai import errors

from mia.rag.providers import gemini_embeddings
from mia.rag.providers.gemini_embeddings import GeminiEmbeddingProvider


def _response(vectors):
    return SimpleNamespace(embeddings=[SimpleNamespace(values=v) for v in vectors])


def _provider(client):
    with patch.object(gemini_embeddings.genai, "Client", return_value=client):
        return GeminiEmbeddingProvider()


def test_embed_normaliza_y_distingue_consulta_de_documento():
    client = MagicMock()
    client.models.embed_content.return_value = _response([[3.0, 4.0]])
    provider = _provider(client)

    [vector] = provider.embed(["¿qué se aprobó?"], is_query=True)

    assert np.isclose(np.linalg.norm(vector), 1.0)
    assert client.models.embed_content.call_args.kwargs["config"].task_type == "RETRIEVAL_QUERY"


def test_embed_divide_en_lotes_de_100():
    client = MagicMock()
    client.models.embed_content.side_effect = lambda model, contents, config: _response(
        [[1.0, 0.0]] * len(contents)
    )
    provider = _provider(client)

    vectors = provider.embed([f"fragmento {i}" for i in range(250)])

    assert len(vectors) == 250
    assert [len(c.kwargs["contents"]) for c in client.models.embed_content.call_args_list] == [
        100,
        100,
        50,
    ]


def test_embed_reintenta_ante_cuota_agotada():
    client = MagicMock()
    client.models.embed_content.side_effect = [
        errors.ClientError(429, {"error": {"message": "RESOURCE_EXHAUSTED"}}),
        _response([[0.0, 2.0]]),
    ]
    provider = _provider(client)

    with patch.object(gemini_embeddings.time, "sleep") as sleep:
        [vector] = provider.embed(["acta"])

    sleep.assert_called_once()
    assert vector == [0.0, 1.0]


def test_embed_no_reintenta_otros_errores():
    client = MagicMock()
    client.models.embed_content.side_effect = errors.ClientError(
        400, {"error": {"message": "INVALID_ARGUMENT"}}
    )
    provider = _provider(client)

    with pytest.raises(errors.ClientError):
        provider.embed(["acta"])
