from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from mia.api.security import require_admin
from mia.storage.db import get_session
from mia.storage.models import QueryLog
from mia.usage import balance as balance_module
from mia.usage import log as log_module
from mia.usage.aggregate import Period, compute_usage, load_rows, page_rows, resolve_period

router = APIRouter(tags=["usage"], dependencies=[Depends(require_admin)])

PeriodName = Literal["today", "7d", "30d", "custom"]
ModeName = Literal["literal", "razonamiento"]


class UsageFilters:
    """Filtros comunes del módulo Uso: período, artefactos y modo (USO-1)."""

    def __init__(
        self,
        period: PeriodName = "7d",
        from_: Annotated[str | None, Query(alias="from")] = None,
        to: str | None = None,
        artifact_id: Annotated[list[str] | None, Query()] = None,
        mode: ModeName | None = None,
    ):
        try:
            self.period: Period = resolve_period(period, from_, to)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        self.artifact_ids = artifact_id or None
        self.mode = mode


class UsageOut(BaseModel):
    # La forma exacta está en specs/002-panel-administracion/contracts/api-uso.md.
    period: dict
    kpis: dict
    series: list[dict]
    by_artifact: list[dict]
    by_model: list[dict]


@router.get("/usage", response_model=UsageOut)
def usage(
    filters: UsageFilters = Depends(),
    group_by: Literal["artifact", "mode", "model"] = "artifact",
    session: Session = Depends(get_session),
) -> dict:
    return compute_usage(session, filters.period, filters.artifact_ids, filters.mode, group_by)


@router.get("/usage/queries")
def usage_queries(
    filters: UsageFilters = Depends(),
    outcome: Annotated[list[str] | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
    format: Literal["json", "csv"] = "json",
    include_questions: bool = False,
    session: Session = Depends(get_session),
):
    period = filters.period
    names = log_module.artifact_names(session)
    if format == "csv":
        rows = load_rows(session, period.start, period.end, filters.artifact_ids, filters.mode, outcome, light=False)
        rows.sort(key=lambda r: (r.created_at, r.id), reverse=True)
        filename = f"mia-consultas-{filters.period.first_day}-{filters.period.last_day}.csv"
        return Response(
            content=log_module.to_csv(rows, names, include_questions),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    total, rows = page_rows(
        session, period.start, period.end, filters.artifact_ids, filters.mode, outcome, page, page_size
    )
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [log_module.list_item(r, names) for r in rows],
    }


@router.get("/usage/queries/{query_id}")
def usage_query_detail(query_id: str, session: Session = Depends(get_session)) -> dict:
    row = session.scalar(select(QueryLog).where(QueryLog.id == query_id))
    if row is None:
        raise HTTPException(status_code=404, detail="Consulta no encontrada.")
    return log_module.detail(session, row)


@router.get("/usage/balance")
def usage_balance(session: Session = Depends(get_session)) -> dict:
    return balance_module.get_balance(session)
