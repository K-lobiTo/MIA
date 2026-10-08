import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, StringConstraints
from sqlalchemy import select
from sqlalchemy.orm import Session

from mia.api.security import require_admin
from mia.config import settings
from mia.storage.db import get_session
from mia.storage.models import Document, Domain, Folder, Unit

# Los nombres se recortan y no pueden quedar vacíos.
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]

router = APIRouter(tags=["inventory"])


class DocumentNode(BaseModel):
    id: str
    filename: str
    source_type: str
    status: str
    uploaded_at: str | None
    folder_id: str | None


class FolderNode(BaseModel):
    id: str
    name: str
    parent_id: str | None
    document_count: int
    folders: list["FolderNode"]
    documents: list[DocumentNode]


class DomainNode(BaseModel):
    id: str
    name: str
    description: str
    document_count: int
    folders: list[FolderNode]
    documents: list[DocumentNode]


class UnitNode(BaseModel):
    id: str
    name: str
    description: str
    document_count: int
    domains: list[DomainNode]


class InventoryOut(BaseModel):
    ingestion_enabled: bool
    max_upload_mb: int
    units: list[UnitNode]
    unassigned_domains: list[DomainNode]


class UnitOut(BaseModel):
    id: str
    name: str
    description: str

    model_config = {"from_attributes": True}


def _document_node(document: Document) -> DocumentNode:
    return DocumentNode(
        id=document.id,
        filename=document.filename,
        source_type=document.source_type,
        status=document.status,
        uploaded_at=(document.uploaded_at.isoformat() + "Z") if document.uploaded_at else None,
        folder_id=document.folder_id,
    )


def _folder_nodes(
    parent_id: str | None,
    folders: dict[str | None, list[Folder]],
    documents: dict[str | None, list[Document]],
) -> list[FolderNode]:
    nodes = []
    for folder in sorted(folders.get(parent_id, []), key=lambda f: f.name.lower()):
        children = _folder_nodes(folder.id, folders, documents)
        own = sorted(documents.get(folder.id, []), key=lambda d: d.filename.lower())
        nodes.append(
            FolderNode(
                id=folder.id,
                name=folder.name,
                parent_id=folder.parent_id,
                document_count=len(own) + sum(c.document_count for c in children),
                folders=children,
                documents=[_document_node(d) for d in own],
            )
        )
    return nodes


def _domain_node(
    domain: Domain,
    folders: dict[str | None, list[Folder]],
    documents: dict[str | None, list[Document]],
) -> DomainNode:
    # `folders` y `documents` ya vienen filtrados por dominio; la raíz es la clave None.
    children = _folder_nodes(None, folders, documents)
    own = sorted(documents.get(None, []), key=lambda d: d.filename.lower())
    return DomainNode(
        id=domain.id,
        name=domain.name,
        description=domain.description,
        document_count=len(own) + sum(c.document_count for c in children),
        folders=children,
        documents=[_document_node(d) for d in own],
    )


@router.get("/inventory", response_model=InventoryOut)
def inventory(session: Session = Depends(get_session)) -> InventoryOut:
    """Árbol completo (unidades, dominios, carpetas y documentos) en una sola petición."""
    units = list(session.scalars(select(Unit)))
    domains = list(session.scalars(select(Domain)))
    all_folders = list(session.scalars(select(Folder)))
    all_documents = list(session.scalars(select(Document)))

    folders_by_domain: dict[str, dict[str | None, list[Folder]]] = {}
    for folder in all_folders:
        folders_by_domain.setdefault(folder.domain_id, {}).setdefault(folder.parent_id, []).append(folder)
    documents_by_domain: dict[str, dict[str | None, list[Document]]] = {}
    for document in all_documents:
        documents_by_domain.setdefault(document.domain_id, {}).setdefault(document.folder_id, []).append(
            document
        )

    def node(domain: Domain) -> DomainNode:
        return _domain_node(
            domain, folders_by_domain.get(domain.id, {}), documents_by_domain.get(domain.id, {})
        )

    unit_nodes = []
    for unit in sorted(units, key=lambda u: u.name.lower()):
        domain_nodes = [node(d) for d in sorted(domains, key=lambda d: d.name.lower()) if d.unit_id == unit.id]
        unit_nodes.append(
            UnitNode(
                id=unit.id,
                name=unit.name,
                description=unit.description,
                document_count=sum(d.document_count for d in domain_nodes),
                domains=domain_nodes,
            )
        )
    unassigned = [node(d) for d in sorted(domains, key=lambda d: d.name.lower()) if d.unit_id is None]
    return InventoryOut(
        ingestion_enabled=settings.ingestion_enabled,
        max_upload_mb=settings.max_upload_mb,
        units=unit_nodes,
        unassigned_domains=unassigned,
    )


