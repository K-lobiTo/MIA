import logging
import time

import numpy as np
from google import genai
from google.genai import errors, types

from mia.config import settings
from mia.rag.embeddings import EmbeddingProvider

# gemini-embedding-001 y no gemini-embedding-2: este último es multimodal y combina todos los
# textos de una llamada en un solo embedding, en vez de devolver uno por texto.
MODEL = "gemini-embedding-001"
DIMENSION = 768
# Máximo de textos por llamada que acepta la API.
BATCH_SIZE = 100
# El tier gratuito limita por minuto: ante un 429 se espera y se reintenta en vez de fallar la ingesta.
MAX_RETRY_SECONDS = 15 * 60
RETRY_WAIT_SECONDS = 30

logger = logging.getLogger(__name__)


class GeminiEmbeddingProvider(EmbeddingProvider):
    dimension = DIMENSION

    def __init__(self) -> None:
        self._client = (
            genai.Client(api_key=settings.gemini_api_key) if settings.gemini_api_key else genai.Client()
        )

    def embed(self, texts: list[str], is_query: bool = False) -> list[list[float]]:
        config = types.EmbedContentConfig(
            task_type="RETRIEVAL_QUERY" if is_query else "RETRIEVAL_DOCUMENT",
            output_dimensionality=DIMENSION,
        )
        embeddings = []
        for start in range(0, len(texts), BATCH_SIZE):
            batch = texts[start : start + BATCH_SIZE]
            response = self._embed_with_retry(batch, config)
            vectors = np.array([embedding.values for embedding in response.embeddings])
            # Con dimensión reducida (< 3072) la API no devuelve vectores normalizados.
            vectors /= np.linalg.norm(vectors, axis=1, keepdims=True)
            embeddings.extend(vectors.tolist())
        return embeddings

    def _embed_with_retry(
        self, batch: list[str], config: types.EmbedContentConfig
    ) -> types.EmbedContentResponse:
        deadline = time.monotonic() + MAX_RETRY_SECONDS
        while True:
            try:
                return self._client.models.embed_content(model=MODEL, contents=batch, config=config)
            except errors.APIError as error:
                if error.code != 429 or time.monotonic() > deadline:
                    raise
                logger.warning("Cuota de embeddings de Gemini agotada, reintentando en %ss", RETRY_WAIT_SECONDS)
                time.sleep(RETRY_WAIT_SECONDS)
