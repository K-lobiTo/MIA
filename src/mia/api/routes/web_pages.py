"""Agregar una página web como fuente (feature 022). Contrato en specs/022-ingesta-web-basica/contracts/pagina-web-api.md.

`POST /domains/{id}/web-pages` lee **una** página en la misma petición, comprueba que se puede leer y, solo entonces, crea el
documento (tipo `web`) con el texto extraído. Si no se puede leer, responde con un código de rechazo y un mensaje y no crea
nada; todo rechazo queda en el registro de administración, sin contenido de la página."""

import hashlib
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from mia.access import audit
from mia.access.guards import ensure_domain
from mia.access.scope import Principal
from mia.api.routes.domains import DocumentOut
from mia.api.security import require_admin
from mia.config import settings
from mia.ingestion.pipeline import UPLOAD_DIR, ingest_document
from mia.ingestion.web.detect import revisar_respuesta, revisar_texto
from mia.ingestion.web.errors import WebRejection, rechazo
from mia.ingestion.web.extract import armar_documento, extraer, fecha_larga, nombre_del_documento
from mia.ingestion.web.fetcher import get_page_fetcher
from mia.ingestion.web.urls import (
    clave_de_comparacion,
    direccion_para_auditoria,
    normalizar_entrada,
)
from mia.storage.db import get_session
from mia.storage.models import Document, Domain, Folder

router = APIRouter(tags=["web-pages"])

ACCION = "document.add_web"


class WebPageIn(BaseModel):
    # Sin límites de largo en el modelo: un `422` de validación de FastAPI trae `detail` como lista y el panel lo mostraría
    # como "[object Object]". El vacío y el largo de la dirección los valida `normalizar_entrada` (`invalid_url`, 400).
    url: str | None = None
    name: str | None = None
    folder_id: str | None = None


def _respuesta_de_rechazo(exc: WebRejection) -> JSONResponse:
    return JSONResponse(status_code=exc.status, content={"detail": exc.message, "code": exc.code, **exc.extra})


def _ya_agregada(session: Session, domain_id: str, url: str) -> None:
    """`already_added` si el dominio ya tiene un documento web de esa dirección (por su clave de comparación), aunque la
    página haya cambiado: hay un solo documento web por dirección y no se reemplaza solo (FR-015a)."""
    clave = clave_de_comparacion(url)
    existentes = session.scalars(select(Document).where(Document.domain_id == domain_id, Document.source_url.is_not(None)))
    for existente in existentes:
        if clave_de_comparacion(existente.source_url) == clave:
            raise rechazo(
                "already_added",
                fecha=fecha_larga(existente.uploaded_at),
                document_id=existente.id,
                read_at=existente.uploaded_at.isoformat(),
            )


def _rechazar(principal: Principal, domain_id: str, url: str | None, exc: WebRejection) -> JSONResponse:
    """Audita el rechazo (quién, la dirección sin consulta ni credenciales y el código; nunca contenido) y responde."""
    detalle = f"{exc.code} {direccion_para_auditoria(url or '')}"
    audit.log_write(principal, ACCION, domain_id, detalle, result="rechazado")
    return _respuesta_de_rechazo(exc)


