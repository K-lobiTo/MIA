"""Armado del contexto para el LLM a partir de los resultados de la búsqueda.

La búsqueda por similitud devuelve fragmentos sueltos de ~1000 caracteres. Cuando la respuesta es
una lista o sección larga (p. ej. los contenidos de un programa de curso), sus partes quedan en
fragmentos consecutivos y las del final se parecen poco a la pregunta, así que no se recuperan y la
respuesta queda incompleta. Por eso a cada fragmento relevante se le suman sus vecinos del mismo
documento y los fragmentos consecutivos se unen en un solo pasaje. Si el documento es corto (p. ej.
un programa de curso o una lista de líneas de TFG), se pasa completo: una lista que ocupa casi todo
el documento no cabe en un fragmento y sus vecinos.
"""

from dataclasses import dataclass

from mia.storage.vector_store import SearchResult, VectorStore

# El chunker superpone 200 caracteres entre fragmentos consecutivos; se busca hasta un poco más.
MAX_OVERLAP = 400
MIN_OVERLAP = 20


@dataclass
class Passage:
    document_id: str
    domain: str
    text: str
    first_index: int
    last_index: int
    # Mejor puntaje de similitud entre los fragmentos que lo componen (los vecinos no suman).
    score: float
    # Hay fragmentos posteriores del documento que no se entregaron (solo se calcula con ContextPolicy).
    continues: bool = False


def join_consecutive(previous: str, following: str) -> str:
    """Une dos fragmentos consecutivos quitando el texto que comparten por la superposición."""
    for size in range(min(len(previous), len(following), MAX_OVERLAP), MIN_OVERLAP - 1, -1):
        if previous.endswith(following[:size]):
            return previous + following[size:]
    return previous + "\n" + following


def merge_into_passages(chunks: list[SearchResult]) -> list[Passage]:
    """Agrupa fragmentos por documento y une los consecutivos. Devuelve los pasajes ordenados
    del más relevante al menos relevante."""
    by_document: dict[str, dict[int, SearchResult]] = {}
    for chunk in chunks:
        existing = by_document.setdefault(chunk.document_id, {}).get(chunk.chunk_index)
        if existing is None or chunk.score > existing.score:
            by_document[chunk.document_id][chunk.chunk_index] = chunk

    passages: list[Passage] = []
    for document_id, indexed in by_document.items():
        current: Passage | None = None
        for index in sorted(indexed):
            chunk = indexed[index]
            if current is not None and index == current.last_index + 1:
                current.text = join_consecutive(current.text, chunk.text)
                current.last_index = index
                current.score = max(current.score, chunk.score)
                continue
            if current is not None:
                passages.append(current)
            current = Passage(
                document_id=document_id,
                domain=chunk.domain,
                text=chunk.text,
                first_index=index,
                last_index=index,
                score=chunk.score,
            )
        if current is not None:
            passages.append(current)

    return sorted(passages, key=lambda passage: passage.score, reverse=True)


@dataclass(frozen=True)
class ContextPolicy:
    """Contexto completo de los documentos principales (feature 007, QUERY_COMPLETE_CONTEXT).

    Los `documents` documentos de mejor resultado se entregan completos si tienen hasta `document_max_chunks`
    fragmentos y, si son más largos, con `forward_neighbors` fragmentos posteriores a cada resultado. Si la
    suma de caracteres supera `max_chars` se descartan pasajes de los demás documentos, de menor puntaje a
    mayor; los del documento principal nunca se descartan.
    """

    documents: int = 1
    document_max_chunks: int = 25
    forward_neighbors: int = 4
    max_chars: int = 80000


def _apply_policy(
    relevant: list[SearchResult],
    wanted: dict[str, set[int]],
    totals: dict[str, int],
    vector_store: VectorStore,
    neighbors: int,
    policy: ContextPolicy,
) -> set[str]:
    """Amplía `wanted` para los documentos principales y devuelve sus ids."""
    best: dict[str, float] = {}
    for result in relevant:
        best[result.document_id] = max(best.get(result.document_id, 0.0), result.score)
    main = sorted(best, key=best.get, reverse=True)[: policy.documents]
    for document_id in main:
        total = totals.setdefault(document_id, vector_store.count_chunks(document_id))
        if total <= policy.document_max_chunks:
            wanted[document_id] = set(range(total))
            continue
        # En un documento principal largo la ventana de cada resultado es asimétrica y reemplaza a la de siempre.
        wanted[document_id] = set()
        for result in (r for r in relevant if r.document_id == document_id):
            around = range(result.chunk_index - neighbors, result.chunk_index + policy.forward_neighbors + 1)
            wanted[document_id].update(i for i in around if 0 <= i < total)
    return set(main)


def build_passages(
    relevant: list[SearchResult],
    vector_store: VectorStore,
    neighbors: int,
    full_document_max_chunks: int = 0,
    policy: ContextPolicy | None = None,
) -> list[Passage]:
    """Suma a cada resultado relevante sus `neighbors` fragmentos anteriores y posteriores del
    mismo documento, y une todo en pasajes continuos. Los documentos de hasta
    `full_document_max_chunks` fragmentos se incluyen completos (0 lo desactiva).

    Con `policy` (feature 007) los documentos principales se completan o se prolongan hacia adelante, cada
    pasaje sabe si su documento continúa (`continues`) y el total se acota a `policy.max_chars`. Sin
    `policy` el resultado es el de siempre."""
    wanted: dict[str, set[int]] = {}
    for result in relevant:
        around = range(result.chunk_index - neighbors, result.chunk_index + neighbors + 1)
        wanted.setdefault(result.document_id, set()).update(i for i in around if i >= 0)
    totals: dict[str, int] = {}
    if full_document_max_chunks > 0:
        for document_id in wanted:
            total = totals.setdefault(document_id, vector_store.count_chunks(document_id))
            if total <= full_document_max_chunks:
                wanted[document_id] = set(range(total))
    main: set[str] = set()
    if policy is not None:
        main = _apply_policy(relevant, wanted, totals, vector_store, neighbors, policy)
    for result in relevant:
        wanted[result.document_id].discard(result.chunk_index)

    chunks = list(relevant)
    for document_id, indexes in wanted.items():
        if indexes:
            chunks.extend(vector_store.get_chunks(document_id, sorted(indexes)))
    passages = merge_into_passages(chunks)
    if policy is None:
        return passages

    for passage in passages:
        total = totals.setdefault(passage.document_id, vector_store.count_chunks(passage.document_id))
        passage.continues = passage.last_index + 1 < total
    # Tope de contexto: salen primero los pasajes de menor puntaje que no son del documento principal.
    size = sum(len(p.text) for p in passages)
    for passage in sorted((p for p in passages if p.document_id not in main), key=lambda p: p.score):
        if size <= policy.max_chars:
            break
        passages.remove(passage)
        size -= len(passage.text)
    return passages
