from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class Chunk:
    id: str
    document_id: str
    domain: str
    text: str
    chunk_index: int
    embedding: list[float]


@dataclass
class SearchResult:
    chunk_id: str
    document_id: str
    domain: str
    text: str
    score: float


class VectorStore(ABC):
    @abstractmethod
    def upsert(self, chunks: list[Chunk]) -> None: ...

    @abstractmethod
    def search(
        self, query_embedding: list[float], domains: list[str], limit: int = 5
    ) -> list[SearchResult]: ...


class QdrantVectorStore(VectorStore):
    """Implementación sobre Qdrant. Colección única (`domain` como payload filtrable),
    ver docs/Definicion_Requerimientos_MVP.md sección 5."""

    def __init__(self, url: str, collection: str):
        self.url = url
        self.collection = collection

    def upsert(self, chunks: list[Chunk]) -> None:
        raise NotImplementedError

    def search(
        self, query_embedding: list[float], domains: list[str], limit: int = 5
    ) -> list[SearchResult]:
        raise NotImplementedError
