import logging
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

logger = logging.getLogger(__name__)


def ingest_document(document_id: str) -> None:
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
            embeddings = embedding_provider.embed(texts, is_query=False)

            chunks = [
                Chunk(
                    id=str(uuid.uuid4()),
                    document_id=document.id,
                    domain=document.domain_id,
                    text=chunk_text_value,
                    chunk_index=index,
                    embedding=embedding,
                )
                for index, (chunk_text_value, embedding) in enumerate(zip(texts, embeddings))
            ]
            get_vector_store().upsert(chunks)
        except Exception:
            logger.exception("Fallo indexando documento %s", document.id)
            document.status = "error"
        else:
            document.status = "done"
        finally:
            session.commit()
