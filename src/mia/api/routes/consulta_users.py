"""Administración de los usuarios de la Consulta (feature 015): GET, POST y PATCH /consulta-users y
POST /consulta-users/{id}/reset-password, que usa el módulo "Usuarios de la Consulta" del panel.

Mismo alcance que el resto del panel: el alcance global gestiona a todos y una cuenta de programa solo a los usuarios de sus
programas. La contraseña se muestra una sola vez (al crear o restablecer) y nunca se devuelve de nuevo. La administración
solo ve la cantidad de conversaciones y la fecha de la última actividad, jamás su texto.
Contrato en specs/015-historial-chats/contracts/usuarios-admin-api.md."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from mia.access import audit
from mia.access.guards import ensure_global, ensure_unit
from mia.access.scope import Principal, unit_in_scope
from mia.api.security import require_admin
from mia.chat import passwords, sessions
from mia.chat.throttle import login_throttle
from mia.storage.db import get_session
from mia.storage.models import ConsultaUser, Conversation, Unit

router = APIRouter(tags=["consulta-users"])


class UnitRef(BaseModel):
    id: str
    name: str


class ConsultaUserOut(BaseModel):
    id: str
    username: str
    unit: UnitRef | None
    active: bool
    created_at: str
    last_login_at: str | None
    # Lo único que la administración ve de las conversaciones (nunca su texto).
    conversation_count: int
    last_activity_at: str | None


class ConsultaUserCreated(ConsultaUserOut):
    # La contraseña (la dada o la generada): la única vez que sale.
    password: str


class ConsultaUserCreate(BaseModel):
    username: str
    unit_id: str | None = None
    password: str | None = None


class ConsultaUserUpdate(BaseModel):
    active: bool | None = None


class PasswordReset(BaseModel):
    password: str | None = None


class PasswordRevealed(BaseModel):
    password: str


class ConsultaUsersOut(BaseModel):
    users: list[ConsultaUserOut]


def _iso(value) -> str | None:
    return value.isoformat() + "Z" if value is not None else None


def _activity(session: Session, user_ids: list[str]) -> dict[str, tuple[int, object]]:
    """Cantidad de conversaciones y fecha de la última actividad por usuario, en una sola consulta agregada."""
    if not user_ids:
        return {}
    rows = session.execute(
        select(Conversation.user_id, func.count(Conversation.id), func.max(Conversation.updated_at))
        .where(Conversation.user_id.in_(user_ids))
        .group_by(Conversation.user_id)
    ).all()
    return {user_id: (count, last) for user_id, count, last in rows}


def _to_out(user: ConsultaUser, units: dict[str, Unit], activity: dict) -> ConsultaUserOut:
    unit = units.get(user.unit_id) if user.unit_id else None
    count, last = activity.get(user.id, (0, None))
    return ConsultaUserOut(
        id=user.id,
        username=user.username,
        unit=UnitRef(id=unit.id, name=unit.name) if unit else None,
        active=user.active,
        created_at=_iso(user.created_at),
        last_login_at=_iso(user.last_login_at),
        conversation_count=count,
        last_activity_at=_iso(last),
    )


def _units_of(session: Session, users: list[ConsultaUser]) -> dict[str, Unit]:
    ids = {u.unit_id for u in users if u.unit_id}
    if not ids:
        return {}
    return {u.id: u for u in session.scalars(select(Unit).where(Unit.id.in_(ids)))}


def _render(session: Session, users: list[ConsultaUser]) -> list[ConsultaUserOut]:
    units = _units_of(session, users)
    activity = _activity(session, [u.id for u in users])
    return [_to_out(user, units, activity) for user in users]


def _user_in_scope(session: Session, principal: Principal, user_id: str) -> ConsultaUser:
    """El usuario si existe y cae en el alcance; si no, 404 (no se distingue un ajeno de uno inexistente)."""
    user = session.get(ConsultaUser, user_id)
    if user is None or not unit_in_scope(principal, user.unit_id):
        raise HTTPException(status_code=404, detail="Usuario no encontrado.")
    return user


def _chosen_password(given: str | None) -> str:
    """La contraseña dada (validada) o una generada."""
    if given is None or given == "":
        return passwords.generate_password()
    problem = passwords.validate_password(given)
    if problem is not None:
        raise HTTPException(status_code=422, detail=problem)
    return given


@router.get("/consulta-users", response_model=ConsultaUsersOut)
def list_users(
    principal: Principal = Depends(require_admin), session: Session = Depends(get_session)
) -> ConsultaUsersOut:
    users = sorted(session.scalars(select(ConsultaUser)), key=lambda u: u.username)
    users = [u for u in users if unit_in_scope(principal, u.unit_id)]
    return ConsultaUsersOut(users=_render(session, users))


@router.post("/consulta-users", response_model=ConsultaUserCreated, status_code=201)
def create_user(
    payload: ConsultaUserCreate,
    principal: Principal = Depends(require_admin),
    session: Session = Depends(get_session),
) -> ConsultaUserCreated:
    username = passwords.normalize_username(payload.username)
    problem = passwords.validate_username(username)
    if problem is not None:
        raise HTTPException(status_code=422, detail=problem)
    unit = None
    if payload.unit_id is None:
        ensure_global(principal, "consulta_user.create", username)
    else:
        unit = session.get(Unit, payload.unit_id)
        if unit is None:
            raise HTTPException(status_code=404, detail="Programa no encontrado.")
        ensure_unit(principal, unit.id, "consulta_user.create", username)
    password = _chosen_password(payload.password)
    if session.scalar(select(ConsultaUser).where(ConsultaUser.username == username)) is not None:
        raise HTTPException(status_code=409, detail=f"Ya existe un usuario llamado '{username}'.")
    user = ConsultaUser(
        id=str(uuid.uuid4()),
        username=username,
        password_hash=passwords.hash_password(password),
        unit_id=unit.id if unit else None,
        active=True,
        created_by=principal.label,
    )
    session.add(user)
    try:
        session.commit()
    except IntegrityError as exc:
        # Otro alta igual llegó entre la comprobación y el guardado.
        session.rollback()
        raise HTTPException(
            status_code=409, detail=f"Ya existe un usuario llamado '{username}'."
        ) from exc
    session.refresh(user)
    audit.log_write(
        principal,
        "consulta_user.create",
        user.id,
        f"{username} -> {unit.name if unit else '(global)'}",
    )
    [out] = _render(session, [user])
    return ConsultaUserCreated(**out.model_dump(), password=password)


@router.patch("/consulta-users/{user_id}", response_model=ConsultaUserOut)
def update_user(
    user_id: str,
    payload: ConsultaUserUpdate,
    principal: Principal = Depends(require_admin),
    session: Session = Depends(get_session),
) -> ConsultaUserOut:
    user = _user_in_scope(session, principal, user_id)
    if payload.active is not None and payload.active != user.active:
        user.active = payload.active
        session.commit()
        if not user.active:
            sessions.close_user_sessions(session, user.id)
        else:
            login_throttle.clear_user(user.username)
        audit.log_write(
            principal,
            "consulta_user.update",
            user.id,
            f"{user.username}: activo {str(user.active).lower()}",
        )
    session.refresh(user)
    [out] = _render(session, [user])
    return out


@router.post("/consulta-users/{user_id}/reset-password", response_model=PasswordRevealed)
def reset_password(
    user_id: str,
    payload: PasswordReset | None = None,
    principal: Principal = Depends(require_admin),
    session: Session = Depends(get_session),
) -> PasswordRevealed:
    user = _user_in_scope(session, principal, user_id)
    password = _chosen_password(payload.password if payload else None)
    user.password_hash = passwords.hash_password(password)
    session.commit()
    sessions.close_user_sessions(session, user.id)
    # Quien pidió el restablecimiento suele estar bloqueado por intentos fallidos: con la contraseña nueva se le libera
    # (el bloqueo vive en la memoria de la API y se aplica antes de verificar la contraseña, aunque sea correcta).
    login_throttle.clear_user(user.username)
    audit.log_write(principal, "consulta_user.reset_password", user.id, user.username)
    return PasswordRevealed(password=password)
