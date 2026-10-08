import hashlib
import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, Response, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from mia.access.permissions import allowed_domain_ids
from mia.api.routes.inventory import Name
from mia.api.security import optional_artifact, require_admin
from mia.config import settings
from mia.ingestion.pipeline import UPLOAD_DIR, ingest_document
from mia.storage.db import get_session
from mia.storage.models import Artifact, ArtifactUnit, Document, Domain, Folder, Unit

router = APIRouter(tags=["domains"])


class DomainCreate(BaseModel):
    unit_id: str
    name: Name
    description: str = ""


class DomainOut(BaseModel):
    id: str
    unit_id: str | None
    unit_name: str | None
    name: str
    description: str


class VisibleTo(BaseModel):
    now: list[str]
    needs_enabling: list[str]


class DomainCreated(BaseModel):
    id: str
    unit_id: str
    name: str
    description: str
    visible_to: VisibleTo


class DocumentOut(BaseModel):
    id: str
    filename: str
    source_type: str
    status: str
    folder_id: str | None = None
    already_existed: bool = False

    model_config = {"from_attributes": True}


def _visible_to(session: Session, unit_id: str) -> VisibleTo:
    """Artefactos activos que verán el dominio nuevo de inmediato (acceso a todos los dominios o a
    la unidad) y los que necesitan que se les habilite (INV-12)."""
    with_unit = set(session.scalars(select(ArtifactUnit.artifact_id).where(ArtifactUnit.unit_id == unit_id)))
    now, needs_enabling = [], []
    for artifact in session.scalars(select(Artifact).where(Artifact.active.is_(True)).order_by(Artifact.name)):
        (now if artifact.all_domains or artifact.id in with_unit else needs_enabling).append(artifact.name)
    return VisibleTo(now=now, needs_enabling=needs_enabling)


@router.post("/domains", response_model=DomainCreated, status_code=201, dependencies=[Depends(require_admin)])
def create_domain(payload: DomainCreate, session: Session = Depends(get_session)) -> DomainCreated:
    if session.get(Unit, payload.unit_id) is None:
        raise HTTPException(status_code=404, detail="Unidad no encontrada.")
    existing = session.scalar(select(Domain).where(Domain.unit_id == payload.unit_id, Domain.name == payload.name))
    if existing is not None:
        raise HTTPException(status_code=409, detail=f"Ya existe un dominio '{payload.name}' en esa unidad.")
    domain = Domain(
        id=str(uuid.uuid4()), unit_id=payload.unit_id, name=payload.name, description=payload.description
    )
    session.add(domain)
    session.commit()
    return DomainCreated(
        id=domain.id,
        unit_id=payload.unit_id,
        name=domain.name,
        description=domain.description,
        visible_to=_visible_to(session, payload.unit_id),
    )


@router.get("/domains", response_model=list[DomainOut])
def list_domains(
    artifact: Artifact | None = Depends(optional_artifact), session: Session = Depends(get_session)
) -> list[DomainOut]:
    """Sin clave, todos los dominios (como hoy). Con la clave de un artefacto, solo los que puede consultar."""
    units = {u.id: u.name for u in session.scalars(select(Unit))}
    allowed = allowed_domain_ids(session, artifact) if artifact is not None else None
    return [
        DomainOut(
            id=d.id, unit_id=d.unit_id, unit_name=units.get(d.unit_id), name=d.name, description=d.description
        )
        for d in session.scalars(select(Domain))
        if allowed is None or d.id in allowed
    ]


@router.post(
    "/domains/{domain_id}/documents",
    response_model=DocumentOut,
    status_code=201,
    dependencies=[Depends(require_admin)],
)
def upload_document(
    domain_id: str,
    file: UploadFile,
    background_tasks: BackgroundTasks,
    response: Response,
    folder_id: Annotated[str | None, Form()] = None,
    session: Session = Depends(get_session),
) -> DocumentOut:
    if not settings.ingestion_enabled:
        raise HTTPException(
            status_code=503,
            detail=(
                "La ingesta de documentos está desactivada en esta instancia. "
                "Ingerir desde una instancia local (ver docs/OPERACION.md)."
            ),
        )

    domain = session.get(Domain, domain_id)
    if domain is None:
        raise HTTPException(status_code=404, detail="Dominio no encontrado")

    source_type = Path(file.filename or "").suffix.lstrip(".").lower()
    if source_type not in {"pdf", "docx", "txt"}:
        raise HTTPException(status_code=400, detail=f"Tipo de fuente no soportado: {source_type}")

    if folder_id is not None:
        folder = session.get(Folder, folder_id)
        if folder is None:
            raise HTTPException(status_code=404, detail="La carpeta no existe.")
        if folder.domain_id != domain_id:
            raise HTTPException(status_code=422, detail="La carpeta pertenece a otro dominio.")

    # Se lee un byte de más para detectar el exceso sin cargar en memoria un archivo enorme.
    limit = settings.max_upload_mb * 1024 * 1024
    content = file.file.read(limit + 1)
    if len(content) > limit:
        raise HTTPException(
            status_code=413, detail=f"El archivo supera el tamaño máximo de {settings.max_upload_mb} MB."
        )
    file_hash = hashlib.sha256(content).hexdigest()

    # Duplicado: mismo contenido en el dominio, en cualquiera de sus carpetas (INV-6).
    existing = session.scalar(
        select(Document).where(Document.domain_id == domain_id, Document.file_hash == file_hash)
    )
    if existing is not None:
        response.status_code = 200
        return DocumentOut.model_validate(existing).model_copy(update={"already_existed": True})

    UPLOAD_DIR.mkdir(exist_ok=True)
    document_id = str(uuid.uuid4())
    dest = UPLOAD_DIR / f"{document_id}.{source_type}"
    dest.write_bytes(content)

    document = Document(
        id=document_id,
        domain_id=domain_id,
        folder_id=folder_id,
        filename=file.filename or dest.name,
        source_type=source_type,
        file_hash=file_hash,
        status="pending",
    )
    session.add(document)
    try:
        session.commit()
    except IntegrityError as exc:
        # La carpeta pudo borrarse entre la validación y el guardado: no deja el archivo huérfano.
        session.rollback()
        dest.unlink(missing_ok=True)
        if folder_id is not None and session.get(Folder, folder_id) is None:
            raise HTTPException(status_code=404, detail="La carpeta ya no existe.") from exc
        raise
    session.refresh(document)

    if settings.ingestion_sync:
        ingest_document(document.id)
        session.refresh(document)
    else:
        background_tasks.add_task(ingest_document, document.id)

    return DocumentOut.model_validate(document)


@router.get("/domains/{domain_id}/documents", response_model=list[DocumentOut])
def list_documents(domain_id: str, session: Session = Depends(get_session)) -> list[Document]:
    return list(session.scalars(select(Document).where(Document.domain_id == domain_id)))
