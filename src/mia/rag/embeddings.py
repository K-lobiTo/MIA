from abc import ABC, abstractmethod
from functools import lru_cache


class EmbeddingProvider(ABC):
    dimension: int

    @abstractmethod
    def embed(self, texts: list[str], is_query: bool = False) -> list[list[float]]:
        """is_query distingue el embedding de una pregunta del de un fragmento de documento,
        algunos modelos (p. ej. la familia E5) rinden mejor con instrucciones distintas para cada caso."""
        ...


@lru_cache
def get_embedding_provider(name: str) -> EmbeddingProvider:
    if name == "local":
        from mia.rag.providers.local_embeddings import LocalEmbeddingProvider

        return LocalEmbeddingProvider()
    if name == "gemini":
        from mia.rag.providers.gemini_embeddings import GeminiEmbeddingProvider

        return GeminiEmbeddingProvider()
    if name == "openai":
        from mia.rag.providers.openai_embeddings import OpenAIEmbeddingProvider

        return OpenAIEmbeddingProvider()
    raise ValueError(f"Proveedor de embeddings desconocido: {name}")
