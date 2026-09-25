from mia.rag.embeddings import EmbeddingProvider


class LocalEmbeddingProvider(EmbeddingProvider):
    """Modelo de embeddings open-source auto-hospedado (p. ej. sentence-transformers u Ollama)."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError
