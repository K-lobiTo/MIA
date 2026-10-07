from unittest.mock import MagicMock

from mia.rag.context import build_passages, join_consecutive, merge_into_passages
from mia.storage.vector_store import SearchResult


def _chunk(index: int, text: str, score: float = 0.0, document_id: str = "doc-1") -> SearchResult:
    return SearchResult(
        chunk_id=f"{document_id}-{index}",
        document_id=document_id,
        domain="dom-1",
        text=text,
        score=score,
        chunk_index=index,
    )


def test_join_consecutive_quita_la_superposicion():
    previous = "A. Introducción. B. Conceptos de experimentos. C. Repaso"
    following = "Conceptos de experimentos. C. Repaso de estadística. D. Monofactoriales"

    joined = join_consecutive(previous, following)

    assert joined == (
        "A. Introducción. B. Conceptos de experimentos. C. Repaso de estadística. D. Monofactoriales"
    )


def test_join_consecutive_sin_superposicion_separa_con_salto_de_linea():
    assert join_consecutive("uno", "dos") == "uno\ndos"


def test_merge_une_consecutivos_y_ordena_por_relevancia():
    chunks = [
        _chunk(4, "cuatro", score=0.86),
        _chunk(5, "cinco"),
        _chunk(9, "nueve", score=0.90),
        _chunk(0, "cero", score=0.80, document_id="doc-2"),
    ]

    passages = merge_into_passages(chunks)

    assert [(p.document_id, p.first_index, p.last_index) for p in passages] == [
        ("doc-1", 9, 9),
        ("doc-1", 4, 5),
        ("doc-2", 0, 0),
    ]
    assert passages[1].text == "cuatro\ncinco"
    assert passages[1].score == 0.86


def test_build_passages_suma_vecinos_sin_repetir_los_ya_recuperados():
    relevant = [_chunk(4, "cuatro", score=0.86), _chunk(5, "cinco", score=0.84)]
    vector_store = MagicMock()
    vector_store.get_chunks.return_value = [_chunk(3, "tres"), _chunk(6, "seis")]

    passages = build_passages(relevant, vector_store, neighbors=1)

    vector_store.get_chunks.assert_called_once_with("doc-1", [3, 6])
    assert len(passages) == 1
    assert (passages[0].first_index, passages[0].last_index) == (3, 6)
    assert passages[0].text == "tres\ncuatro\ncinco\nseis"


def test_build_passages_sin_vecinos_no_consulta_el_vector_store():
    vector_store = MagicMock()

    passages = build_passages([_chunk(0, "cero", score=0.9)], vector_store, neighbors=0)

    vector_store.get_chunks.assert_not_called()
    assert [p.text for p in passages] == ["cero"]


def test_build_passages_incluye_completo_un_documento_corto():
    relevant = [_chunk(1, "uno", score=0.9)]
    vector_store = MagicMock()
    vector_store.count_chunks.return_value = 4
    vector_store.get_chunks.return_value = [_chunk(0, "cero"), _chunk(2, "dos"), _chunk(3, "tres")]

    passages = build_passages(relevant, vector_store, neighbors=1, full_document_max_chunks=12)

    vector_store.get_chunks.assert_called_once_with("doc-1", [0, 2, 3])
    assert len(passages) == 1
    assert passages[0].text == "cero\nuno\ndos\ntres"


def test_build_passages_documento_largo_solo_suma_vecinos():
    relevant = [_chunk(10, "diez", score=0.9)]
    vector_store = MagicMock()
    vector_store.count_chunks.return_value = 200
    vector_store.get_chunks.return_value = []

    build_passages(relevant, vector_store, neighbors=1, full_document_max_chunks=12)

    vector_store.get_chunks.assert_called_once_with("doc-1", [9, 11])
