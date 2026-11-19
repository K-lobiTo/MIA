"""Plantillas de respuesta en la Consulta (feature 020): GET /templates para listar las visibles y, con sesión, crear, editar,
eliminar plantillas personales y leer un archivo. Usan la clave del artefacto (`X-Artifact-Key`) y, donde se indica, la sesión
de la persona (`X-Session-Token`). El contenido de una plantilla nunca se escribe en los registros del servidor.
Contrato en specs/020-modo-plantilla/contracts/plantillas-api.md."""

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from mia.access.errors import AuthError
from mia.access.permissions import allowed_modes
from mia.api.security import optional_user, require_artifact
from mia.config import settings
from mia.rag.mode_ids import PLANTILLA
from mia.rag.modes import mode_available
from mia.storage.db import get_session
from mia.storage.models import Artifact, ConsultaUser, ResponseTemplate
from mia.templates import service

router = APIRouter(tags=["templates"])

DUPLICATE = "Ya tienes una plantilla con ese nombre."
NO_MODE = "Este artefacto no tiene el modo plantilla."


class TemplateOut(BaseModel):
    id: str
    name: str
    content: str
    updated_at: str


class PersonalTemplateOut(TemplateOut):
    # `all`: para todos los artefactos; `artifact`: solo para el artefacto de la clave.
    scope: Literal["all", "artifact"]


class LimitsOut(BaseModel):
    max_chars: int
    max_per_user: int
    file_max_mb: int


class TemplatesOut(BaseModel):
    enabled: bool
    limits: LimitsOut
    can_create: bool
    artifact: list[TemplateOut]
    mine: list[PersonalTemplateOut]


def iso(value) -> str:
    return value.isoformat() + "Z"


def template_out(template: ResponseTemplate) -> TemplateOut:
    return TemplateOut(id=template.id, name=template.name, content=template.content, updated_at=iso(template.updated_at))


def personal_out(template: ResponseTemplate) -> PersonalTemplateOut:
    return PersonalTemplateOut(
        id=template.id,
        name=template.name,
        content=template.content,
        updated_at=iso(template.updated_at),
        scope="all" if template.artifact_id is None else "artifact",
    )


def limits_out() -> LimitsOut:
    return LimitsOut(
        max_chars=settings.template_max_chars,
        max_per_user=settings.template_max_per_user,
        file_max_mb=settings.template_file_max_mb,
    )


def mode_enabled(artifact: Artifact) -> bool:
    """El artefacto permite el modo plantilla y la instancia lo tiene disponible (depende del razonamiento)."""
    return PLANTILLA in allowed_modes(artifact) and mode_available(PLANTILLA)[0]


@router.get("/templates", response_model=TemplatesOut)
def list_templates(
    artifact: Artifact = Depends(require_artifact),
    user: ConsultaUser | None = Depends(optional_user),
    session: Session = Depends(get_session),
) -> TemplatesOut:
    """Las plantillas visibles para el artefacto de la clave y, con sesión, para la persona. No exige el modo habilitado: sin
    él devuelve listas vacías (no ofrece nada)."""
    enabled = mode_enabled(artifact)
    of_artifact, mine = service.visible_templates(session, artifact, user) if enabled else ([], [])
    return TemplatesOut(
        enabled=enabled,
        limits=limits_out(),
        can_create=user is not None,
        artifact=[template_out(t) for t in of_artifact],
        mine=[personal_out(t) for t in mine],
    )


class PersonalIn(BaseModel):
    name: str
    content: str
    # `artifact`: solo para el artefacto de la clave; `all`: para todos los artefactos donde inicie sesión.
    scope: Literal["artifact", "all"]


class PersonalUpdate(PersonalIn):
    # La versión que la persona abrió: si cambió desde entonces (otra pestaña), 409 con la versión actual.
    expected_updated_at: str | None = None


class ExtractedOut(BaseModel):
    text: str


def session_user(user: ConsultaUser | None = Depends(optional_user)) -> ConsultaUser:
    """Las plantillas personales exigen la sesión de la persona; sin ella, el mismo código que usa la Consulta para pedirla."""
    if user is None:
        raise AuthError(401, "login_required", "Inicia sesión para guardar tus propias plantillas.")
    return user


def _own(session: Session, user: ConsultaUser, template_id: str) -> ResponseTemplate:
    """Una plantilla personal de la persona; una ajena, del artefacto o inexistente responde lo mismo (404)."""
    template = session.get(ResponseTemplate, template_id)
    if template is None or template.scope != "personal" or template.user_id != user.id:
        raise HTTPException(status_code=404, detail=service.NOT_AVAILABLE)
    return template


def _commit(session: Session) -> None:
    try:
        session.commit()
    except IntegrityError:
        # Dos pestañas guardaron el mismo nombre a la vez: la restricción de la base lo impide.
        session.rollback()
        raise HTTPException(status_code=409, detail=DUPLICATE) from None


@router.post("/templates", response_model=PersonalTemplateOut, status_code=201)
def create_template(
    payload: PersonalIn,
    artifact: Artifact = Depends(require_artifact),
    user: ConsultaUser = Depends(session_user),
    session: Session = Depends(get_session),
) -> PersonalTemplateOut:
    if not mode_enabled(artifact):
        raise HTTPException(status_code=403, detail=NO_MODE)
    name, name_key, content = service.prepare(payload.name, payload.content)
    owner_key = service.user_owner_key(user.id)
    service.ensure_unique(session, owner_key, name_key, DUPLICATE)
    service.ensure_room(
        service.count_for_user(session, user.id),
        settings.template_max_per_user,
        f"Llegaste al máximo de {settings.template_max_per_user} plantillas personales.",
    )
    template = ResponseTemplate(
        id=str(uuid.uuid4()), scope="personal", owner_key=owner_key,
        artifact_id=artifact.id if payload.scope == "artifact" else None, user_id=user.id,
        name=name, name_key=name_key, content=content, created_by=user.id,
    )
    session.add(template)
    _commit(session)
    session.refresh(template)
    return personal_out(template)


@router.put("/templates/{template_id}", response_model=PersonalTemplateOut)
def update_template(
    template_id: str,
    payload: PersonalUpdate,
    artifact: Artifact = Depends(require_artifact),
    user: ConsultaUser = Depends(session_user),
    session: Session = Depends(get_session),
):
    template = _own(session, user, template_id)
    conflict = service.changed_since(template, payload.expected_updated_at)
    if conflict is not None:
        return conflict
    name, name_key, content = service.prepare(payload.name, payload.content)
    service.ensure_unique(session, template.owner_key, name_key, DUPLICATE, exclude_id=template.id)
    template.name, template.name_key, template.content = name, name_key, content
    template.artifact_id = artifact.id if payload.scope == "artifact" else None
    _commit(session)
    session.refresh(template)
    return personal_out(template)


@router.delete("/templates/{template_id}", status_code=204)
def delete_template(
    template_id: str,
    artifact: Artifact = Depends(require_artifact),
    user: ConsultaUser = Depends(session_user),
    session: Session = Depends(get_session),
) -> Response:
    session.delete(_own(session, user, template_id))
    session.commit()
    return Response(status_code=204)


@router.post("/templates/extract", response_model=ExtractedOut)
def extract_template(
    file: UploadFile,
    artifact: Artifact = Depends(require_artifact),
    user: ConsultaUser = Depends(session_user),
) -> ExtractedOut:
    """El texto de un `.docx` o `.txt` para revisarlo antes de guardarlo como plantilla; no guarda nada."""
    return ExtractedOut(text=service.extract_text(file, settings.template_max_chars, settings.template_file_max_mb))
