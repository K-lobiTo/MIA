from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from mia.api.main import app
from mia.api.routes import query as query_routes
from mia.api.routes.query import NO_INFO_ANSWER
from mia.storage.vector_store import SearchResult


def test_sin_resultados_por_encima_del_umbral_no_llama_al_llm():
    fake_vector_store = MagicMock()
    fake_vector_store.count_chunks.return_value = 100
    fake_vector_store.search.return_value = [
        SearchResult(chunk_id="c1", document_id="doc-1", domain="dom-1", text="irrelevante", score=0.2),
    ]
    fake_embedding_provider = MagicMock()
    fake_embedding_provider.embed.return_value = [[0.1, 0.2]]
    fake_llm_provider = MagicMock()

    with (
        patch.object(query_routes, "get_vector_store", return_value=fake_vector_store),
        patch.object(query_routes, "get_embedding_provider", return_value=fake_embedding_provider),
        patch.object(query_routes, "get_llm_provider", return_value=fake_llm_provider),
    ):
        client = TestClient(app)
        response = client.post(
            "/query", json={"domains": ["dom-1"], "question": "¿Cuál es la capital de Mongolia?"}
        )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == NO_INFO_ANSWER
    assert body["sources"] == []
    fake_llm_provider.answer.assert_not_called()


def test_si_el_llm_indica_que_no_hay_informacion_no_se_listan_fuentes():
    fake_vector_store = MagicMock()
    fake_vector_store.count_chunks.return_value = 100
    fake_vector_store.search.return_value = [
        SearchResult(chunk_id="c1", document_id="doc-1", domain="dom-1", text="otro tema", score=0.95),
    ]
    fake_embedding_provider = MagicMock()
    fake_embedding_provider.embed.return_value = [[0.1, 0.2]]
    fake_llm_provider = MagicMock()
    fake_llm_provider.answer.return_value = " SIN_INFORMACION.\n"

    with (
        patch.object(query_routes, "get_vector_store", return_value=fake_vector_store),
        patch.object(query_routes, "get_embedding_provider", return_value=fake_embedding_provider),
        patch.object(query_routes, "get_llm_provider", return_value=fake_llm_provider),
    ):
        client = TestClient(app)
        response = client.post(
            "/query", json={"domains": ["dom-1"], "question": "¿Qué se acordó sobre Ciberseguridad?"}
        )

    assert response.status_code == 200
    assert response.json() == {"answer": NO_INFO_ANSWER, "sources": []}
