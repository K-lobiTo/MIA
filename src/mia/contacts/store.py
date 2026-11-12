"""Almacén de contactos de WhatsApp (feature 017): crear o leer, aplicar eventos, listar con filtros y borrar.

Reglas (specs/017-datos-contacto-whatsapp/data-model.md y contracts/bot-contactos-api.md):
- Un contacto por `(bot_id, phone)`; la creación es segura ante carreras (la unicidad la garantiza la base).
- La invitación se reclama de forma atómica (`UPDATE ... WHERE status = 'pendiente'`), así dos mensajes simultáneos de una
  persona nueva producen una sola invitación.
- Los errores NUNCA repiten el teléfono, el nombre ni el correo recibidos.
"""

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from mia.storage.models import WhatsAppContact, _now

STATUSES = ("pendiente", "invitada", "entrego", "declino")
EVENTS = ("claim_invite", "release_invite", "provided", "email_retry", "declined", "erase", "reopen")

NAME_MAX = 80
EMAIL_MAX = 254
# Con una escritura de `last_seen_at` por hora y por contacto basta para saber cuándo escribió por última vez.
TOUCH_EVERY = timedelta(hours=1)

_EMAIL = re.compile(r"[^\s@]+@[^\s@.]+(?:\.[^\s@.]+)+")


class InvalidData(ValueError):
    """Dato inválido (evento, nombre o correo). El mensaje nunca repite el valor recibido."""


class ContactNotFound(LookupError):
    """El evento exige un contacto que no existe."""


class InvalidTransition(Exception):
    """El evento no aplica al estado actual del contacto; `status` es ese estado."""

    def __init__(self, status: str):
        super().__init__("El evento no aplica al estado actual del contacto.")
        self.status = status


@dataclass
class EventResult:
    contact: WhatsAppContact
    claimed: bool = False
    had_data: bool = False


@dataclass
class ContactFilters:
    bot_id: str | None = None
    statuses: list[str] = field(default_factory=list)
    has_email: bool | None = None


def clean_name(value: str | None) -> str:
    name = (value or "").strip()
    if not 1 <= len(name) <= NAME_MAX or "\n" in name or "\r" in name:
        raise InvalidData("Nombre inválido.")
    return name


def clean_email(value: str | None) -> str:
    email = (value or "").strip().lower()
    if len(email) > EMAIL_MAX or not _EMAIL.fullmatch(email):
        raise InvalidData("Correo inválido.")
    return email


def _find(session: Session, bot_id: str, phone: str) -> WhatsAppContact | None:
    return session.scalar(
        select(WhatsAppContact).where(WhatsAppContact.bot_id == bot_id, WhatsAppContact.phone == phone)
    )


def get_or_create(session: Session, bot_id: str, phone: str) -> WhatsAppContact:
    """El contacto de ese teléfono y bot (`pendiente` si es nuevo). Si otro mensaje lo creó en el mismo instante, lee el suyo."""
    contact = _find(session, bot_id, phone)
    if contact is not None:
        return contact
    now = _now()
    contact = WhatsAppContact(
        id=str(uuid.uuid4()), bot_id=bot_id, phone=phone, status="pendiente", email_retried=False,
        created_at=now, last_seen_at=now, updated_at=now,
    )
    session.add(contact)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        existing = _find(session, bot_id, phone)
        if existing is None:
            raise
        return existing
    return contact


def touch(session: Session, contact: WhatsAppContact, now: datetime | None = None) -> None:
    """Actualiza `last_seen_at`, como máximo una vez por hora para no cargar la base."""
    now = now or _now()
    if now - contact.last_seen_at >= TOUCH_EVERY:
        contact.last_seen_at = now
        session.commit()


def claim_invite(session: Session, contact_id: str) -> bool:
    """Reclama la invitación de forma atómica: solo gana quien encuentra el contacto `pendiente`."""
    result = session.execute(
        update(WhatsAppContact)
        .where(WhatsAppContact.id == contact_id, WhatsAppContact.status == "pendiente")
        .values(status="invitada", updated_at=_now())
    )
    session.commit()
    return result.rowcount == 1


def _has_data(contact: WhatsAppContact) -> bool:
    return bool(contact.name or contact.email)


