import logging
import threading
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

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

# Documentos cuya eliminación se pidió (feature 012). La ingesta los consulta antes de empezar, antes de cada lote y al
# terminar; vive en la memoria de este proceso (otra instancia de la API se entera por la fila ausente).
_cancelled: set[str] = set()
_cancelled_lock = threading.Lock()


def request_cancel(document_id: str) -> None:
    with _cancelled_lock:
        _cancelled.add(document_id)


def is_cancelled(document_id: str) -> bool:
    with _cancelled_lock:
        return document_id in _cancelled


def clear_cancel(document_id: str) -> None:
    with _cancelled_lock:
        _cancelled.discard(document_id)


def acquire_ingest_lock(timeout: float) -> bool:
    """Toma el cerrojo de la ingesta esperando como mucho `timeout` segundos (lo usa la eliminación de un documento
    que se está procesando)."""
    return _ingest_lock.acquire(timeout=timeout)


def release_ingest_lock() -> None:
    _ingest_lock.release()


def ingest_document(document_id: str) -> None:
    with _ingest_lock:
        _ingest_document(document_id)


def _removed(session: Session, document_id: str) -> bool:
    """El documento se eliminó (o se pidió eliminarlo) mientras se procesaba. Consulta la base, no la memoria de la
    sesión, para enterarse también de lo que elimine otra instancia de la API."""
    return is_cancelled(document_id) or session.scalar(select(Document.id).where(Document.id == document_id)) is None


def _discard_chunks(document_id: str) -> None:
    """Quita los fragmentos que la ingesta alcanzó a escribir de un documento que ya no existe."""
    try:
        get_vector_store().delete_document(document_id)
    except Exception:
        logger.exception("No se pudieron limpiar los fragmentos del documento eliminado %s", document_id)


def _commit_unless_removed(session: Session, document_id: str) -> bool:
    """Confirma; False si la fila ya no existe (la eliminación se adelantó): entonces limpia y no toca nada más."""
    try:
        session.commit()
    except StaleDataError:
        session.rollback()
        _discard_chunks(document_id)
        return False
    return True


def _ingest_document(document_id: str) -> None:
    with SessionLocal() as session:
        document = session.get(Document, document_id)
        if document is None or is_cancelled(document_id):
            return

        document.status = "processing"
        if not _commit_unless_removed(session, document_id):
            return

        status = "done"
        try:
            path = UPLOAD_DIR / f"{document.id}.{document.source_type}"
            text = get_loader(document.source_type).load(path)
            if not text or not text.strip():
                raise ValueError(f"Documento sin texto extraíble: {path}")

            texts = chunk_text(text)
            embedding_provider = get_embedding_provider(settings.embedding_provider)
            vector_store = get_vector_store()
            for start in range(0, len(texts), INGEST_BATCH_SIZE):
                if _removed(session, document_id):
                    _discard_chunks(document_id)
                    return
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
            logger.exception("Fallo indexando documento %s", document_id)
            status = "error"

        # Se pudo eliminar mientras se procesaba el último lote: no se marca ni se deja nada.
        if _removed(session, document_id):
            _discard_chunks(document_id)
            return
        document.status = status
        _commit_unless_removed(session, document_id)
