from sentence_transformers import SentenceTransformer

from mia.rag.embeddings import EmbeddingProvider

MODEL_NAME = "intfloat/multilingual-e5-small"


class LocalEmbeddingProvider(EmbeddingProvider):
    def __init__(self) -> None:
        self._model = SentenceTransformer(MODEL_NAME)
        self.dimension = self._model.get_embedding_dimension()

    def embed(self, texts: list[str], is_query: bool = False) -> list[list[float]]:
        prefix = "query: " if is_query else "passage: "
        prefixed = [prefix + text for text in texts]
        return self._model.encode(prefixed, normalize_embeddings=True).tolist()