def apply_event(
    session: Session, bot_id: str, phone: str, event: str, *, name: str | None = None, email: str | None = None
) -> EventResult:
    """Aplica un evento al contacto (tabla de contracts/bot-contactos-api.md). `phone` ya viene normalizado."""
    if event not in EVENTS:
        raise InvalidData("Evento inválido.")

    if event in ("claim_invite", "erase", "reopen"):
        contact = get_or_create(session, bot_id, phone)
    else:
        contact = _find(session, bot_id, phone)
        if contact is None:
            raise ContactNotFound("El contacto no existe.")

    if event == "claim_invite":
        claimed = claim_invite(session, contact.id)
        session.refresh(contact)
        return EventResult(contact, claimed=claimed)

    if event == "erase":
        had_data = _has_data(contact)
        contact.name = None
        contact.email = None
        contact.status = "declino"
        contact.email_retried = False
        session.commit()
        return EventResult(contact, had_data=had_data)

    if event == "reopen":
        contact.status = "invitada"
        contact.email_retried = False
        session.commit()
        return EventResult(contact, claimed=True)

    if event == "declined" and contact.status in ("declino", "entrego"):
        # Repetirlo no falla: la invitación ya estaba cerrada.
        return EventResult(contact)

    if contact.status != "invitada":
        raise InvalidTransition(contact.status)

    if event == "release_invite":
        if _has_data(contact):
            raise InvalidTransition(contact.status)
        contact.status = "pendiente"
    elif event == "provided":
        new_name = clean_name(name) if name is not None else None
        new_email = clean_email(email) if email is not None else None
        if new_name is None and new_email is None:
            raise InvalidData("Falta el nombre o el correo.")
        if new_name is not None:
            contact.name = new_name
        if new_email is not None:
            contact.email = new_email
        contact.status = "entrego"
        contact.email_retried = False
    elif event == "email_retry":
        if contact.email_retried:
            raise InvalidTransition(contact.status)
        if name is not None:
            contact.name = clean_name(name)
        contact.email_retried = True
    elif event == "declined":
        contact.status = "entrego" if _has_data(contact) else "declino"
    session.commit()
    return EventResult(contact)


def _where(filters: ContactFilters, *, with_status: bool = True) -> list:
    conditions = []
    if filters.bot_id:
        conditions.append(WhatsAppContact.bot_id == filters.bot_id)
    if with_status and filters.statuses:
        conditions.append(WhatsAppContact.status.in_(filters.statuses))
    if filters.has_email is True:
        conditions.append(WhatsAppContact.email.is_not(None))
    elif filters.has_email is False:
        conditions.append(WhatsAppContact.email.is_(None))
    return conditions


def count(session: Session, filters: ContactFilters) -> int:
    return session.scalar(select(func.count()).select_from(WhatsAppContact).where(*_where(filters))) or 0


def _ordered(filters: ContactFilters):
    return (
        select(WhatsAppContact)
        .where(*_where(filters))
        .order_by(WhatsAppContact.created_at.desc(), WhatsAppContact.id.desc())
    )


def list_contacts(
    session: Session, filters: ContactFilters, page: int, page_size: int
) -> tuple[list[WhatsAppContact], int]:
    """Una página de contactos, de la más reciente a la más antigua, y el total del filtro."""
    items = session.scalars(_ordered(filters).limit(page_size).offset((page - 1) * page_size)).all()
    return list(items), count(session, filters)


def all_contacts(session: Session, filters: ContactFilters, limit: int) -> list[WhatsAppContact]:
    """Todos los contactos del filtro (para el CSV), hasta `limit`."""
    return list(session.scalars(_ordered(filters).limit(limit)).all())


def summary(session: Session, filters: ContactFilters) -> dict[str, int]:
    """Conteo por estado SIN el filtro de estado (pero con los demás filtros)."""
    rows = session.execute(
        select(WhatsAppContact.status, func.count())
        .where(*_where(filters, with_status=False))
        .group_by(WhatsAppContact.status)
    ).all()
    totals = {status: 0 for status in STATUSES}
    totals.update({status: n for status, n in rows})
    return totals


def delete_contact(session: Session, contact_id: str) -> bool:
    result = session.execute(delete(WhatsAppContact).where(WhatsAppContact.id == contact_id))
    session.commit()
    return result.rowcount == 1


def delete_filtered(session: Session, filters: ContactFilters) -> int:
    result = session.execute(delete(WhatsAppContact).where(*_where(filters)))
    session.commit()
    return result.rowcount


def state_of(contact: WhatsAppContact) -> dict:
    """El estado que la API devuelve al servicio del bot: nunca el nombre ni el correo, solo si existen."""
    return {
        "status": contact.status,
        "email_retried": contact.email_retried,
        "has_name": bool(contact.name),
        "has_email": bool(contact.email),
    }
