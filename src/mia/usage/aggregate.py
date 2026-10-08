"""Indicadores, series y tablas del módulo Uso, calculados sobre el registro de consultas.

Se agrega en Python y no en SQL: SQLite (desarrollo y pruebas) no tiene percentiles, y con el volumen
del prototipo (miles de filas por mes) es inmediato y funciona igual en SQLite y Postgres."""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from functools import lru_cache
from typing import Literal
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from mia.access.caps import spent_today
from mia.config import settings
from mia.storage.models import Artifact, QueryLog

NO_MODEL = "(sin modelo)"
NO_ARTIFACT = "(sin artefacto)"
MAX_CUSTOM_DAYS = 366
REJECTED = ("rejected_cap", "rejected_permission")


@dataclass
class Period:
    start: datetime  # UTC sin zona, incluido
    end: datetime  # UTC sin zona, excluido
    prev_start: datetime
    first_day: date  # días locales, ambos incluidos
    last_day: date
    bucket: Literal["hour", "day"]


def _zone() -> ZoneInfo:
    return ZoneInfo(settings.cap_timezone)


def _midnight_utc(day: date) -> datetime:
    return datetime(day.year, day.month, day.day, tzinfo=_zone()).astimezone(UTC).replace(tzinfo=None)


def resolve_period(
    period: str, first: str | None = None, last: str | None = None, now: datetime | None = None
) -> Period:
    """Período pedido, con el anterior de igual duración. Los días se cortan a medianoche local, como
    los topes. Lanza ValueError con un mensaje claro si el período no es válido."""
    now = now or datetime.now(UTC)
    today = (now if now.tzinfo else now.replace(tzinfo=UTC)).astimezone(_zone()).date()
    if period == "today":
        first_day = last_day = today
    elif period == "7d":
        first_day, last_day = today - timedelta(days=6), today
    elif period == "30d":
        first_day, last_day = today - timedelta(days=29), today
    elif period == "custom":
        if not first or not last:
            raise ValueError("Un período personalizado necesita las fechas 'from' y 'to'.")
        try:
            first_day, last_day = date.fromisoformat(first), date.fromisoformat(last)
        except ValueError as error:
            raise ValueError("Las fechas deben tener la forma AAAA-MM-DD.") from error
        if first_day > last_day:
            raise ValueError("La fecha inicial no puede ser posterior a la final.")
        if (last_day - first_day).days + 1 > MAX_CUSTOM_DAYS:
            raise ValueError(f"El período no puede superar {MAX_CUSTOM_DAYS} días.")
    else:
        raise ValueError("El período debe ser 'today', '7d', '30d' o 'custom'.")
    days = (last_day - first_day).days + 1
    return Period(
        start=_midnight_utc(first_day),
        end=_midnight_utc(last_day + timedelta(days=1)),
        prev_start=_midnight_utc(first_day - timedelta(days=days)),
        first_day=first_day,
        last_day=last_day,
        bucket="hour" if period == "today" else "day",
    )


def _statement(
    start: datetime,
    end: datetime,
    artifact_ids: list[str] | None,
    mode: str | None,
    outcomes: list[str] | None = None,
):
    query = select(QueryLog).where(QueryLog.created_at >= start, QueryLog.created_at < end)
    if artifact_ids:
        query = query.where(QueryLog.artifact_id.in_(artifact_ids))
    if mode:
        query = query.where(QueryLog.mode == mode)
    if outcomes:
        query = query.where(QueryLog.outcome.in_(outcomes))
    return query


# Columnas que usan los indicadores. Traer solo estas, como filas simples y no como objetos del ORM,
# es lo que hace rápido agregar decenas de miles de consultas (crear los objetos era lo más caro).
AGGREGATE_COLUMNS = (
    QueryLog.created_at,
    QueryLog.artifact_id,
    QueryLog.mode,
    QueryLog.model,
    QueryLog.prompt_tokens,
    QueryLog.completion_tokens,
    QueryLog.reasoning_tokens,
    QueryLog.cost_usd,
    QueryLog.latency_ms,
    QueryLog.outcome,
    QueryLog.rating,
)


def load_rows(
    session: Session,
    start: datetime,
    end: datetime,
    artifact_ids: list[str] | None,
    mode: str | None,
    outcomes: list[str] | None = None,
    light: bool = True,
) -> Sequence:
    """Consultas del período. Con `light` (por defecto) devuelve filas simples con solo las columnas de los
    indicadores; sin él, objetos completos (con la pregunta, las fuentes y el motivo de rechazo), para el
    CSV y el detalle."""
    query = _statement(start, end, artifact_ids, mode, outcomes)
    if light:
        return session.execute(query.with_only_columns(*AGGREGATE_COLUMNS)).all()
    return list(session.scalars(query))


