"""Métodos léxicos del almacén (feature 010) con un cliente de Qdrant simulado: filtros, índice de texto y valores
por defecto de la interfaz. Sin red."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from qdrant_client.models import (
    FieldCondition,
    HasIdCondition,
    MatchAny,
    MatchText,
    TokenizerType,
)

from mia.storage.vector_store import (
    TEXT_INDEX_PARAMS,
    QdrantVectorStore,
    SearchResult,
    VectorStore,
)


@pytest.fixture
def almacen():
    store = QdrantVectorStore.__new__(QdrantVectorStore)
    store.client = MagicMock()
    store.collection = "mia_prueba"
    return store


def _esquema(params=None, points=10):
    return SimpleNamespace(data_type=SimpleNamespace(value="text"), params=params, points=points)


def _coleccion(esquema=None, points_count=10):
    payload = {"text": esquema} if esquema is not None else {}
    return SimpleNamespace(payload_schema=payload, points_count=points_count)


def test_match_chunks_arma_el_filtro_de_dominios_mas_texto(almacen):
    almacen.client.scroll.return_value = ([SimpleNamespace(id="a"), SimpleNamespace(id="b")], None)
    ids = almacen.match_chunks(["d1", "d2"], "obando", 61)
    assert ids == ["a", "b"]
    kwargs = almacen.client.scroll.call_args.kwargs
    assert kwargs["collection_name"] == "mia_prueba"
    assert kwargs["limit"] == 61
    assert kwargs["with_payload"] is False and kwargs["with_vectors"] is False
    must = kwargs["scroll_filter"].must
    assert FieldCondition(key="domain", match=MatchAny(any=["d1", "d2"])) in must
    assert FieldCondition(key="text", match=MatchText(text="obando")) in must


def test_score_chunks_filtra_por_ids_y_dominios_y_devuelve_el_coseno(almacen):
    punto = SimpleNamespace(
        id="a", score=0.77,
        payload={"document_id": "doc", "domain": "d1", "text": "hola", "chunk_index": 2},
    )
    almacen.client.query_points.return_value = SimpleNamespace(points=[punto])
    resultados = almacen.score_chunks([0.1, 0.2], ["d1"], ["a", "b"])
    assert resultados == [SearchResult("a", "doc", "d1", "hola", 0.77, 2)]
    kwargs = almacen.client.query_points.call_args.kwargs
    assert kwargs["query"] == [0.1, 0.2] and kwargs["limit"] == 2
    must = kwargs["query_filter"].must
    assert HasIdCondition(has_id=["a", "b"]) in must
    assert FieldCondition(key="domain", match=MatchAny(any=["d1"])) in must


def test_score_chunks_sin_ids_no_llama_a_qdrant(almacen):
    assert almacen.score_chunks([0.1], ["d1"], []) == []
    almacen.client.query_points.assert_not_called()


def test_los_parametros_del_indice_de_texto():
    assert TEXT_INDEX_PARAMS.tokenizer == TokenizerType.PREFIX
    assert TEXT_INDEX_PARAMS.min_token_len == 3 and TEXT_INDEX_PARAMS.max_token_len == 15
    assert TEXT_INDEX_PARAMS.lowercase is True and TEXT_INDEX_PARAMS.ascii_folding is True
    assert TEXT_INDEX_PARAMS.on_disk is True


def test_ensure_text_index_lo_crea_si_no_existe(almacen):
    almacen.client.get_collection.return_value = _coleccion()
    almacen.ensure_text_index()
    kwargs = almacen.client.create_payload_index.call_args.kwargs
    assert kwargs["collection_name"] == "mia_prueba" and kwargs["field_name"] == "text"
    assert kwargs["field_schema"] == TEXT_INDEX_PARAMS and kwargs["wait"] is True


def test_ensure_text_index_no_hace_nada_si_ya_existe_igual(almacen):
    almacen.client.get_collection.return_value = _coleccion(_esquema(TEXT_INDEX_PARAMS))
    almacen.ensure_text_index()
    almacen.client.create_payload_index.assert_not_called()


def test_ensure_text_index_falla_con_mensaje_claro_si_existe_con_otros_parametros(almacen):
    otros = SimpleNamespace(
        tokenizer=TokenizerType.WORD, lowercase=True, ascii_folding=True, min_token_len=2, max_token_len=20
    )
    almacen.client.get_collection.return_value = _coleccion(_esquema(otros))
    with pytest.raises(RuntimeError, match="otros parámetros"):
        almacen.ensure_text_index()
    almacen.client.create_payload_index.assert_not_called()


def test_text_index_status_con_y_sin_indice(almacen):
    almacen.client.get_collection.return_value = _coleccion(_esquema(TEXT_INDEX_PARAMS, points=7), points_count=10)
    estado = almacen.text_index_status()
    assert estado["exists"] is True and estado["indexed"] == 7 and estado["points"] == 10
    assert estado["params"]["tokenizer"] == "prefix"
    almacen.client.get_collection.return_value = _coleccion(points_count=10)
    assert almacen.text_index_status() == {"exists": False, "params": {}, "indexed": 0, "points": 10}


def test_drop_text_index(almacen):
    almacen.drop_text_index()
    kwargs = almacen.client.delete_payload_index.call_args.kwargs
    assert kwargs["collection_name"] == "mia_prueba" and kwargs["field_name"] == "text"


def test_un_almacen_sin_busqueda_por_palabras_lanza_not_implemented():
    class Minimo(VectorStore):
        def ensure_collection(self, vector_size): ...
        def upsert(self, chunks): ...
        def search(self, query_embedding, domains, limit=5): ...
        def get_chunks(self, document_id, chunk_indexes): ...
        def count_chunks(self, document_id): ...
        def set_domain(self, document_id, domain_id): ...

    almacen = Minimo()
    for llamada in (
        almacen.ensure_text_index,
        almacen.text_index_status,
        almacen.drop_text_index,
        lambda: almacen.match_chunks(["d"], "x", 1),
        lambda: almacen.score_chunks([0.1], ["d"], ["a"]),
    ):
        with pytest.raises(NotImplementedError):
            llamada()
