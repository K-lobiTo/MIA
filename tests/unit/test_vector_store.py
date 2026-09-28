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
    assert indexed == {"domain", "document_id"}


def test_ensure_collection_existente_tambien_asegura_indices():
    client = MagicMock()
    client.collection_exists.return_value = True
    client.get_collection.return_value = _collection_with_size(384)

    _store(client).ensure_collection(384)

    client.create_collection.assert_not_called()
    assert client.create_payload_index.call_count == 2


def test_ensure_collection_falla_si_la_dimension_no_coincide():
    client = MagicMock()
    client.collection_exists.return_value = True
    client.get_collection.return_value = _collection_with_size(768)

    with pytest.raises(RuntimeError, match="dimensión 768"):
        _store(client).ensure_collection(384)
