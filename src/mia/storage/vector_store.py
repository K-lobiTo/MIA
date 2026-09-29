from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import lru_cache

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchAny,
    MatchValue,
    PayloadSchemaType,
    PointStruct,
    VectorParams,
)

# Campos del payload por los que se filtra: `domain` en las consultas; `document_id` y
# `chunk_index` para traer fragmentos vecinos de un documento (o ubicarlos para borrarlos).
FILTERABLE_FIELDS = {
    "domain": PayloadSchemaType.KEYWORD,
    "document_id": PayloadSchemaType.KEYWORD,
    "chunk_index": PayloadSchemaType.INTEGER,
}


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
    chunk_index: int = 0


class VectorStore(ABC):
    @abstractmethod
    def ensure_collection(self, vector_size: int) -> None: ...

    @abstractmethod
    def upsert(self, chunks: list[Chunk]) -> None: ...

    @abstractmethod
    def search(
        self, query_embedding: list[float], domains: list[str], limit: int = 5
    ) -> list[SearchResult]: ...

    @abstractmethod
    def get_chunks(self, document_id: str, chunk_indexes: list[int]) -> list[SearchResult]:
        """Fragmentos de un documento por posición (sin puntaje de similitud, `score=0`)."""


class QdrantVectorStore(VectorStore):
    """Implementación sobre Qdrant. Colección única (`domain` como payload filtrable),
    ver docs/Definicion_Requerimientos_MVP.md sección 5."""

    def __init__(self, url: str, collection: str, api_key: str = ""):
        self.collection = collection
        self.client = QdrantClient(url=url, api_key=api_key or None)

    def ensure_collection(self, vector_size: int) -> None:
        if not self.client.collection_exists(self.collection):
            self.client.create_collection(
                collection_name=self.collection,
                vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
            )
        else:
            existing_size = self.client.get_collection(self.collection).config.params.vectors.size
            if existing_size != vector_size:
                raise RuntimeError(
                    f"La colección '{self.collection}' tiene vectores de dimensión "
                    f"{existing_size}, pero el proveedor de embeddings genera {vector_size}. "
                    "Usar otra colección (QDRANT_COLLECTION) o reindexar."
                )

        # Qdrant Cloud rechaza filtrar por un campo del payload sin índice (el Qdrant local no).
        # Crear un índice que ya existe no hace nada, así que se asegura en cada arranque.
        for field, schema in FILTERABLE_FIELDS.items():
            self.client.create_payload_index(
                collection_name=self.collection, field_name=field, field_schema=schema
            )

    def upsert(self, chunks: list[Chunk]) -> None:
        points = [
            PointStruct(
                id=chunk.id,
                vector=chunk.embedding,
                payload={
                    "document_id": chunk.document_id,
                    "domain": chunk.domain,
                    "text": chunk.text,
                    "chunk_index": chunk.chunk_index,
                },
            )
            for chunk in chunks
        ]
        self.client.upsert(collection_name=self.collection, points=points)

    def search(
        self, query_embedding: list[float], domains: list[str], limit: int = 5
    ) -> list[SearchResult]:
        response = self.client.query_points(
            collection_name=self.collection,
            query=query_embedding,
            query_filter=Filter(must=[FieldCondition(key="domain", match=MatchAny(any=domains))]),
            limit=limit,
        )
        return [_to_result(point, point.score) for point in response.points]

    def get_chunks(self, document_id: str, chunk_indexes: list[int]) -> list[SearchResult]:
        if not chunk_indexes:
            return []
        points, _ = self.client.scroll(
            collection_name=self.collection,
            scroll_filter=Filter(
                must=[
                    FieldCondition(key="document_id", match=MatchValue(value=document_id)),
                    FieldCondition(key="chunk_index", match=MatchAny(any=chunk_indexes)),
                ]
            ),
            limit=len(chunk_indexes),
            with_payload=True,
        )
        return [_to_result(point, 0.0) for point in points]


def _to_result(point, score: float) -> SearchResult:
    return SearchResult(
        chunk_id=str(point.id),
        document_id=point.payload["document_id"],
        domain=point.payload["domain"],
        text=point.payload["text"],
        score=score,
        chunk_index=point.payload.get("chunk_index", 0),
    )


@lru_cache
def get_vector_store() -> VectorStore:
    from mia.config import settings

    return QdrantVectorStore(
        url=settings.qdrant_url,
        collection=settings.qdrant_collection,
        api_key=settings.qdrant_api_key,
    )
