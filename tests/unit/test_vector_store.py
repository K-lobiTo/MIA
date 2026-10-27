from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from mia.storage import vector_store
from mia.storage.vector_store import QdrantVectorStore


def _store(client):
    with patch.object(vector_store, "QdrantClient", return_value=client):
        return QdrantVectorStore(url="http://qdrant", collection="mia_chunks")


def _collection_with_size(size):
    return SimpleNamespace(
        config=SimpleNamespace(params=SimpleNamespace(vectors=SimpleNamespace(size=size)))
    )


def test_ensure_collection_crea_indices_de_payload_para_filtrar():
    client = MagicMock()
    client.collection_exists.return_value = False

    _store(client).ensure_collection(384)

    client.create_collection.assert_called_once()
    indexed = {c.kwargs["field_name"] for c in client.create_payload_index.call_args_list}
    assert indexed == {"domain", "document_id", "chunk_index"}


def test_ensure_collection_existente_tambien_asegura_indices():
    client = MagicMock()
    client.collection_exists.return_value = True
    client.get_collection.return_value = _collection_with_size(384)

    _store(client).ensure_collection(384)

    client.create_collection.assert_not_called()
    assert client.create_payload_index.call_count == 3


def test_ensure_collection_falla_si_la_dimension_no_coincide():
    client = MagicMock()
    client.collection_exists.return_value = True
    client.get_collection.return_value = _collection_with_size(768)

    with pytest.raises(RuntimeError, match="dimensión 768"):
        _store(client).ensure_collection(384)


def test_count_chunks_filtra_por_documento():
    client = MagicMock()
    client.count.return_value = SimpleNamespace(count=9)

    assert _store(client).count_chunks("doc-1") == 9
    filtro = client.count.call_args.kwargs["count_filter"]
    assert filtro.must[0].key == "document_id"
    assert filtro.must[0].match.value == "doc-1"


def test_set_domain_cambia_el_dominio_de_los_fragmentos_de_un_documento_sin_tocar_vectores():
    client = MagicMock()

    _store(client).set_domain("doc-1", "dominio-nuevo")

    client.set_payload.assert_called_once()
    kwargs = client.set_payload.call_args.kwargs
    assert kwargs["collection_name"] == "mia_chunks"
    assert kwargs["payload"] == {"domain": "dominio-nuevo"}
    condition = kwargs["points"].must[0]
    assert condition.key == "document_id" and condition.match.value == "doc-1"
    client.upsert.assert_not_called()


def test_delete_document_borra_por_filtro_de_document_id_y_espera():
    client = MagicMock()

    _store(client).delete_document("doc-1")

    client.delete.assert_called_once()
    kwargs = client.delete.call_args.kwargs
    assert kwargs["collection_name"] == "mia_chunks"
    assert kwargs["wait"] is True
    condition = kwargs["points_selector"].filter.must[0]
    assert condition.key == "document_id" and condition.match.value == "doc-1"
    client.upsert.assert_not_called()


def test_delete_document_sin_fragmentos_no_falla():
    client = MagicMock()
    client.delete.return_value = SimpleNamespace(status="completed")

    _store(client).delete_document("sin-fragmentos")


def test_la_interfaz_base_no_sabe_eliminar_y_la_subclase_minima_sigue_instanciandose():
    from mia.storage.vector_store import VectorStore

    class Minimo(VectorStore):
        def ensure_collection(self, vector_size): ...
        def upsert(self, chunks): ...
        def search(self, query_embedding, domains, limit=5): ...
        def get_chunks(self, document_id, chunk_indexes): ...
        def count_chunks(self, document_id): ...
        def set_domain(self, document_id, domain_id): ...

    with pytest.raises(NotImplementedError):
        Minimo().delete_document("doc-1")
