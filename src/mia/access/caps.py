"""Topes diarios de gasto, en USD. El día se corta a medianoche de la zona de CAP_TIMEZONE (Costa Rica),
sin depender de la zona horaria del servidor. El gasto se suma sobre el registro de consultas: es la
misma fuente que usa el módulo Uso, así el panel y el control nunca discrepan."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Literal
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from mia.config import settings
from mia.rag.modes import RAZONAMIENTO
from mia.storage.models import Artifact, QueryLog

Scope = Literal["api", "artifact", "reasoning"]


def _aware_utc(now: datetime | None) -> datetime:
    if now is None:
        return datetime.now(UTC)
    return now.replace(tzinfo=UTC) if now.tzinfo is None else now.astimezone(UTC)


def _local_midnight(now: datetime | None, days_ahead: int = 0) -> datetime:
    zone = ZoneInfo(settings.cap_timezone)
    local = _aware_utc(now).astimezone(zone)
    # Se arma con la fecha local (no sumando 24 horas) para no equivocarse en un cambio de horario.
    day = local.date() + timedelta(days=days_ahead)
    return datetime(day.year, day.month, day.day, tzinfo=zone)


def day_start_utc(now: datetime | None = None) -> datetime:
    """Inicio del día de los topes, como UTC sin zona (así se guardan las fechas)."""
    return _local_midnight(now).astimezone(UTC).replace(tzinfo=None)


def next_reset_utc(now: datetime | None = None) -> datetime:
    """Cuándo se reinician los topes: la próxima medianoche local, como UTC sin zona."""
    return _local_midnight(now, days_ahead=1).astimezone(UTC).replace(tzinfo=None)


def seconds_until(moment: datetime, now: datetime | None = None) -> int:
    """Segundos hasta `moment` (UTC sin zona), nunca negativos; para el encabezado Retry-After."""
    return max(0, int((moment - _aware_utc(now).replace(tzinfo=None)).total_seconds()))


def spent_today(
    session: Session,
    artifact_id: str | None = None,
    mode: str | None = None,
    now: datetime | None = None,
) -> Decimal:
    """Gasto de hoy en USD, de toda la API o filtrado por artefacto y por modo."""
    query = select(func.coalesce(func.sum(QueryLog.cost_usd), 0)).where(QueryLog.created_at >= day_start_utc(now))
    if artifact_id is not None:
        query = query.where(QueryLog.artifact_id == artifact_id)
    if mode is not None:
        query = query.where(QueryLog.mode == mode)
    return Decimal(str(session.scalar(query)))


@dataclass
class CapStatus:
    """Un tope alcanzado: cuál es, cuánto vale, cuánto se gastó y cuándo se reinicia."""

    scope: Scope
    cap: Decimal
    spent: Decimal
    resets_at: datetime


def check_caps(session: Session, artifact: Artifact, mode: str, now: datetime | None = None) -> CapStatus | None:
    """El primer tope alcanzado que impide consultar en ese modo, o None si puede consultar.
    Orden: toda la API, total del artefacto, y el del modo con razonamiento si aplica."""
    resets_at = next_reset_utc(now)

    api_cap = Decimal(str(settings.daily_cap_usd))
    api_spent = spent_today(session, now=now)
    if api_spent >= api_cap:
        return CapStatus("api", api_cap, api_spent, resets_at)

    cap = Decimal(artifact.daily_cap_usd)
    spent = spent_today(session, artifact_id=artifact.id, now=now)
    if spent >= cap:
        return CapStatus("artifact", cap, spent, resets_at)

    if mode == RAZONAMIENTO and artifact.reasoning_daily_cap_usd is not None:
        reasoning_cap = Decimal(artifact.reasoning_daily_cap_usd)
        reasoning_spent = spent_today(session, artifact_id=artifact.id, mode=RAZONAMIENTO, now=now)
        if reasoning_spent >= reasoning_cap:
            return CapStatus("reasoning", reasoning_cap, reasoning_spent, resets_at)
    return None


@dataclass
class ArtifactCapState:
    """Gasto de hoy de un artefacto frente a sus topes, para /config y para el listado del panel."""

    spent: Decimal
    reasoning_spent: Decimal
    cap_reached: bool
    reasoning_cap_reached: bool
    global_cap_reached: bool
    resets_at: datetime


def artifact_status(session: Session, artifact: Artifact, now: datetime | None = None) -> ArtifactCapState:
    spent = spent_today(session, artifact_id=artifact.id, now=now)
    reasoning_spent = spent_today(session, artifact_id=artifact.id, mode=RAZONAMIENTO, now=now)
    reasoning_cap = artifact.reasoning_daily_cap_usd
    return ArtifactCapState(
        spent=spent,
        reasoning_spent=reasoning_spent,
        cap_reached=spent >= Decimal(artifact.daily_cap_usd),
        reasoning_cap_reached=reasoning_cap is not None and reasoning_spent >= Decimal(reasoning_cap),
        global_cap_reached=spent_today(session, now=now) >= Decimal(str(settings.daily_cap_usd)),
        resets_at=next_reset_utc(now),
    )
