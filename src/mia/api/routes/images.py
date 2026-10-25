"""Imágenes asociadas a documentos (feature 011): rutas de administración por documento que usa el diálogo "Imágenes" del
Inventario del panel. Contrato en specs/011-bot-whatsapp-kapso/contracts/imagenes-api.md.

Requieren administración y el mismo alcance que ya se tiene sobre el documento (el dominio del documento). Una imagen se
valida por su contenido (PNG o JPG completo, hasta MAX_IMAGE_MB); reemplazarla conserva su descripción y su posición y le
da un identificador público nuevo, así el enlace anterior deja de servir. El contenido nunca va al registro de administración.
"""

import secrets
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Response, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from mia.access import audit
from mia.access.guards import ensure_domain
from mia.access.scope import Principal
from mia.api.security import require_admin
from mia.config import settings
from mia.images.validate import MAX_CAPTION, ImageFormatError, ImageIncompleteError, validate_image
from mia.storage.db import get_session
from mia.storage.models import Document, DocumentImage, Domain

router = APIRouter(tags=["images"])

BASE = "/domains/{domain_id}/documents/{document_id}/images"


class ImageOut(BaseModel):
    id: str
    public_id: str
    url: str
    content_type: str
    size_bytes: int
    caption: str
    position: int


class ImagesOut(BaseModel):
    images: list[ImageOut]
    max_image_mb: int


class OrderOut(BaseModel):
    images: list[ImageOut]


class CaptionUpdate(BaseModel):
    caption: str = Field(max_length=MAX_CAPTION)


class OrderIn(BaseModel):
    image_ids: list[str]


def _out(image: DocumentImage) -> ImageOut:
    return ImageOut(
        id=image.id,
        public_id=image.public_id,
        url=f"/media/{image.public_id}",
        content_type=image.content_type,
        size_bytes=image.size_bytes,
        caption=image.caption,
        position=image.position,
    )


def _document(session: Session, principal: Principal, domain_id: str, document_id: str, action: str) -> Document:
    """El documento de la ruta, con el alcance comprobado. Un documento que no es del dominio de la ruta no existe."""
    domain = session.get(Domain, domain_id)
    if domain is None:
        raise HTTPException(status_code=404, detail="Dominio no encontrado.")
    ensure_domain(principal, domain, action)
    document = session.get(Document, document_id)
    if document is None or document.domain_id != domain_id:
        raise HTTPException(status_code=404, detail="Documento no encontrado.")
    return document


def _image(session: Session, document: Document, image_id: str) -> DocumentImage:
    image = session.get(DocumentImage, image_id)
    if image is None or image.document_id != document.id:
        raise HTTPException(status_code=404, detail="Imagen no encontrada.")
    return image


def _ordered(session: Session, document_id: str) -> list[DocumentImage]:
    # El binario es `deferred`: no se lee al listar.
    return list(
        session.scalars(
            select(DocumentImage).where(DocumentImage.document_id == document_id).order_by(DocumentImage.position)
        )
    )


def _read_image(file: UploadFile) -> tuple[bytes, str]:
    """El contenido y su tipo, con los errores del contrato en su orden: tamaño (413), formato (415), imagen incompleta
    (422). Se lee un byte de más del límite para detectar el exceso sin cargar en memoria un archivo enorme."""
    limit = settings.max_image_mb * 1024 * 1024
    content = file.file.read(limit + 1)
    if len(content) > limit:
        raise HTTPException(status_code=413, detail=f"La imagen supera el tamaño máximo de {settings.max_image_mb} MB.")
    try:
        return content, validate_image(content)
    except ImageFormatError as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    except ImageIncompleteError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get(BASE, response_model=ImagesOut)
def list_images(
    domain_id: str,
    document_id: str,
    principal: Principal = Depends(require_admin),
    session: Session = Depends(get_session),
) -> ImagesOut:
    document = _document(session, principal, domain_id, document_id, "image.list")
    return ImagesOut(images=[_out(i) for i in _ordered(session, document.id)], max_image_mb=settings.max_image_mb)


