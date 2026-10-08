from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from mia.config import settings
from mia.storage.db import get_session
from mia.storage.models import Document, Domain, Folder, Unit

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
        ingestion_enabled=settings.ingestion_enabled, units=unit_nodes, unassigned_domains=unassigned
    )


@router.get("/units", response_model=list[UnitOut])
def list_units(session: Session = Depends(get_session)) -> list[Unit]:
    return sorted(session.scalars(select(Unit)), key=lambda u: u.name.lower())
