from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from mia.access.scope import Principal
from mia.api.security import require_admin
from mia.storage.db import get_session
from mia.storage.models import Unit

router = APIRouter(tags=["me"])


class UnitRef(BaseModel):
    id: str
    name: str


class MeOut(BaseModel):
    email: str | None
    is_global: bool
    units: list[UnitRef]
    source: str


@router.get("/me", response_model=MeOut)
def me(principal: Principal = Depends(require_admin), session: Session = Depends(get_session)) -> MeOut:
    """Quién es la persona que inició sesión y qué alcance tiene: lo usa el panel tras entrar."""
    units = session.scalars(select(Unit).where(Unit.id.in_(principal.unit_ids)).order_by(Unit.name))
    return MeOut(
        email=principal.email,
        is_global=principal.is_global,
        units=[UnitRef(id=u.id, name=u.name) for u in units],
        source=principal.source,
    )
