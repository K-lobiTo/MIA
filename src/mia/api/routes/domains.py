import hashlib
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from mia.ingestion.pipeline import UPLOAD_DIR, ingest_document
from mia.storage.db import get_session
from mia.storage.models import Document, Domain

router = APIRouter(tags=["domains"])


class DomainCreate(BaseModel):
    name: str
    description: str = ""


class DomainOut(BaseModel):
    id: str
    name: str
    description: str

    model_config = {"from_attributes": True}


class DocumentOut(BaseModel):
    id: str
    filename: str
    source_type: str
    status: str

    model_config = {"from_attributes": True}


@router.post("/domains", response_model=DomainOut)
def create_domain(payload: DomainCreate, session: Session = Depends(get_session)) -> Domain:
    domain = Domain(id=str(uuid.uuid4()), name=payload.name, description=payload.description)
    session.add(domain)
    session.commit()
    session.refresh(domain)
    return domain


@router.get("/domains", response_model=list[DomainOut])
def list_domains(session: Session = Depends(get_session)) -> list[Domain]:
    return list(session.scalars(select(Domain)))


@router.post("/domains/{domain_id}/documents", response_model=DocumentOut)
def upload_document(
    domain_id: str,
    file: UploadFile,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
) -> Document:
    domain = session.get(Domain, domain_id)
    if domain is None:
        raise HTTPException(status_code=404, detail="Dominio no encontrado")

    source_type = Path(file.filename or "").suffix.lstrip(".").lower()
    if source_type not in {"pdf", "docx", "txt"}:
        raise HTTPException(status_code=400, detail=f"Tipo de fuente no soportado: {source_type}")

    content = file.file.read()
    file_hash = hashlib.sha256(content).hexdigest()

    existing = session.scalar(
        select(Document).where(Document.domain_id == domain_id, Document.file_hash == file_hash)
    )
    if existing is not None:
        return existing

    UPLOAD_DIR.mkdir(exist_ok=True)
    document_id = str(uuid.uuid4())
    dest = UPLOAD_DIR / f"{document_id}.{source_type}"
    dest.write_bytes(content)

    document = Document(
        id=document_id,
        domain_id=domain_id,
        filename=file.filename or dest.name,
        source_type=source_type,
        file_hash=file_hash,
        status="pending",
    )
    session.add(document)
    session.commit()
    session.refresh(document)

    background_tasks.add_task(ingest_document, document.id)

    return document


@router.get("/domains/{domain_id}/documents", response_model=list[DocumentOut])
def list_documents(domain_id: str, session: Session = Depends(get_session)) -> list[Document]:
    return list(session.scalars(select(Document).where(Document.domain_id == domain_id)))
