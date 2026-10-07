from collections.abc import Iterator
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from mia.api.main import app
from mia.api.routes import query as query_routes
from mia.storage.db import get_session
from mia.storage.models import Base, Document, Domain
from mia.storage.vector_store import SearchResult


def _override_get_session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)

    with session_factory() as session:
        session.add(Domain(id="dom-1", name="Memoria del Consejo", description=""))
        session.add(
            Document(
                id="doc-1",
                domain_id="dom-1",
                filename="acta.txt",
                source_type="txt",
                file_hash="h",
                status="done",
            )
        )
        session.commit()

    def _get_session() -> Iterator[Session]:
        with session_factory() as session:
            yield session

    return _get_session


def test_sources_solo_incluye_fragmentos_por_encima_del_umbral(tmp_path):
    app.dependency_overrides[get_session] = _override_get_session(tmp_path)

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
    fake_llm_provider.answer.return_value = "Respuesta basada en el fragmento relevante."

    try:
        with (
            patch.object(query_routes, "get_vector_store", return_value=fake_vector_store),
            patch.object(query_routes, "get_embedding_provider", return_value=fake_embedding_provider),
            patch.object(query_routes, "get_llm_provider", return_value=fake_llm_provider),
        ):
            client = TestClient(app)
            response = client.post(
                "/query", json={"domains": ["dom-1"], "question": "¿Qué se aprobó?"}
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert len(body["sources"]) == 1
    assert body["sources"][0] == {
        "domain": "Memoria del Consejo",
        "document": "acta.txt",
        "excerpt": "fragmento relevante",
    }
    fake_llm_provider.answer.assert_called_once()
