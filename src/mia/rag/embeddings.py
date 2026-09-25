from abc import ABC, abstractmethod


class EmbeddingProvider(ABC):
    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]: ...


def get_embedding_provider(name: str) -> EmbeddingProvider:
    if name == "local":
        from mia.rag.providers.local_embeddings import LocalEmbeddingProvider

        return LocalEmbeddingProvider()
    if name == "openai":
        from mia.rag.providers.openai_embeddings import OpenAIEmbeddingProvider

        return OpenAIEmbeddingProvider()
    raise ValueError(f"Proveedor de embeddings desconocido: {name}")
