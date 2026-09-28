import logging
import threading
import uuid
from pathlib import Path

from mia.config import settings
from mia.ingestion.chunker import chunk_text
from mia.ingestion.loaders.base import get_loader
from mia.rag.embeddings import get_embedding_provider
from mia.storage.db import SessionLocal
from mia.storage.models import Document
from mia.storage.vector_store import Chunk, get_vector_store

UPLOAD_DIR = Path("uploads")
# Fragmentos por lote de embeddings + upsert: acota la memoria con documentos largos.
INGEST_BATCH_SIZE = 64

# Las BackgroundTasks síncronas corren en el threadpool, así que varias subidas seguidas
# ingerirían en paralelo y multiplicarían la memoria del modelo de embeddings (con 3 actas
# grandes se superaban los 512 MB de Render). Se ingiere un documento a la vez.
_ingest_lock = threading.Lock()

logger = logging.getLogger(__name__)


def ingest_document(document_id: str) -> None:
    with _ingest_lock:
        _ingest_document(document_id)


def _ingest_document(document_id: str) -> None:
    with SessionLocal() as session:
        document = session.get(Document, document_id)
        if document is None:
            return

        document.status = "processing"
        session.commit()

        try:
            path = UPLOAD_DIR / f"{document.id}.{document.source_type}"
            text = get_loader(document.source_type).load(path)
            if not text or not text.strip():
                raise ValueError(f"Documento sin texto extraíble: {path}")

            texts = chunk_text(text)
            embedding_provider = get_embedding_provider(settings.embedding_provider)
            vector_store = get_vector_store()
            for start in range(0, len(texts), INGEST_BATCH_SIZE):
                batch = texts[start : start + INGEST_BATCH_SIZE]
                embeddings = embedding_provider.embed(batch, is_query=False)
                vector_store.upsert(
                    [
                        Chunk(
                            id=str(uuid.uuid4()),
                            document_id=document.id,
                            domain=document.domain_id,
                            text=chunk_text_value,
                            chunk_index=start + offset,
                            embedding=embedding,
                        )
                        for offset, (chunk_text_value, embedding) in enumerate(
                            zip(batch, embeddings)
                        )
                    ]
                )
        except Exception:
            logger.exception("Fallo indexando documento %s", document.id)
            document.status = "error"
        else:
            document.status = "done"
        finally:
            session.commit()
