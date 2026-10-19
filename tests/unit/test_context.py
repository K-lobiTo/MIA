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


# --- Contexto completo del documento principal (feature 007) --------------------------------


class _AlmacenFalso:
    """Almacén con documentos de `n` fragmentos cuyo texto es `<documento>:<índice>` (de 100 caracteres)."""

    def __init__(self, tamanos: dict[str, int]):
        self.tamanos = tamanos
        self.pedidos: list[tuple[str, list[int]]] = []

    def count_chunks(self, document_id: str) -> int:
        return self.tamanos[document_id]

    def get_chunks(self, document_id: str, indexes: list[int]) -> list[SearchResult]:
        self.pedidos.append((document_id, list(indexes)))
        return [
            _chunk(i, f"{document_id}:{i}".ljust(100, "."), document_id=document_id)
            for i in indexes
            if 0 <= i < self.tamanos[document_id]
        ]


def _relevante(documento: str, indice: int, puntaje: float) -> SearchResult:
    return _chunk(indice, f"{documento}:{indice}".ljust(100, "."), score=puntaje, document_id=documento)


def _politica(**cambios):
    from mia.rag.context import ContextPolicy

    valores = {"documents": 1, "document_max_chunks": 25, "forward_neighbors": 4, "max_chars": 80000, **cambios}
    return ContextPolicy(**valores)


def _rangos(pasajes):
    return sorted((p.document_id, p.first_index, p.last_index, p.continues) for p in pasajes)


def test_sin_politica_el_resultado_es_el_de_siempre():
    almacen = _AlmacenFalso({"doc-1": 60})
    relevant = [_relevante("doc-1", 20, 0.9)]
    sin = build_passages(relevant, almacen, neighbors=1, full_document_max_chunks=12)
    con_none = build_passages(relevant, almacen, neighbors=1, full_document_max_chunks=12, policy=None)
    assert _rangos(sin) == _rangos(con_none) == [("doc-1", 19, 21, False)]


def test_el_documento_principal_de_15_fragmentos_se_entrega_completo():
    almacen = _AlmacenFalso({"doc-1": 15})
    pasajes = build_passages([_relevante("doc-1", 5, 0.9)], almacen, neighbors=1, full_document_max_chunks=12, policy=_politica())
    assert _rangos(pasajes) == [("doc-1", 0, 14, False)]


def test_el_documento_principal_largo_suma_un_anterior_y_posteriores():
    almacen = _AlmacenFalso({"doc-1": 60})
    pasajes = build_passages([_relevante("doc-1", 20, 0.9)], almacen, neighbors=1, full_document_max_chunks=12, policy=_politica())
    assert _rangos(pasajes) == [("doc-1", 19, 24, True)]
    assert almacen.pedidos == [("doc-1", [19, 21, 22, 23, 24])]


def test_sin_fragmentos_posteriores_solo_queda_el_anterior():
    almacen = _AlmacenFalso({"doc-1": 60})
    pasajes = build_passages(
        [_relevante("doc-1", 20, 0.9)], almacen, neighbors=1, full_document_max_chunks=12, policy=_politica(forward_neighbors=0)
    )
    assert _rangos(pasajes) == [("doc-1", 19, 20, True)]


def test_el_avance_hacia_adelante_no_pasa_del_ultimo_fragmento():
    almacen = _AlmacenFalso({"doc-1": 60})
    pasajes = build_passages([_relevante("doc-1", 58, 0.9)], almacen, neighbors=1, full_document_max_chunks=12, policy=_politica())
    assert _rangos(pasajes) == [("doc-1", 57, 59, False)]  # llega al último fragmento: no continúa


def test_los_documentos_secundarios_siguen_como_hoy():
    almacen = _AlmacenFalso({"doc-1": 60, "doc-2": 100, "doc-3": 8})
    relevant = [_relevante("doc-1", 20, 0.95), _relevante("doc-2", 50, 0.90), _relevante("doc-3", 3, 0.85)]
    pasajes = build_passages(relevant, almacen, neighbors=1, full_document_max_chunks=12, policy=_politica())
    assert _rangos(pasajes) == [
        ("doc-1", 19, 24, True),  # principal: avanza
        ("doc-2", 49, 51, True),  # secundario largo: un vecino a cada lado
        ("doc-3", 0, 7, False),  # secundario corto (8 <= 12): completo
    ]


def test_documents_2_amplia_tambien_el_segundo_documento():
    almacen = _AlmacenFalso({"doc-1": 60, "doc-2": 15})
    relevant = [_relevante("doc-1", 20, 0.95), _relevante("doc-2", 5, 0.90)]
    pasajes = build_passages(relevant, almacen, neighbors=1, full_document_max_chunks=12, policy=_politica(documents=2))
    assert _rangos(pasajes) == [("doc-1", 19, 24, True), ("doc-2", 0, 14, False)]


def test_el_documento_principal_es_el_de_mejor_puntaje_aunque_llegue_despues():
    almacen = _AlmacenFalso({"doc-1": 60, "doc-2": 15})
    relevant = [_relevante("doc-1", 20, 0.80), _relevante("doc-2", 5, 0.95)]
    pasajes = build_passages(relevant, almacen, neighbors=1, full_document_max_chunks=12, policy=_politica())
    assert ("doc-2", 0, 14, False) in _rangos(pasajes)


def test_el_tope_descarta_primero_los_pasajes_secundarios_de_menor_puntaje():
    almacen = _AlmacenFalso({"doc-1": 15, "doc-2": 100, "doc-3": 100})
    relevant = [_relevante("doc-1", 5, 0.95), _relevante("doc-2", 50, 0.90), _relevante("doc-3", 50, 0.85)]
    # doc-1 completo son 15 x 100 = 1.500 caracteres; cada secundario 3 x 100 = 300 (con "\n" de unión, un poco más).
    sin_tope = build_passages(relevant, almacen, neighbors=1, full_document_max_chunks=12, policy=_politica())
    assert {p.document_id for p in sin_tope} == {"doc-1", "doc-2", "doc-3"}

    con_tope = build_passages(relevant, almacen, neighbors=1, full_document_max_chunks=12, policy=_politica(max_chars=2000))
    assert {p.document_id for p in con_tope} == {"doc-1", "doc-2"}  # sale el de menor puntaje

    muy_bajo = build_passages(relevant, almacen, neighbors=1, full_document_max_chunks=12, policy=_politica(max_chars=100))
    assert {p.document_id for p in muy_bajo} == {"doc-1"}  # el principal nunca se descarta, aunque exceda el tope
    assert sum(len(p.text) for p in muy_bajo) > 100
