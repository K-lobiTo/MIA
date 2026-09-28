import numpy as np
import onnxruntime as ort
import sentencepiece as spm
from huggingface_hub import hf_hub_download

from mia.rag.embeddings import EmbeddingProvider

# Mismo modelo intfloat/multilingual-e5-small, exportado a ONNX y cuantizado a int8.
# Se usa onnxruntime + sentencepiece en lugar de sentence-transformers (PyTorch) para que la API
# quepa en los 512 MB del plan free de Render: PyTorch + el modelo en fp32 superaban 1 GB.
MODEL_REPO = "Xenova/multilingual-e5-small"
MODEL_FILE = "onnx/model_quantized.onnx"
TOKENIZER_REPO = "intfloat/multilingual-e5-small"
TOKENIZER_FILE = "sentencepiece.bpe.model"

MAX_TOKENS = 512
# Lotes chicos para acotar el pico de memoria al ingerir documentos con muchos fragmentos.
BATCH_SIZE = 8
# Convención de XLM-RoBERTa: ids especiales fijos y los ids de sentencepiece desplazados en 1.
BOS_ID, PAD_ID, EOS_ID, UNK_ID = 0, 1, 2, 3


def download_model_files() -> tuple[str, str]:
    """Descarga (o toma de la caché de HuggingFace) el modelo y el tokenizador.
    El Dockerfile la llama en el build para no descargar en cada arranque en frío."""
    return hf_hub_download(MODEL_REPO, MODEL_FILE), hf_hub_download(TOKENIZER_REPO, TOKENIZER_FILE)


class LocalEmbeddingProvider(EmbeddingProvider):
    dimension = 384

    def __init__(self) -> None:
        model_path, tokenizer_path = download_model_files()
        self._tokenizer = spm.SentencePieceProcessor(model_file=tokenizer_path)

        options = ort.SessionOptions()
        options.enable_cpu_mem_arena = False
        options.intra_op_num_threads = 1
        self._session = ort.InferenceSession(
            model_path, options, providers=["CPUExecutionProvider"]
        )
        self._input_names = {i.name for i in self._session.get_inputs()}

    def _token_ids(self, text: str) -> list[int]:
        pieces = [i + 1 if i != 0 else UNK_ID for i in self._tokenizer.encode(text.strip())]
        return [BOS_ID, *pieces[: MAX_TOKENS - 2], EOS_ID]

    def embed(self, texts: list[str], is_query: bool = False) -> list[list[float]]:
        prefix = "query: " if is_query else "passage: "
        embeddings = []
        for start in range(0, len(texts), BATCH_SIZE):
            batch = texts[start : start + BATCH_SIZE]
            embeddings.extend(self._embed_batch([prefix + text for text in batch]))
        return embeddings

    def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        ids = [self._token_ids(text) for text in texts]
        length = max(len(row) for row in ids)
        input_ids = np.full((len(ids), length), PAD_ID, dtype=np.int64)
        attention_mask = np.zeros((len(ids), length), dtype=np.int64)
        for i, row in enumerate(ids):
            input_ids[i, : len(row)] = row
            attention_mask[i, : len(row)] = 1

        inputs = {"input_ids": input_ids, "attention_mask": attention_mask}
        if "token_type_ids" in self._input_names:
            inputs["token_type_ids"] = np.zeros_like(input_ids)
        hidden = self._session.run(None, inputs)[0]

        # Mean pooling sobre los tokens reales y normalización L2, igual que el modelo original.
        mask = attention_mask[..., None]
        pooled = (hidden * mask).sum(axis=1) / mask.sum(axis=1)
        normalized = pooled / np.linalg.norm(pooled, axis=1, keepdims=True)
        return normalized.tolist()