def page_rows(
    session: Session,
    start: datetime,
    end: datetime,
    artifact_ids: list[str] | None,
    mode: str | None,
    outcomes: list[str] | None,
    page: int,
    page_size: int,
) -> tuple[int, list[QueryLog]]:
    """Una página del registro (la más reciente primero) paginada en SQL, y el total de filas."""
    query = _statement(start, end, artifact_ids, mode, outcomes)
    total = session.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = session.scalars(
        query.order_by(QueryLog.created_at.desc(), QueryLog.id.desc()).offset((page - 1) * page_size).limit(page_size)
    )
    return total, list(rows)


def _tokens(row) -> int:
    return (row.prompt_tokens or 0) + (row.completion_tokens or 0)


def _percentile(values: list[int], q: float) -> int | None:
    """Percentil por rango más cercano: el valor que deja a q de los datos por debajo."""
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(q * len(ordered)) - 1)]


def _pct_change(value: float, previous: float | None) -> float | None:
    if previous is None or previous == 0:
        return None
    return round((value - previous) / previous * 100, 1)


@dataclass
class Totals:
    spend: float
    queries: int
    input_tokens: int
    output_tokens: int
    reasoning_tokens: int
    model_queries: int
    p50: int | None
    p95: int | None
    no_info_pct: float | None
    error_pct: float | None
    useful_pct: float | None
    rated: int


def totals(rows: Sequence) -> Totals:
    answered = sum(1 for r in rows if r.outcome == "answered")
    no_info = sum(1 for r in rows if r.outcome == "no_info")
    errors = sum(1 for r in rows if r.outcome == "error")
    not_rejected = [r for r in rows if r.outcome not in REJECTED]
    latencies = [r.latency_ms for r in not_rejected if r.latency_ms is not None]
    rated = [r for r in rows if r.rating]
    return Totals(
        spend=float(sum(r.cost_usd or 0 for r in rows)),
        queries=len(rows),
        input_tokens=sum(r.prompt_tokens or 0 for r in rows),
        output_tokens=sum(r.completion_tokens or 0 for r in rows),
        reasoning_tokens=sum(r.reasoning_tokens or 0 for r in rows),
        # Costo medio: solo las consultas que llegaron al modelo, no las rechazadas ni las sin resultados.
        model_queries=sum(1 for r in rows if r.outcome in ("answered", "no_info") and r.model),
        p50=_percentile(latencies, 0.50),
        p95=_percentile(latencies, 0.95),
        no_info_pct=(no_info / (answered + no_info) * 100) if answered + no_info else None,
        error_pct=(errors / len(not_rejected) * 100) if not_rejected else None,
        useful_pct=(sum(1 for r in rated if r.rating == "util") / len(rated) * 100) if rated else None,
        rated=len(rated),
    )


def _avg_cost(rows: Sequence, t: Totals) -> float:
    model_rows = [r for r in rows if r.outcome in ("answered", "no_info") and r.model]
    return float(sum(r.cost_usd or 0 for r in model_rows)) / t.model_queries if t.model_queries else 0.0


def _points(value: float | None, previous: float | None) -> float | None:
    """Variación en puntos porcentuales; nula si falta alguno de los dos períodos."""
    if value is None or previous is None:
        return None
    return round(value - previous, 1)


def build_kpis(rows: Sequence, previous_rows: Sequence) -> dict:
    now_t, prev_t = totals(rows), totals(previous_rows)
    now_total = now_t.input_tokens + now_t.output_tokens
    prev_total = prev_t.input_tokens + prev_t.output_tokens
    avg, prev_avg = _avg_cost(rows, now_t), _avg_cost(previous_rows, prev_t)
    # Con 0 consultas anteriores no hay con qué comparar: `previous` queda en 0 y la variación nula.
    return {
        "spend_usd": {"value": now_t.spend, "previous": prev_t.spend, "change_pct": _pct_change(now_t.spend, prev_t.spend)},
        "queries": {"value": now_t.queries, "previous": prev_t.queries, "change_pct": _pct_change(now_t.queries, prev_t.queries)},
        "tokens": {
            "value": now_total,
            "input": now_t.input_tokens,
            "output": now_t.output_tokens,
            # Los tokens de razonamiento son parte de los de salida: se muestran aparte, no se suman de nuevo.
            "reasoning": now_t.reasoning_tokens,
            "previous": prev_total,
            "change_pct": _pct_change(now_total, prev_total),
        },
        "avg_cost_usd": {"value": avg, "previous": prev_avg, "change_pct": _pct_change(avg, prev_avg)},
        "latency_ms": {
            "p50": now_t.p50,
            "p95": now_t.p95,
            "previous_p50": prev_t.p50,
            "change_pct": _pct_change(now_t.p50, prev_t.p50) if now_t.p50 is not None else None,
        },
        "no_info_pct": _pct_kpi(now_t.no_info_pct, prev_t.no_info_pct),
        "error_pct": _pct_kpi(now_t.error_pct, prev_t.error_pct),
        "useful_pct": {**_pct_kpi(now_t.useful_pct, prev_t.useful_pct), "rated": now_t.rated},
    }


