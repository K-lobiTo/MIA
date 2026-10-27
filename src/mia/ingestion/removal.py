"""Eliminación de un documento (feature 012): lo quita de la base, del almacén de vectores y del disco.

El orden es lo que importa (specs/012-eliminar-documentos/research.md R1): la base se modifica dentro de una
transacción que todavía no se confirma, después se borran y se verifican los fragmentos, y solo entonces se confirma.
Así un documento nunca sale del inventario mientras sus fragmentos siguen respondiendo; si falla el almacén se
descarta la transacción y el documento queda como estaba."""

import logging
from pathlib import Path

from sqlalchemy import delete, update
from sqlalchemy.exc import InvalidRequestError
from sqlalchemy.orm import Session

from mia.ingestion import pipeline
from mia.storage.models import Document, DocumentImage
from mia.storage.vector_store import VectorStore

logger = logging.getLogger(__name__)


class DocumentNotFound(Exception):
    """El documento ya no existe (por ejemplo, otra persona lo eliminó antes)."""


class DocumentBusy(Exception):
    """El documento se está procesando y la ingesta no soltó el cerrojo a tiempo."""


class StoreUnavailable(Exception):
    """No se pudieron quitar los fragmentos del almacén de vectores; el documento quedó como estaba."""


def remove_document(
    session: Session, vector_store: VectorStore, document: Document, upload_dir: Path, wait_seconds: float
) -> None:
    """Elimina el documento por completo. Coordina con la ingesta (research R3): uno en cola solo se marca como
    cancelado, uno que se está procesando además espera (hasta `wait_seconds`) a que la ingesta se detenga, y los listos
    o con error no necesitan coordinación."""
    try:
        session.refresh(document)
    except InvalidRequestError as exc:  # la fila ya no existe
        session.rollback()
        raise DocumentNotFound(document.id) from exc
    document_id = document.id
    status = document.status

    if status not in ("pending", "processing"):
        _remove(session, vector_store, document, upload_dir)
        return

    pipeline.request_cancel(document_id)
    holds_lock = False
    try:
        if status == "processing":
            if not pipeline.acquire_ingest_lock(wait_seconds):
                raise DocumentBusy(document_id)
            holds_lock = True
        _remove(session, vector_store, document, upload_dir)
    except StoreUnavailable:
        # La ingesta pudo detenerse por la cancelación y el documento sigue en la base: no se queda "Procesando". El
        # UPDATE solo toca a uno que esté `processing` (también el que se leyó `pending` y arrancó justo entonces).
        _mark_error(session, document_id)
        raise
    finally:
        if holds_lock:
            pipeline.release_ingest_lock()
        pipeline.clear_cancel(document_id)


def _mark_error(session: Session, document_id: str) -> None:
    try:
        session.execute(
            update(Document).where(Document.id == document_id, Document.status == "processing").values(status="error")
        )
        session.commit()
    except Exception:
        session.rollback()
        logger.exception("No se pudo marcar con error el documento %s", document_id)


def _remove(session: Session, vector_store: VectorStore, document: Document, upload_dir: Path) -> None:
    document_id, source_type = document.id, document.source_type

    session.execute(delete(DocumentImage).where(DocumentImage.document_id == document_id))
    borradas = session.execute(delete(Document).where(Document.id == document_id)).rowcount
    if not borradas:
        session.rollback()
        raise DocumentNotFound(document_id)
    session.flush()

    try:
        vector_store.delete_document(document_id)
        restantes = vector_store.count_chunks(document_id)
    except Exception as exc:
        session.rollback()
        logger.exception("No se pudieron quitar los fragmentos del documento %s", document_id)
        raise StoreUnavailable(document_id) from exc
    if restantes:
        session.rollback()
        logger.error("Quedan %s fragmentos del documento %s tras borrarlos", restantes, document_id)
        raise StoreUnavailable(document_id)

    session.commit()

    try:
        (upload_dir / f"{document_id}.{source_type}").unlink(missing_ok=True)
    except OSError:
        logger.warning("No se pudo borrar el archivo original del documento %s", document_id, exc_info=True)