@router.post("/domains/{domain_id}/web-pages", response_model=DocumentOut, status_code=201)
def add_web_page(
    domain_id: str,
    body: WebPageIn,
    background_tasks: BackgroundTasks,
    response: Response,
    principal: Principal = Depends(require_admin),
    session: Session = Depends(get_session),
):
    if not settings.ingestion_enabled:
        return _rechazar(principal, domain_id, body.url, rechazo("ingestion_disabled"))

    domain = session.get(Domain, domain_id)
    if domain is None:
        raise HTTPException(status_code=404, detail="Dominio no encontrado")
    ensure_domain(principal, domain, ACCION)

    try:
        url = normalizar_entrada(body.url)
        folder_id = body.folder_id
        if folder_id is not None:
            folder = session.get(Folder, folder_id)
            if folder is None:
                raise HTTPException(status_code=404, detail="La carpeta no existe.")
            if folder.domain_id != domain_id:
                raise HTTPException(status_code=422, detail="La carpeta pertenece a otro dominio.")

        _ya_agregada(session, domain_id, url)  # antes de leer: no se hace una lectura inútil

        pagina = get_page_fetcher().fetch(url)
        _ya_agregada(session, domain_id, pagina.url_final)  # la dirección a la que llevó una redirección
        revisar_respuesta(pagina)
        extraido = extraer(pagina.cuerpo, pagina.url_final, pagina.codificacion)
        revisar_texto(pagina, extraido)
        nombre = nombre_del_documento(body.name, extraido.titulo, pagina.url_final)
        texto = armar_documento(pagina.url_final, nombre, extraido.texto, datetime.now(UTC))
        if len(texto.encode("utf-8")) > settings.max_upload_mb * 1024 * 1024:
            raise rechazo("text_too_large", mb=settings.max_upload_mb)
    except WebRejection as exc:
        return _rechazar(principal, domain_id, body.url, exc)

    file_hash = hashlib.sha256(texto.encode("utf-8")).hexdigest()
    # Duplicado por contenido: el mismo texto ya está en el dominio, en cualquiera de sus carpetas (como un archivo repetido).
    existente = session.scalar(select(Document).where(Document.domain_id == domain_id, Document.file_hash == file_hash))
    if existente is not None:
        response.status_code = 200
        return DocumentOut.model_validate(existente).model_copy(update={"already_existed": True})

    UPLOAD_DIR.mkdir(exist_ok=True)
    document_id = str(uuid.uuid4())
    destino = UPLOAD_DIR / f"{document_id}.web"
    destino.write_text(texto, encoding="utf-8")

    document = Document(
        id=document_id,
        domain_id=domain_id,
        folder_id=folder_id,
        filename=nombre,
        source_type="web",
        file_hash=file_hash,
        status="pending",
        source_url=pagina.url_final,
        source_text=texto,
    )
    session.add(document)
    try:
        session.commit()
    except IntegrityError as exc:
        # La carpeta pudo borrarse entre la validación y el guardado: no deja el archivo huérfano.
        session.rollback()
        destino.unlink(missing_ok=True)
        if folder_id is not None and session.get(Folder, folder_id) is None:
            raise HTTPException(status_code=404, detail="La carpeta ya no existe.") from exc
        raise
    session.refresh(document)
    audit.log_write(principal, ACCION, document.id, f"{document.filename} en {domain.name}")

    if settings.ingestion_sync:
        ingest_document(document.id)
        session.refresh(document)
    else:
        background_tasks.add_task(ingest_document, document.id)

    return DocumentOut.model_validate(document)


class DocumentTextOut(BaseModel):
    text: str
    source_url: str | None
    read_at: datetime | None
    filename: str


@router.get("/domains/{domain_id}/documents/{document_id}/text", response_model=DocumentTextOut)
def get_document_text(
    domain_id: str,
    document_id: str,
    principal: Principal = Depends(require_admin),
    session: Session = Depends(get_session),
) -> DocumentTextOut:
    """El texto extraído de un documento web, para revisarlo. Solo lectura: no se audita."""
    domain = session.get(Domain, domain_id)
    if domain is None:
        raise HTTPException(status_code=404, detail="Dominio no encontrado")
    ensure_domain(principal, domain, "document.text")
    document = session.get(Document, document_id)
    if document is None or document.domain_id != domain_id or document.source_type != "web" or not document.source_text:
        raise HTTPException(status_code=404, detail="Documento no encontrado.")
    return DocumentTextOut(
        text=document.source_text,
        source_url=document.source_url,
        read_at=document.uploaded_at,
        filename=document.filename,
    )
