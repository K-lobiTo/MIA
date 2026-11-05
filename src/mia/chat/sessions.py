"""Sesiones de los usuarios de la Consulta (feature 015, research R2).

El token es aleatorio y opaco; en la base solo queda su SHA-256, así que cerrar una sesión es borrar su fila. La vigencia se
desliza con el uso (`session_hours`) sin pasar de `session_max_days` desde que se creó, y la renovación se escribe como
máximo una vez por minuto."""

import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from mia.access.keys import hash_key
from mia.config import settings
from mia.storage.models import ConsultaSession, ConsultaUser, _now

TOKEN_PREFIX = "mias_"
RENEW_EVERY = timedelta(minutes=1)


@dataclass
class SessionInfo:
    user: ConsultaUser
    session_id: str
    expires_at: datetime


def _expiry(created_at: datetime, now: datetime) -> datetime:
    """Vence `session_hours` después de `now`, y nunca después del tope absoluto de la sesión."""
    return min(
        now + timedelta(hours=settings.session_hours),
        created_at + timedelta(days=settings.session_max_days),
    )


def create_session(session: Session, user: ConsultaUser) -> tuple[str, ConsultaSession]:
    """Crea una sesión y devuelve el token en claro (única vez que existe) y su fila."""
    token = TOKEN_PREFIX + secrets.token_urlsafe(32)
    now = _now()
    row = ConsultaSession(
        id=str(uuid.uuid4()),
        user_id=user.id,
        token_hash=hash_key(token),
        created_at=now,
        last_seen_at=now,
        expires_at=_expiry(now, now),
    )
    session.add(row)
    session.commit()
    return token, row


def resolve_session(
    session: Session, token: str, now: datetime | None = None
) -> SessionInfo | None:
    """La sesión del token si vale (existe, no venció y su usuario está activo), renovándola con el uso; si no, nada."""
    if not token:
        return None
    now = now or _now()
    row = session.scalar(
        select(ConsultaSession).where(ConsultaSession.token_hash == hash_key(token))
    )
    if row is None:
        return None
    user = session.get(ConsultaUser, row.user_id)
    absolute_end = row.created_at + timedelta(days=settings.session_max_days)
    if user is None or not user.active or row.expires_at <= now or absolute_end <= now:
        return None
    if now - row.last_seen_at >= RENEW_EVERY:
        row.last_seen_at = now
        row.expires_at = _expiry(row.created_at, now)
        session.commit()
    return SessionInfo(user=user, session_id=row.id, expires_at=row.expires_at)


def close_session(session: Session, token: str) -> None:
    session.execute(delete(ConsultaSession).where(ConsultaSession.token_hash == hash_key(token)))
    session.commit()


def close_user_sessions(session: Session, user_id: str, except_id: str | None = None) -> None:
    """Cierra todas las sesiones del usuario (o todas menos una)."""
    statement = delete(ConsultaSession).where(ConsultaSession.user_id == user_id)
    if except_id is not None:
        statement = statement.where(ConsultaSession.id != except_id)
    session.execute(statement)
    session.commit()


def purge_expired_sessions(session: Session, now: datetime | None = None) -> int:
    """Borra las sesiones vencidas y devuelve cuántas."""
    result = session.execute(
        delete(ConsultaSession).where(ConsultaSession.expires_at <= (now or _now()))
    )
    session.commit()
    return result.rowcount or 0
