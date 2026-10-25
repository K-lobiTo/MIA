"""Consumo mensual de mensajes de un bot de WhatsApp (feature 011, research R4 de specs/011-bot-whatsapp-kapso).

El plan gratuito de Kapso incluye 2.000 mensajes al mes entre recibidos y enviados, así que ese conteo (no el gasto de
modelos) es el límite real del bot. Vive en la base de la API, una fila por bot y mes: sobrevive a los reinicios del
servicio, es la cifra que muestra el panel y un mes nuevo nace en cero sin tareas de reinicio.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from mia.config import settings
from mia.storage.models import BotMessageCount, _now


@dataclass(frozen=True)
class MonthUsage:
    received: int = 0
    sent: int = 0

    @property
    def total(self) -> int:
        return self.received + self.sent


def current_month(now: datetime | None = None) -> str:
    """Mes calendario (AAAA-MM) en la zona de CAP_TIMEZONE, la misma en que se corta el día de los topes de gasto."""
    if now is None:
        moment = datetime.now(UTC)
    else:
        moment = now.replace(tzinfo=UTC) if now.tzinfo is None else now.astimezone(UTC)
    local = moment.astimezone(ZoneInfo(settings.cap_timezone))
    return f"{local.year:04d}-{local.month:02d}"


def _increment(session: Session, bot_id: str, month: str, received: int, sent: int) -> int:
    result = session.execute(
        update(BotMessageCount)
        .where(BotMessageCount.bot_id == bot_id, BotMessageCount.month == month)
        .values(
            received=BotMessageCount.received + received,
            sent=BotMessageCount.sent + sent,
            updated_at=_now(),
        )
    )
    return result.rowcount


def add_messages(session: Session, bot_id: str, month: str, received: int, sent: int) -> None:
    """Suma mensajes al mes de un bot con un incremento atómico en SQL (no lee y escribe): dos llamadas a la vez
    no pierden cuentas. Si todavía no hay fila del mes se inserta; si otro proceso la insertó a la vez (conflicto de
    clave), se repite el incremento. Hace commit."""
    if _increment(session, bot_id, month, received, sent) == 0:
        try:
            session.add(BotMessageCount(bot_id=bot_id, month=month, received=received, sent=sent))
            session.flush()
        except IntegrityError:
            session.rollback()
            _increment(session, bot_id, month, received, sent)
    session.commit()


def month_usage(session: Session, bot_id: str, month: str | None = None) -> MonthUsage:
    """Lo consumido en el mes (el actual por defecto); ceros si no hay fila. Lee las columnas directo de la base (no la
    fila ORM) para no ver un valor viejo del identity map si otro proceso sumó mientras tanto."""
    row = session.execute(
        select(BotMessageCount.received, BotMessageCount.sent).where(
            BotMessageCount.bot_id == bot_id, BotMessageCount.month == (month or current_month())
        )
    ).first()
    return MonthUsage() if row is None else MonthUsage(received=row.received, sent=row.sent)


def cap_reached(total: int, cap: int) -> bool:
    """El tope se alcanza al llegar a él: con tope 1.800, el mensaje 1.800 ya lo alcanza."""
    return total >= cap
