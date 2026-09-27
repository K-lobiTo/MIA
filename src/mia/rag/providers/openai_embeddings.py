from mia.rag.embeddings import EmbeddingProvider


class OpenAIEmbeddingProvider(EmbeddingProvider):
    def __init__(self) -> None:
        self.dimension = 1536  # text-embedding-3-small; ajustar si se implementa con otro modelo

    def embed(self, texts: list[str], is_query: bool = False) -> list[list[float]]:
        raise NotImplementedError
