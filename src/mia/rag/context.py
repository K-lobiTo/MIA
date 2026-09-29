"""Armado del contexto para el LLM a partir de los resultados de la búsqueda.

La búsqueda por similitud devuelve fragmentos sueltos de ~1000 caracteres. Cuando la respuesta es
una lista o sección larga (p. ej. los contenidos de un programa de curso), sus partes quedan en
fragmentos consecutivos y las del final se parecen poco a la pregunta, así que no se recuperan y la
respuesta queda incompleta. Por eso a cada fragmento relevante se le suman sus vecinos del mismo
documento y los fragmentos consecutivos se unen en un solo pasaje.
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


def build_passages(
    relevant: list[SearchResult], vector_store: VectorStore, neighbors: int
) -> list[Passage]:
    """Suma a cada resultado relevante sus `neighbors` fragmentos anteriores y posteriores del
    mismo documento, y une todo en pasajes continuos."""
    chunks = list(relevant)
    if neighbors > 0:
        wanted: dict[str, set[int]] = {}
        for result in relevant:
            around = range(result.chunk_index - neighbors, result.chunk_index + neighbors + 1)
            wanted.setdefault(result.document_id, set()).update(i for i in around if i >= 0)
        for result in relevant:
            wanted[result.document_id].discard(result.chunk_index)
        for document_id, indexes in wanted.items():
            chunks.extend(vector_store.get_chunks(document_id, sorted(indexes)))
    return merge_into_passages(chunks)