def _pct_kpi(value: float | None, previous: float | None) -> dict:
    return {
        "value": round(value, 1) if value is not None else 0.0,
        "previous": round(previous, 1) if previous is not None else None,
        "change_pts": _points(value, previous),
    }


def _bucket_labels(period: Period) -> list[str]:
    if period.bucket == "hour":
        return [f"{period.first_day.isoformat()}T{hour:02d}:00" for hour in range(24)]
    days = (period.last_day - period.first_day).days + 1
    return [(period.first_day + timedelta(days=i)).isoformat() for i in range(days)]


@lru_cache(maxsize=16384)
def _local_hour(block: datetime, zone_name: str) -> tuple[str, int]:
    """Día y hora locales de un instante. Se guarda en caché por bloques de 15 minutos: todos los
    desfases horarios son múltiplos de 15 minutos, así que el bloque determina la hora local, y convertir
    decenas de miles de filas una por una era lo más lento del módulo."""
    local = block.replace(tzinfo=UTC).astimezone(ZoneInfo(zone_name))
    return local.date().isoformat(), local.hour


def _bucket_of(row, period: Period) -> str:
    created = row.created_at
    day, hour = _local_hour(
        created.replace(minute=created.minute // 15 * 15, second=0, microsecond=0), settings.cap_timezone
    )
    return f"{day}T{hour:02d}:00" if period.bucket == "hour" else day


def build_series(rows: Sequence, period: Period, group_by: str, artifact_names: dict[str, str]) -> list[dict]:
    def group_of(row) -> str:
        if group_by == "mode":
            return row.mode
        if group_by == "model":
            return row.model or NO_MODEL
        return artifact_names.get(row.artifact_id or "", NO_ARTIFACT)

    by_bucket: dict[str, dict[str, dict]] = {label: {} for label in _bucket_labels(period)}
    for row in rows:
        groups = by_bucket.get(_bucket_of(row, period))
        if groups is None:
            continue
        cell = groups.setdefault(group_of(row), {"spend_usd": 0.0, "queries": 0, "tokens": 0})
        cell["spend_usd"] += float(row.cost_usd or 0)
        cell["queries"] += 1
        cell["tokens"] += _tokens(row)
    return [{"bucket": label, "groups": groups} for label, groups in by_bucket.items()]


def _avg_latency(rows: Sequence) -> float | None:
    values = [r.latency_ms for r in rows if r.outcome not in REJECTED and r.latency_ms is not None]
    return sum(values) / len(values) if values else None


def build_by_artifact(
    session: Session, rows: Sequence, artifacts: list[Artifact]
) -> list[dict]:
    result = []
    for artifact in sorted(artifacts, key=lambda a: a.name.lower()):
        own = [r for r in rows if r.artifact_id == artifact.id]
        result.append(
            {
                "id": artifact.id,
                "name": artifact.name,
                # Gasto de hoy frente al tope: no depende del período ni del filtro de modo elegidos.
                "today_spent_usd": float(spent_today(session, artifact_id=artifact.id)),
                "daily_cap_usd": float(artifact.daily_cap_usd),
                "spend_usd": float(sum(r.cost_usd or 0 for r in own)),
                "queries": len(own),
                "avg_latency_ms": _avg_latency(own),
            }
        )
    return result


def build_by_model(rows: Sequence) -> list[dict]:
    models: dict[str, list] = {}
    for row in rows:
        if row.model:
            models.setdefault(row.model, []).append(row)
    result = [
        {
            "model": model,
            "queries": len(own),
            "tokens": sum(_tokens(r) for r in own),
            "spend_usd": float(sum(r.cost_usd or 0 for r in own)),
            "avg_latency_ms": _avg_latency(own),
        }
        for model, own in models.items()
    ]
    return sorted(result, key=lambda m: m["spend_usd"], reverse=True)


def compute_usage(
    session: Session,
    period: Period,
    artifact_ids: list[str] | None,
    mode: str | None,
    group_by: str,
) -> dict:
    rows = load_rows(session, period.start, period.end, artifact_ids, mode)
    previous = load_rows(session, period.prev_start, period.start, artifact_ids, mode)
    artifacts = list(session.scalars(select(Artifact)))
    names = {a.id: a.name for a in artifacts}
    shown = [a for a in artifacts if not artifact_ids or a.id in artifact_ids]
    return {
        "period": {"from": period.first_day.isoformat(), "to": period.last_day.isoformat(), "bucket": period.bucket},
        "kpis": build_kpis(rows, previous),
        "series": build_series(rows, period, group_by, names),
        "by_artifact": build_by_artifact(session, rows, shown),
        "by_model": build_by_model(rows),
    }
