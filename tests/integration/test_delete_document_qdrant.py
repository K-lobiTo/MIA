"""Eliminación de los fragmentos de un documento contra un Qdrant real (feature 012). Se omite si no hay un Qdrant
local en MIA_TEST_QDRANT_URL (por defecto http://localhost:6333); usa una colección temporal."""

import os
import uuid

import pytest
from qdrant_client import QdrantClient

from mia.storage.vector_store import Chunk, QdrantVectorStore

URL = os.environ.get("MIA_TEST_QDRANT_URL", "http://localhost:6333")


def _cliente():
    try:
        client = QdrantClient(url=URL, timeout=3)
        client.get_collections()
        return client
    except Exception:  # noqa: BLE001
        return None


@pytest.fixture
def almacen():
    client = _cliente()
    if client is None:
        pytest.skip(f"No hay un Qdrant local en {URL}")
    nombre = f"mia_prueba_{uuid.uuid4().hex[:8]}"
    store = QdrantVectorStore(url=URL, collection=nombre)
    store.ensure_collection(4)
    yield store
    client.delete_collection(nombre)


def _chunk(documento, indice, dominio="d1"):
    return Chunk(
        id=str(uuid.uuid4()), document_id=documento, domain=dominio, text=f"texto {documento} {indice}",
        chunk_index=indice, embedding=[1.0, 0.0, 0.0, 0.0],
    )


def test_eliminar_un_documento_deja_los_fragmentos_de_los_demas(almacen):
    almacen.upsert([_chunk("doc-a", i) for i in range(5)] + [_chunk("doc-b", i) for i in range(3)])
    assert almacen.count_chunks("doc-a") == 5

    almacen.delete_document("doc-a")

    assert almacen.count_chunks("doc-a") == 0
    assert almacen.count_chunks("doc-b") == 3


def test_repetir_la_eliminacion_o_eliminar_un_documento_sin_fragmentos_no_falla(almacen):
    almacen.upsert([_chunk("doc-a", 0)])
    almacen.delete_document("doc-a")
    almacen.delete_document("doc-a")
    almacen.delete_document("nunca-existio")
    assert almacen.count_chunks("doc-a") == 0
