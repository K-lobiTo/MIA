from mia.rag.embeddings import EmbeddingProvider


class OpenAIEmbeddingProvider(EmbeddingProvider):
    def embed(self, texts: list[str]) -> list[list[float]]:
        raise NotImplementedError
