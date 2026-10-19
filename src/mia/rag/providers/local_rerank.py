"""Reranker local (feature 009): cross-encoder multilingüe pequeño con onnxruntime y sentencepiece.

Mismo patrón que `local_embeddings.py`: el modelo `cross-encoder/mmarco-mMiniLMv2-L12-H384-v1` en su variante ONNX
cuantizada a 8 bits, sin PyTorch, para que quepa junto al modelo de embeddings. Lee la pregunta y un pasaje a la vez
y devuelve un logit: cuanto más alto, más responde el pasaje a la pregunta. Solo se importa si RERANK_PROVIDER=local.

Ver specs/009-reranker-local/research.md (R1).
"""

import time

import numpy as np
import onnxruntime as ort
import sentencepiece as spm
from huggingface_hub import hf_hub_download

from mia.config import settings
from mia.rag.providers.local_embeddings import BOS_ID, EOS_ID, UNK_ID
from mia.rag.rerank import RerankProvider, RerankTimeout

MODEL_REPO = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"
# Variante cuantizada que corre en cualquier x86 con AVX2.
MODEL_FILE = "onnx/model_quint8_avx2.onnx"
TOKENIZER_FILE = "sentencepiece.bpe.model"

MAX_TOKENS = 512
# Lotes chicos para acotar el pico de memoria y para comprobar el tiempo entre lotes.
BATCH_SIZE = 4
PAD_ID = 1


def download_rerank_files() -> tuple[str, str]:
    """Descarga (o toma de la caché de HuggingFace) el modelo y el tokenizador. El Dockerfile la llama en el build."""
    return hf_hub_download(MODEL_REPO, MODEL_FILE), hf_hub_download(MODEL_REPO, TOKENIZER_FILE)


class LocalRerankProvider(RerankProvider):
    def __init__(self, session=None, tokenizer=None) -> None:
        # Las pruebas inyectan una sesión y un tokenizador simulados; sin ellos se cargan los reales.
        if session is None or tokenizer is None:
            model_path, tokenizer_path = download_rerank_files()
            if tokenizer is None:
                tokenizer = spm.SentencePieceProcessor(model_file=tokenizer_path)
            if session is None:
                options = ort.SessionOptions()
                options.enable_cpu_mem_arena = False
                options.intra_op_num_threads = settings.rerank_threads
                session = ort.InferenceSession(model_path, options, providers=["CPUExecutionProvider"])
        self._tokenizer = tokenizer
        self._session = session
        self._input_names = {i.name for i in session.get_inputs()}

    def _pieces(self, text: str) -> list[int]:
        # Los ids de sentencepiece se desplazan en 1 (convención de XLM-RoBERTa) y 0 pasa a UNK.
        return [i + 1 if i != 0 else UNK_ID for i in self._tokenizer.encode(text.strip())]

    def _pair_ids(self, query_pieces: list[int], passage: str) -> list[int]:
        """<s> pregunta </s></s> pasaje </s>, con el pasaje recortado y el total bajo MAX_TOKENS."""
        passage_pieces = self._pieces(passage)[: settings.rerank_passage_tokens]
        room = max(MAX_TOKENS - len(query_pieces) - 4, 0)
        return [BOS_ID, *query_pieces, EOS_ID, EOS_ID, *passage_pieces[:room], EOS_ID]

    def score(self, query: str, passages: list[str], deadline: float | None = None) -> list[float]:
        if not passages:
            return []
        query_pieces = self._pieces(query)[: MAX_TOKENS // 2]
        logits: list[float] = []
        for start in range(0, len(passages), BATCH_SIZE):
            # El primer lote siempre se puntúa; el tiempo se comprueba antes de los demás.
            if start > 0 and deadline is not None and time.perf_counter() > deadline:
                raise RerankTimeout("Se agotó el tiempo para puntuar los candidatos")
            rows = [self._pair_ids(query_pieces, p) for p in passages[start : start + BATCH_SIZE]]
            logits.extend(self._score_batch(rows))
        return logits

    def _score_batch(self, rows: list[list[int]]) -> list[float]:
        length = max(len(row) for row in rows)
        input_ids = np.full((len(rows), length), PAD_ID, dtype=np.int64)
        attention_mask = np.zeros((len(rows), length), dtype=np.int64)
        for i, row in enumerate(rows):
            input_ids[i, : len(row)] = row
            attention_mask[i, : len(row)] = 1
        inputs = {"input_ids": input_ids, "attention_mask": attention_mask}
        if "token_type_ids" in self._input_names:
            inputs["token_type_ids"] = np.zeros_like(input_ids)
        output = self._session.run(None, inputs)[0]
        return [float(x) for x in np.asarray(output).reshape(-1)]
