from unittest.mock import MagicMock, patch

import pytest

from mia.api.routes import query as query_routes
from mia.rag.llm import LLMAnswer
from mia.storage.models import Document, Domain, Unit
from mia.storage.vector_store import SearchResult


@pytest.fixture
def base(db, modes_config):
    with db() as session:
        session.add(Unit(id="u1", name="Computación"))
        session.flush()
        session.add(Domain(id="dom-1", unit_id="u1", name="Memoria del Consejo", description=""))
        session.flush()
        session.add(
            Document(id="doc-1", domain_id="dom-1", filename="acta.txt", source_type="txt", file_hash="h", status="done")
        )
        session.commit()


def test_sources_solo_incluye_fragmentos_por_encima_del_umbral(client, base, make_artifact):
    artefacto = make_artifact(units=["u1"])
    fake_vector_store = MagicMock()
    # Documento largo: no se incluye completo, solo los fragmentos relevantes y sus vecinos.
    fake_vector_store.count_chunks.return_value = 100
    fake_vector_store.search.return_value = [
        SearchResult(chunk_id="c1", document_id="doc-1", domain="dom-1", text="fragmento relevante", score=0.9),
        SearchResult(chunk_id="c2", document_id="doc-1", domain="dom-1", text="fragmento irrelevante", score=0.1),
    ]
    fake_embedding_provider = MagicMock()
    fake_embedding_provider.embed.return_value = [[0.1, 0.2]]
    fake_llm_provider = MagicMock()
    fake_llm_provider.answer.return_value = LLMAnswer(text="Respuesta basada en el fragmento relevante.")

    with (
        patch.object(query_routes, "get_vector_store", return_value=fake_vector_store),
        patch.object(query_routes, "get_embedding_provider", return_value=fake_embedding_provider),
        patch.object(query_routes, "get_llm_provider", return_value=fake_llm_provider),
    ):
        response = client.post(
            "/query", json={"domains": ["dom-1"], "question": "¿Qué se aprobó?"}, headers=artefacto.headers
        )

    assert response.status_code == 200
    body = response.json()
    assert len(body["sources"]) == 1
    assert body["sources"][0] == {
        "domain": "Memoria del Consejo",
        "document": "acta.txt",
        "excerpt": "fragmento relevante",
    }
    fake_llm_provider.answer.assert_called_once()