@router.get("/units", response_model=list[UnitOut])
def list_units(session: Session = Depends(get_session)) -> list[Unit]:
    return sorted(session.scalars(select(Unit)), key=lambda u: u.name.lower())


class UnitCreate(BaseModel):
    name: Name
    description: str = ""


@router.post("/units", response_model=UnitOut, status_code=201, dependencies=[Depends(require_admin)])
def create_unit(payload: UnitCreate, session: Session = Depends(get_session)) -> Unit:
    if session.scalar(select(Unit).where(Unit.name == payload.name)) is not None:
        raise HTTPException(status_code=409, detail=f"Ya existe una unidad llamada '{payload.name}'.")
    unit = Unit(id=str(uuid.uuid4()), name=payload.name, description=payload.description)
    session.add(unit)
    session.commit()
    session.refresh(unit)
    return unit


class FolderCreate(BaseModel):
    name: Name
    parent_id: str | None = None


class FolderRename(BaseModel):
    name: Name


class FolderOut(BaseModel):
    id: str
    domain_id: str
    parent_id: str | None
    name: str

    model_config = {"from_attributes": True}


def _sibling(session: Session, domain_id: str, parent_id: str | None, name: str, exclude_id: str | None = None):
    # En SQL un parent_id nulo no participa de una restricción única: en la raíz del dominio la
    # unicidad del nombre se verifica aquí.
    query = select(Folder).where(Folder.domain_id == domain_id, Folder.name == name)
    query = query.where(Folder.parent_id.is_(None) if parent_id is None else Folder.parent_id == parent_id)
    if exclude_id:
        query = query.where(Folder.id != exclude_id)
    return session.scalar(query)


@router.post(
    "/domains/{domain_id}/folders", response_model=FolderOut, status_code=201, dependencies=[Depends(require_admin)]
)
def create_folder(domain_id: str, payload: FolderCreate, session: Session = Depends(get_session)) -> Folder:
    if session.get(Domain, domain_id) is None:
        raise HTTPException(status_code=404, detail="Dominio no encontrado.")
    if payload.parent_id is not None:
        parent = session.get(Folder, payload.parent_id)
        if parent is None:
            raise HTTPException(status_code=404, detail="La carpeta padre no existe.")
        if parent.domain_id != domain_id:
            raise HTTPException(status_code=422, detail="La carpeta padre pertenece a otro dominio.")
    if _sibling(session, domain_id, payload.parent_id, payload.name) is not None:
        raise HTTPException(status_code=409, detail=f"Ya existe una carpeta '{payload.name}' en ese nivel.")
    folder = Folder(id=str(uuid.uuid4()), domain_id=domain_id, parent_id=payload.parent_id, name=payload.name)
    session.add(folder)
    session.commit()
    session.refresh(folder)
    return folder


@router.patch("/folders/{folder_id}", response_model=FolderOut, dependencies=[Depends(require_admin)])
def rename_folder(folder_id: str, payload: FolderRename, session: Session = Depends(get_session)) -> Folder:
    folder = session.get(Folder, folder_id)
    if folder is None:
        raise HTTPException(status_code=404, detail="Carpeta no encontrada.")
    if _sibling(session, folder.domain_id, folder.parent_id, payload.name, exclude_id=folder.id) is not None:
        raise HTTPException(status_code=409, detail=f"Ya existe una carpeta '{payload.name}' en ese nivel.")
    folder.name = payload.name
    session.commit()
    session.refresh(folder)
    return folder


@router.delete("/folders/{folder_id}", status_code=204, dependencies=[Depends(require_admin)])
def delete_folder(folder_id: str, session: Session = Depends(get_session)) -> Response:
    folder = session.get(Folder, folder_id)
    if folder is None:
        raise HTTPException(status_code=404, detail="Carpeta no encontrada.")
    has_documents = session.scalar(select(Document.id).where(Document.folder_id == folder_id).limit(1))
    has_children = session.scalar(select(Folder.id).where(Folder.parent_id == folder_id).limit(1))
    if has_documents is not None or has_children is not None:
        raise HTTPException(
            status_code=409,
            detail="La carpeta debe estar vacía (sin documentos ni subcarpetas) para borrarla.",
        )
    session.delete(folder)
    session.commit()
    return Response(status_code=204)