@router.post(BASE, response_model=ImageOut, status_code=201)
def add_image(
    domain_id: str,
    document_id: str,
    file: UploadFile,
    caption: Annotated[str | None, Form()] = None,
    principal: Principal = Depends(require_admin),
    session: Session = Depends(get_session),
) -> ImageOut:
    document = _document(session, principal, domain_id, document_id, "image.create")
    content, content_type = _read_image(file)
    caption = caption or ""
    if len(caption) > MAX_CAPTION:
        raise HTTPException(status_code=422, detail=f"La descripción tiene como máximo {MAX_CAPTION} caracteres.")
    last = session.scalar(select(func.max(DocumentImage.position)).where(DocumentImage.document_id == document.id))
    image = DocumentImage(
        id=str(uuid.uuid4()),
        document_id=document.id,
        public_id=secrets.token_urlsafe(24),
        content_type=content_type,
        content=content,
        size_bytes=len(content),
        caption=caption,
        position=0 if last is None else last + 1,
        created_by=principal.label,
    )
    session.add(image)
    session.commit()
    session.refresh(image)
    audit.log_write(principal, "image.create", image.id, document.filename)
    return _out(image)


# `order` se declara antes que `{image_id}` para que no se tome como el id de una imagen.
@router.put(f"{BASE}/order", response_model=OrderOut)
def reorder_images(
    domain_id: str,
    document_id: str,
    payload: OrderIn,
    principal: Principal = Depends(require_admin),
    session: Session = Depends(get_session),
) -> OrderOut:
    document = _document(session, principal, domain_id, document_id, "image.reorder")
    images = _ordered(session, document.id)
    if sorted(payload.image_ids) != sorted(i.id for i in images):
        raise HTTPException(
            status_code=422,
            detail="La lista debe tener exactamente las imágenes del documento, cada una una vez. Recarga la lista.",
        )
    by_id = {i.id: i for i in images}
    for position, image_id in enumerate(payload.image_ids):
        by_id[image_id].position = position
    session.commit()
    audit.log_write(principal, "image.reorder", document.id, document.filename)
    return OrderOut(images=[_out(i) for i in _ordered(session, document.id)])


@router.put(f"{BASE}/{{image_id}}", response_model=ImageOut)
def replace_image(
    domain_id: str,
    document_id: str,
    image_id: str,
    file: UploadFile,
    principal: Principal = Depends(require_admin),
    session: Session = Depends(get_session),
) -> ImageOut:
    document = _document(session, principal, domain_id, document_id, "image.replace")
    image = _image(session, document, image_id)
    content, content_type = _read_image(file)
    # Conserva descripción y posición. El identificador público cambia: el enlace anterior deja de servir.
    image.content = content
    image.content_type = content_type
    image.size_bytes = len(content)
    image.public_id = secrets.token_urlsafe(24)
    session.commit()
    session.refresh(image)
    audit.log_write(principal, "image.replace", image.id, document.filename)
    return _out(image)


@router.patch(f"{BASE}/{{image_id}}", response_model=ImageOut)
def update_caption(
    domain_id: str,
    document_id: str,
    image_id: str,
    payload: CaptionUpdate,
    principal: Principal = Depends(require_admin),
    session: Session = Depends(get_session),
) -> ImageOut:
    document = _document(session, principal, domain_id, document_id, "image.update")
    image = _image(session, document, image_id)
    image.caption = payload.caption
    session.commit()
    session.refresh(image)
    audit.log_write(principal, "image.update", image.id, document.filename)
    return _out(image)


@router.delete(f"{BASE}/{{image_id}}", status_code=204)
def delete_image(
    domain_id: str,
    document_id: str,
    image_id: str,
    principal: Principal = Depends(require_admin),
    session: Session = Depends(get_session),
) -> Response:
    document = _document(session, principal, domain_id, document_id, "image.delete")
    image = _image(session, document, image_id)
    session.delete(image)
    session.flush()
    # Las posiciones quedan desde 0 y sin huecos.
    for position, remaining in enumerate(_ordered(session, document.id)):
        remaining.position = position
    session.commit()
    audit.log_write(principal, "image.delete", image_id, document.filename)
    return Response(status_code=204)
