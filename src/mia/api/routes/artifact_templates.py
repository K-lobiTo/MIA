"""Plantillas del artefacto en el panel (feature 020): la administración agrega, edita y elimina el catálogo de plantillas que
ve toda persona que consulta con el artefacto. Mismo alcance que `PATCH /artifacts/{id}`: un artefacto fuera del alcance
responde igual que uno inexistente. Cada escritura queda en el registro de administración con el nombre de la plantilla y
nunca con su contenido.
Contrato en specs/020-modo-plantilla/contracts/plantillas-api.md."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from mia.access import audit
from mia.access.scope import Principal, artifact_in_scope
from mia.api.routes.templates import TemplateOut, template_out
from mia.api.security import require_admin
from mia.config import settings
from mia.storage.db import get_session
from mia.storage.models import Artifact, ResponseTemplate
from mia.templates import service

router = APIRouter(tags=["artifact-templates"])

DUPLICATE = "Ya hay una plantilla del artefacto con ese nombre."


class AdminLimitsOut(BaseModel):
    max_chars: int
    max_per_artifact: int
    file_max_mb: int


class ArtifactTemplatesOut(BaseModel):
    limits: AdminLimitsOut
    templates: list[TemplateOut]


class TemplateIn(BaseModel):
    name: str
    content: str


class TemplateUpdate(TemplateIn):
    # La versión que la persona abrió: si la plantilla cambió desde entonces, 409 con la versión actual.
    expected_updated_at: str | None = None


class ExtractedOut(BaseModel):
    text: str


def _artifact(session: Session, principal: Principal, artifact_id: str) -> Artifact:
    artifact = session.get(Artifact, artifact_id)
    if artifact is None or not artifact_in_scope(session, principal, artifact):
        raise HTTPException(status_code=404, detail="Artefacto no encontrado.")
    return artifact


def _template(session: Session, artifact: Artifact, template_id: str) -> ResponseTemplate:
    template = session.get(ResponseTemplate, template_id)
    if template is None or template.scope != "artifact" or template.artifact_id != artifact.id:
        raise HTTPException(status_code=404, detail="Plantilla no encontrada.")
    return template


@router.get("/artifacts/{artifact_id}/templates", response_model=ArtifactTemplatesOut)
def list_artifact_templates(
    artifact_id: str, principal: Principal = Depends(require_admin), session: Session = Depends(get_session)
) -> ArtifactTemplatesOut:
    artifact = _artifact(session, principal, artifact_id)
    of_artifact, _ = service.visible_templates(session, artifact, None)
    return ArtifactTemplatesOut(
        limits=AdminLimitsOut(
            max_chars=settings.template_max_chars,
            max_per_artifact=settings.template_max_per_artifact,
            file_max_mb=settings.template_file_max_mb,
        ),
        templates=[template_out(t) for t in of_artifact],
    )


@router.post("/artifacts/{artifact_id}/templates", response_model=TemplateOut, status_code=201)
def create_artifact_template(
    artifact_id: str,
    payload: TemplateIn,
    principal: Principal = Depends(require_admin),
    session: Session = Depends(get_session),
) -> TemplateOut:
    artifact = _artifact(session, principal, artifact_id)
    name, name_key, content = service.prepare(payload.name, payload.content)
    owner_key = service.artifact_owner_key(artifact.id)
    service.ensure_unique(session, owner_key, name_key, DUPLICATE)
    service.ensure_room(
        service.count_for_artifact(session, artifact.id),
        settings.template_max_per_artifact,
        f"El artefacto llegó al máximo de {settings.template_max_per_artifact} plantillas.",
    )
    template = ResponseTemplate(
        id=str(uuid.uuid4()), scope="artifact", owner_key=owner_key, artifact_id=artifact.id, user_id=None,
        name=name, name_key=name_key, content=content, created_by=principal.label,
    )
    session.add(template)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=409, detail=DUPLICATE) from None
    session.refresh(template)
    audit.log_write(principal, "template.create", artifact.id, f"{artifact.name}: {template.name}")
    return template_out(template)


@router.put("/artifacts/{artifact_id}/templates/{template_id}", response_model=TemplateOut)
def update_artifact_template(
    artifact_id: str,
    template_id: str,
    payload: TemplateUpdate,
    principal: Principal = Depends(require_admin),
    session: Session = Depends(get_session),
):
    artifact = _artifact(session, principal, artifact_id)
    template = _template(session, artifact, template_id)
    conflict = service.changed_since(template, payload.expected_updated_at)
    if conflict is not None:
        return conflict
    name, name_key, content = service.prepare(payload.name, payload.content)
    service.ensure_unique(session, template.owner_key, name_key, DUPLICATE, exclude_id=template.id)
    template.name, template.name_key, template.content = name, name_key, content
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status_code=409, detail=DUPLICATE) from None
    session.refresh(template)
    audit.log_write(principal, "template.update", artifact.id, f"{artifact.name}: {template.name}")
    return template_out(template)


@router.delete("/artifacts/{artifact_id}/templates/{template_id}", status_code=204)
def delete_artifact_template(
    artifact_id: str,
    template_id: str,
    principal: Principal = Depends(require_admin),
    session: Session = Depends(get_session),
) -> Response:
    artifact = _artifact(session, principal, artifact_id)
    template = _template(session, artifact, template_id)
    name = template.name
    session.delete(template)
    session.commit()
    audit.log_write(principal, "template.delete", artifact.id, f"{artifact.name}: {name}")
    return Response(status_code=204)


@router.post("/artifacts/{artifact_id}/templates/extract", response_model=ExtractedOut)
def extract_artifact_template(
    artifact_id: str,
    file: UploadFile,
    principal: Principal = Depends(require_admin),
    session: Session = Depends(get_session),
) -> ExtractedOut:
    """El texto de un `.docx` o `.txt` para revisarlo antes de guardarlo; no guarda nada."""
    _artifact(session, principal, artifact_id)
    return ExtractedOut(
        text=service.extract_text(file, settings.template_max_chars, settings.template_file_max_mb)
    )
