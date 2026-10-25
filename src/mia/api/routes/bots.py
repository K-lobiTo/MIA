"""Administración de bots de WhatsApp (feature 011): GET, POST y PATCH /bots, que usa el módulo Bots del panel.

Todo con alcance global (el número de WhatsApp y la cuota de mensajes son de toda la institución, no de un programa).
Un bot no se borra: se desactiva. Contrato en specs/011-bot-whatsapp-kapso/contracts/bots-api.md.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, StringConstraints
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from mia.access import audit
from mia.access.errors import global_only
from mia.access.guards import ensure_global
from mia.access.scope import Principal
from mia.api.routes.inventory import Name
from mia.api.security import require_admin
from mia.bots.status import bot_state, domain_labels
from mia.bots.usage import current_month
from mia.config import settings
from mia.storage.db import get_session
from mia.storage.models import Artifact, Bot

router = APIRouter(tags=["bots"])

# El `phone_number_id` de Kapso: de 1 a 64 caracteres, sin espacios.
NumberId = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64, pattern=r"^\S+$")]


class BotCreate(BaseModel):
    name: Name
    kapso_number_id: NumberId
    artifact_id: str


class BotUpdate(BaseModel):
    name: Name | None = None
    kapso_number_id: NumberId | None = None
    artifact_id: str | None = None
    active: bool | None = None


class ArtifactRef(BaseModel):
    id: str
    name: str
    active: bool


class UsageOut(BaseModel):
    received: int
    sent: int
    total: int
    cap_reached: bool


class BotOut(BaseModel):
    id: str
    name: str
    kapso_number_id: str
    active: bool
    artifact: ArtifactRef | None
    domains: list[str]
    available: bool
    unavailable_reason: str | None
    usage: UsageOut
    created_at: str


class BotsOut(BaseModel):
    monthly_cap: int
    service_configured: bool
    month: str
    bots: list[BotOut]


def _to_out(session: Session, bot: Bot, month: str) -> BotOut:
    state = bot_state(session, bot, month)
    artifact = state.artifact
    return BotOut(
        id=bot.id,
        name=bot.name,
        kapso_number_id=bot.kapso_number_id,
        active=bot.active,
        artifact=ArtifactRef(id=artifact.id, name=artifact.name, active=artifact.active) if artifact else None,
        domains=domain_labels(session, artifact),
        available=state.available,
        unavailable_reason=state.reason,
        usage=UsageOut(
            received=state.usage.received,
            sent=state.usage.sent,
            total=state.usage.total,
            cap_reached=state.status == "cap_reached",
        ),
        created_at=bot.created_at.isoformat() + "Z",
    )


def _conflict_name(name: str) -> HTTPException:
    return HTTPException(status_code=409, detail=f"Ya existe un bot llamado '{name}'.")


def _conflict_number() -> HTTPException:
    return HTTPException(status_code=409, detail="Ya hay un bot registrado para ese número de Kapso.")


def _check_unique(session: Session, name: str | None, number: str | None, ignore_id: str | None = None) -> None:
    if name is not None:
        other = session.scalar(select(Bot).where(Bot.name == name))
        if other is not None and other.id != ignore_id:
            raise _conflict_name(name)
    if number is not None:
        other = session.scalar(select(Bot).where(Bot.kapso_number_id == number))
        if other is not None and other.id != ignore_id:
            raise _conflict_number()


def _artifact_or_404(session: Session, artifact_id: str) -> Artifact:
    artifact = session.get(Artifact, artifact_id)
    if artifact is None:
        raise HTTPException(status_code=404, detail="Artefacto no encontrado.")
    return artifact


@router.get("/bots", response_model=BotsOut)
def list_bots(principal: Principal = Depends(require_admin), session: Session = Depends(get_session)) -> BotsOut:
    if not principal.is_global:
        raise global_only()
    month = current_month()
    bots = sorted(session.scalars(select(Bot)), key=lambda b: b.name.lower())
    return BotsOut(
        monthly_cap=settings.bot_monthly_message_cap,
        service_configured=bool(settings.bot_service_key),
        month=month,
        bots=[_to_out(session, bot, month) for bot in bots],
    )


@router.post("/bots", response_model=BotOut, status_code=201)
def create_bot(
    payload: BotCreate, principal: Principal = Depends(require_admin), session: Session = Depends(get_session)
) -> BotOut:
    ensure_global(principal, "bot.create", payload.name)
    artifact = _artifact_or_404(session, payload.artifact_id)
    _check_unique(session, payload.name, payload.kapso_number_id)
    bot = Bot(
        id=str(uuid.uuid4()),
        name=payload.name,
        kapso_number_id=payload.kapso_number_id,
        artifact_id=artifact.id,
        active=True,
    )
    session.add(bot)
    try:
        session.commit()
    except IntegrityError as exc:
        # Otro registro igual llegó entre la comprobación y el guardado.
        session.rollback()
        _check_unique(session, payload.name, payload.kapso_number_id)
        raise HTTPException(status_code=409, detail="El bot ya existe.") from exc
    session.refresh(bot)
    audit.log_write(principal, "bot.create", bot.id, f"{bot.name} -> {artifact.name}")
    return _to_out(session, bot, current_month())


@router.patch("/bots/{bot_id}", response_model=BotOut)
def update_bot(
    bot_id: str,
    payload: BotUpdate,
    principal: Principal = Depends(require_admin),
    session: Session = Depends(get_session),
) -> BotOut:
    ensure_global(principal, "bot.update", bot_id)
    bot = session.get(Bot, bot_id)
    if bot is None:
        raise HTTPException(status_code=404, detail="Bot no encontrado.")
    changes = payload.model_fields_set
    if "artifact_id" in changes and payload.artifact_id is None:
        raise HTTPException(status_code=422, detail="El bot debe tener un artefacto asignado.")
    new_artifact = _artifact_or_404(session, payload.artifact_id) if "artifact_id" in changes else None
    _check_unique(
        session,
        payload.name if "name" in changes else None,
        payload.kapso_number_id if "kapso_number_id" in changes else None,
        ignore_id=bot.id,
    )

    detail: list[str] = []
    if "name" in changes and payload.name is not None and payload.name != bot.name:
        detail.append(f"nombre: {bot.name} -> {payload.name}")
        bot.name = payload.name
    if "kapso_number_id" in changes and payload.kapso_number_id is not None and payload.kapso_number_id != bot.kapso_number_id:
        detail.append(f"numero: {bot.kapso_number_id} -> {payload.kapso_number_id}")
        bot.kapso_number_id = payload.kapso_number_id
    if new_artifact is not None and new_artifact.id != bot.artifact_id:
        previous = session.get(Artifact, bot.artifact_id) if bot.artifact_id else None
        detail.append(f"artefacto: {previous.name if previous else '(ninguno)'} -> {new_artifact.name}")
        bot.artifact_id = new_artifact.id
    if "active" in changes and payload.active is not None and payload.active != bot.active:
        detail.append(f"activo: {str(payload.active).lower()}")
        bot.active = payload.active
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail="Ya existe otro bot con ese nombre o número.") from exc
    session.refresh(bot)
    for line in detail:
        audit.log_write(principal, "bot.update", bot.id, line)
    return _to_out(session, bot, current_month())
