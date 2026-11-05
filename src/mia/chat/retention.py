"""Retención de las conversaciones guardadas (feature 015, research R8).

La actividad de una conversación es su `updated_at`. No hay un planificador: la limpieza corre al arrancar la API y, de
forma perezosa, como máximo una vez por hora por proceso cuando llega una petición de sesión o de conversaciones.
`CHAT_RETENTION_DAYS=0` apaga el guardado y la limpieza borra **todas** las conversaciones guardadas (los usuarios quedan);
ese borrado no se puede deshacer desde la aplicación. El registro escribe solo cantidades."""

import logging
import time
from collections.abc import Callable
from datetime import datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from mia.chat.sessions import purge_expired_sessions
from mia.config import settings
from mia.storage.db import SessionLocal
from mia.storage.models import Conversation, ConversationTurn, _now

logger = logging.getLogger("mia.chat")

PURGE_EVERY_SECONDS = 3600
_last_run: float | None = None


def reset_purge_clock() -> None:
    """Olvida cuándo corrió la limpieza perezosa por última vez (las pruebas y los reinicios)."""
    global _last_run
    _last_run = None


def purge_expired(session: Session, now: datetime | None = None) -> dict[str, int]:
    """Borra las conversaciones (con sus vueltas) sin actividad por más de `chat_retention_days` (todas si es 0) y las
    sesiones vencidas. Devuelve las cantidades borradas."""
    now = now or _now()
    expired = select(Conversation.id)
    if settings.chat_retention_days > 0:
        expired = expired.where(
            Conversation.updated_at < now - timedelta(days=settings.chat_retention_days)
        )
    ids = list(session.scalars(expired))
    # Primero las vueltas y luego la conversación: SQLite no hace cumplir las claves foráneas sin PRAGMA.
    for start in range(0, len(ids), 500):
        chunk = ids[start : start + 500]
        session.execute(delete(ConversationTurn).where(ConversationTurn.conversation_id.in_(chunk)))
        session.execute(delete(Conversation).where(Conversation.id.in_(chunk)))
    session.commit()
    sessions_deleted = purge_expired_sessions(session, now)
    result = {"conversations": len(ids), "sessions": sessions_deleted}
    if ids or sessions_deleted:
        logger.info(
            "Limpieza resultado=ok conversaciones=%d sesiones=%d", len(ids), sessions_deleted
        )
    return result


def maybe_purge(session: Session, clock: Callable[[], float] = time.monotonic) -> bool:
    """Corre la limpieza si pasó más de una hora desde la última de este proceso. Un fallo se registra y no rompe la petición."""
    global _last_run
    now = clock()
    if _last_run is not None and now - _last_run < PURGE_EVERY_SECONDS:
        return False
    _last_run = now
    try:
        purge_expired(session)
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        logger.warning("Falló la limpieza de conversaciones (%s)", type(exc).__name__)
    return True


def purge_on_startup() -> None:
    """La limpieza al arrancar la API: con su propia sesión y sin impedir el arranque si falla."""
    global _last_run
    try:
        with SessionLocal() as session:
            purge_expired(session)
        _last_run = time.monotonic()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Falló la limpieza de conversaciones al arrancar (%s)", type(exc).__name__)
