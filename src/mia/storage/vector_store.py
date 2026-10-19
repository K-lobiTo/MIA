from abc import ABC, abstractmethod
from dataclasses import dataclass
from functools import lru_cache

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    HasIdCondition,
    MatchAny,
    MatchText,
    MatchValue,
    PayloadSchemaType,
    PointStruct,
    TextIndexParams,
    TextIndexType,
    TokenizerType,
    VectorParams,
)

# Campos del payload por los que se filtra: `domain` en las consultas; `document_id` y
# `chunk_index` para traer fragmentos vecinos de un documento (o ubicarlos para borrarlos).
FILTERABLE_FIELDS = {
    "domain": PayloadSchemaType.KEYWORD,
    "document_id": PayloadSchemaType.KEYWORD,
    "chunk_index": PayloadSchemaType.INTEGER,
}

# Índice de texto sobre el campo `text` (feature 010, búsqueda por palabras). Tokenizador por prefijo: una palabra
# coincide con el inicio de otra, lo que encuentra "obando" en "Obando2023800202" (nombre pegado al carné en las
# carátulas de los PDF). Sin tildes ni mayúsculas. No guarda palabras de menos de 3 letras. En disco: Qdrant no
# gasta memoria por él. Ver specs/010-busqueda-hibrida/research.md R2.
TEXT_FIELD = "text"
TEXT_INDEX_PARAMS = TextIndexParams(
    type=TextIndexType.TEXT,
    tokenizer=TokenizerType.PREFIX,
    lowercase=True,
    ascii_folding=True,
    min_token_len=3,
    max_token_len=15,
    on_disk=True,
)


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

    # Búsqueda por palabras (feature 010). No son abstractos: un almacén que no los tenga cae a la búsqueda por
    # significado (la ruta trata NotImplementedError como "parte léxica no disponible").
    def ensure_text_index(self) -> None:
        """Crea el índice de texto sobre `text` si no existe (idempotente)."""
        raise NotImplementedError("Este almacén no tiene búsqueda por palabras")

    def text_index_status(self) -> dict:
        """{"exists", "params", "indexed", "points"}."""
        raise NotImplementedError("Este almacén no tiene búsqueda por palabras")

    def drop_text_index(self) -> None:
        raise NotImplementedError("Este almacén no tiene búsqueda por palabras")

    def match_chunks(self, domains: list[str], text: str, limit: int) -> list[str]:
        """Ids de fragmentos de los dominios cuyo texto contiene todas las palabras de `text`, como mucho `limit`."""
        raise NotImplementedError("Este almacén no tiene búsqueda por palabras")

    def score_chunks(
        self, embedding: list[float], domains: list[str], chunk_ids: list[str]
    ) -> list[SearchResult]:
        """Los fragmentos con esos ids (dentro de los dominios), con su coseno contra `embedding` en `score`."""
        raise NotImplementedError("Este almacén no tiene búsqueda por palabras")

    @abstractmethod
    def count_chunks(self, document_id: str) -> int:
        """Cantidad de fragmentos de un documento."""

    @abstractmethod
    def set_domain(self, document_id: str, domain_id: str) -> None:
        """Cambia el dominio de todos los fragmentos de un documento, sin recalcular embeddings
        (al mover un documento de dominio)."""


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

    def ensure_text_index(self) -> None:
        existing = self._text_index_schema()
        if existing is None:
            self.client.create_payload_index(
                collection_name=self.collection,
                field_name=TEXT_FIELD,
                field_schema=TEXT_INDEX_PARAMS,
                wait=True,
            )
            return
        if _index_params(existing) != _index_params(TEXT_INDEX_PARAMS):
            raise RuntimeError(
                f"La colección '{self.collection}' ya tiene un índice de texto con otros parámetros "
                f"({_index_params(existing)}). Quitarlo con scripts/palabras.py quitar y volver a prepararlo."
            )

    def text_index_status(self) -> dict:
        info = self.client.get_collection(self.collection)
        schema = (info.payload_schema or {}).get(TEXT_FIELD)
        exists = schema is not None and _is_text_schema(schema)
        return {
            "exists": exists,
            "params": _index_params(schema.params) if exists and getattr(schema, "params", None) else {},
            "indexed": (schema.points or 0) if exists else 0,
            "points": info.points_count or 0,
        }

    def drop_text_index(self) -> None:
        self.client.delete_payload_index(collection_name=self.collection, field_name=TEXT_FIELD, wait=True)

    def _text_index_schema(self):
        """Parámetros del índice de texto actual, o None si no existe."""
        schema = (self.client.get_collection(self.collection).payload_schema or {}).get(TEXT_FIELD)
        if schema is None or not _is_text_schema(schema):
            return None
        return getattr(schema, "params", None) or TEXT_INDEX_PARAMS

    def match_chunks(self, domains: list[str], text: str, limit: int) -> list[str]:
        points, _ = self.client.scroll(
            collection_name=self.collection,
            scroll_filter=Filter(
                must=[
                    FieldCondition(key="domain", match=MatchAny(any=domains)),
                    FieldCondition(key=TEXT_FIELD, match=MatchText(text=text)),
                ]
            ),
            limit=limit,
            with_payload=False,
            with_vectors=False,
        )
        return [str(point.id) for point in points]

    def score_chunks(
        self, embedding: list[float], domains: list[str], chunk_ids: list[str]
    ) -> list[SearchResult]:
        if not chunk_ids:
            return []
        response = self.client.query_points(
            collection_name=self.collection,
            query=embedding,
            query_filter=Filter(
                must=[
                    HasIdCondition(has_id=chunk_ids),
                    FieldCondition(key="domain", match=MatchAny(any=domains)),
                ]
            ),
            limit=len(chunk_ids),
        )
        return [_to_result(point, point.score) for point in response.points]

    def count_chunks(self, document_id: str) -> int:
        return self.client.count(
            collection_name=self.collection,
            count_filter=Filter(
                must=[FieldCondition(key="document_id", match=MatchValue(value=document_id))]
            ),
            exact=True,
        ).count

    def set_domain(self, document_id: str, domain_id: str) -> None:
        self.client.set_payload(
            collection_name=self.collection,
            payload={"domain": domain_id},
            points=Filter(
                must=[FieldCondition(key="document_id", match=MatchValue(value=document_id))]
            ),
        )


def _is_text_schema(schema) -> bool:
    return getattr(getattr(schema, "data_type", None), "value", getattr(schema, "data_type", None)) == "text"


def _index_params(params) -> dict:
    """Los parámetros del índice de texto que importan al comparar (los que decide TEXT_INDEX_PARAMS)."""
    tokenizer = getattr(params, "tokenizer", None)
    return {
        "tokenizer": getattr(tokenizer, "value", tokenizer),
        "lowercase": getattr(params, "lowercase", None),
        "ascii_folding": getattr(params, "ascii_folding", None),
        "min_token_len": getattr(params, "min_token_len", None),
        "max_token_len": getattr(params, "max_token_len", None),
    }


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
