"""Eliminación de documentos (feature 012). Contrato en specs/012-eliminar-documentos/contracts/eliminar-documentos-api.md.

Requiere administración y el mismo alcance que ya se tiene para subir el documento (el dominio del documento). La API
elimina al recibir el pedido: la confirmación es del panel. La línea `document.delete` del registro de administración
lleva el nombre y el dominio, nunca el contenido."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from mia.access import audit
from mia.access.errors import AuthError
from mia.access.guards import ensure_domain
from mia.access.scope import Principal
from mia.api.security import require_admin
from mia.config import settings
from mia.ingestion.pipeline import UPLOAD_DIR
from mia.ingestion.removal import DocumentBusy, DocumentNotFound, StoreUnavailable, remove_document
from mia.storage.db import get_session
from mia.storage.models import Document, Domain
from mia.storage.vector_store import get_vector_store

router = APIRouter(tags=["documents"])

BUSY_MESSAGE = "El documento se está procesando; intenta de nuevo en un momento."
STORE_MESSAGE = (
    "No se pudo quitar el contenido del documento del almacén de búsqueda; el documento sigue como estaba. "
    "Intenta de nuevo."
)


@router.delete("/domains/{domain_id}/documents/{document_id}", status_code=204)
def delete_document(
    domain_id: str,
    document_id: str,
    principal: Principal = Depends(require_admin),
    session: Session = Depends(get_session),
) -> Response:
    domain = session.get(Domain, domain_id)
    if domain is None:
        raise HTTPException(status_code=404, detail="Dominio no encontrado.")
    ensure_domain(principal, domain, "document.delete")
    document = session.get(Document, document_id)
    if document is None or document.domain_id != domain_id:
        raise HTTPException(status_code=404, detail="Documento no encontrado.")

    filename = document.filename
    try:
        remove_document(session, get_vector_store(), document, UPLOAD_DIR, settings.delete_wait_seconds)
    except DocumentNotFound as exc:
        raise HTTPException(status_code=404, detail="Documento no encontrado.") from exc
    except DocumentBusy as exc:
        raise HTTPException(status_code=409, detail=BUSY_MESSAGE) from exc
    except StoreUnavailable as exc:
        raise HTTPException(status_code=503, detail=STORE_MESSAGE) from exc

    audit.log_write(principal, "document.delete", document_id, f"{filename} en {domain.name}")
    return Response(status_code=204)


MAX_BULK = 100


class BulkDeleteIn(BaseModel):
    document_ids: list[str] = Field(min_length=1, max_length=MAX_BULK)


class BulkDeleteItem(BaseModel):
    document_id: str
    filename: str | None = None
    status: Literal["deleted", "not_found", "out_of_scope", "busy", "error"]
    detail: str | None = None


class BulkDeleteOut(BaseModel):
    deleted: int
    failed: int
    results: list[BulkDeleteItem]


@router.post("/documents/bulk-delete", response_model=BulkDeleteOut, response_model_exclude_none=True)
def bulk_delete_documents(
    body: BulkDeleteIn,
    principal: Principal = Depends(require_admin),
    session: Session = Depends(get_session),
) -> BulkDeleteOut:
    """Cada documento se valida y se elimina por separado: uno que falla no impide los demás."""
    vector_store = get_vector_store()
    results: list[BulkDeleteItem] = []
    for document_id in dict.fromkeys(body.document_ids):
        document = session.get(Document, document_id)
        if document is None:
            results.append(BulkDeleteItem(document_id=document_id, status="not_found"))
            continue
        filename = document.filename
        domain = session.get(Domain, document.domain_id)
        try:
            ensure_domain(principal, domain, "document.delete")
        except AuthError as exc:
            results.append(
                BulkDeleteItem(document_id=document_id, filename=filename, status="out_of_scope", detail=exc.detail)
            )
            continue
        domain_name = domain.name
        try:
            remove_document(session, vector_store, document, UPLOAD_DIR, settings.delete_wait_seconds)
        except DocumentNotFound:
            results.append(BulkDeleteItem(document_id=document_id, status="not_found"))
        except DocumentBusy:
            results.append(BulkDeleteItem(document_id=document_id, filename=filename, status="busy", detail=BUSY_MESSAGE))
        except StoreUnavailable:
            results.append(BulkDeleteItem(document_id=document_id, filename=filename, status="error", detail=STORE_MESSAGE))
        else:
            audit.log_write(principal, "document.delete", document_id, f"{filename} en {domain_name}")
            results.append(BulkDeleteItem(document_id=document_id, filename=filename, status="deleted"))
    deleted = sum(1 for r in results if r.status == "deleted")
    return BulkDeleteOut(deleted=deleted, failed=len(results) - deleted, results=results)
