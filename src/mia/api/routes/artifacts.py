import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from mia.access.keys import generate_key, hash_key, key_prefix
from mia.access.permissions import allowed_modes, configured_domain_ids
from mia.api.routes.inventory import Name
from mia.api.security import require_admin
from mia.rag.modes import MODE_IDS, MODES, mode_available
from mia.storage.db import get_session
from mia.storage.models import Artifact, ArtifactDomain, ArtifactUnit, Domain, QueryLog, Unit

router = APIRouter(tags=["artifacts"], dependencies=[Depends(require_admin)])

ModeId = Literal["literal", "razonamiento"]
DEFAULT_DAILY_CAP = 0.50


class Access(BaseModel):
    all_domains: bool = False
    unit_ids: list[str] = []
    domain_ids: list[str] = []


class ArtifactCreate(BaseModel):
    name: Name
    description: str = ""
    access: Access
    modes: list[ModeId] = Field(min_length=1)
    daily_cap_usd: float | None = Field(default=None, gt=0)
    reasoning_daily_cap_usd: float | None = Field(default=None, gt=0)


class ArtifactUpdate(BaseModel):
    description: str | None = None
    access: Access | None = None
    modes: list[ModeId] | None = Field(default=None, min_length=1)
    daily_cap_usd: float | None = Field(default=None, gt=0)
    reasoning_daily_cap_usd: float | None = Field(default=None, gt=0)
    active: bool | None = None


class ArtifactOut(BaseModel):
    id: str
    name: str
    description: str
    key_prefix: str
    active: bool
    access: Access
    allowed_domain_count: int
    modes: list[str]
    daily_cap_usd: float
    reasoning_daily_cap_usd: float | None
    queries_last_7_days: int
    created_at: str


class ArtifactCreatedOut(ArtifactOut):
    # Solo al crear: la clave completa se muestra una única vez y no se puede volver a ver.
    key: str


class ModeOut(BaseModel):
    id: str
    name: str
    available: bool
    avg_cost_usd_7d: float | None


class ArtifactsOut(BaseModel):
    artifacts: list[ArtifactOut]
    modes: list[ModeOut]


class NewKeyOut(BaseModel):
    key: str
    key_prefix: str


def _week_ago() -> datetime:
    return (datetime.now(UTC) - timedelta(days=7)).replace(tzinfo=None)


def _to_out(session: Session, artifact: Artifact) -> ArtifactOut:
    unit_ids = sorted(session.scalars(select(ArtifactUnit.unit_id).where(ArtifactUnit.artifact_id == artifact.id)))
    domain_ids = sorted(
        session.scalars(select(ArtifactDomain.domain_id).where(ArtifactDomain.artifact_id == artifact.id))
    )
    queries = session.scalar(
        select(func.count()).select_from(QueryLog).where(
            QueryLog.artifact_id == artifact.id, QueryLog.created_at >= _week_ago()
        )
    )
    reasoning_cap = artifact.reasoning_daily_cap_usd
    return ArtifactOut(
        id=artifact.id,
        name=artifact.name,
        description=artifact.description,
        key_prefix=artifact.key_prefix,
        active=artifact.active,
        access=Access(all_domains=artifact.all_domains, unit_ids=unit_ids, domain_ids=domain_ids),
        allowed_domain_count=len(configured_domain_ids(session, artifact)),
        modes=allowed_modes(artifact),
        daily_cap_usd=float(artifact.daily_cap_usd),
        reasoning_daily_cap_usd=float(reasoning_cap) if reasoning_cap is not None else None,
        queries_last_7_days=queries or 0,
        created_at=artifact.created_at.isoformat() + "Z",
    )


def _validate_access(session: Session, access: Access) -> None:
    if not (access.all_domains or access.unit_ids or access.domain_ids):
        raise HTTPException(status_code=422, detail="El artefacto debe tener acceso al menos a un dominio o unidad.")
    known_units = set(session.scalars(select(Unit.id).where(Unit.id.in_(access.unit_ids)))) if access.unit_ids else set()
    missing_units = set(access.unit_ids) - known_units
    known_domains = (
        set(session.scalars(select(Domain.id).where(Domain.id.in_(access.domain_ids)))) if access.domain_ids else set()
    )
    missing_domains = set(access.domain_ids) - known_domains
    if missing_units or missing_domains:
        raise HTTPException(
            status_code=422,
            detail="Unidades o dominios inexistentes: " + ", ".join(sorted(missing_units | missing_domains)),
        )


def _validate_caps(daily: float, reasoning: float | None) -> None:
    if reasoning is not None and reasoning > daily:
        raise HTTPException(
            status_code=422, detail="El tope de razonamiento no puede superar el tope diario total del artefacto."
        )


def _set_access(session: Session, artifact: Artifact, access: Access) -> None:
    artifact.all_domains = access.all_domains
    session.execute(delete(ArtifactUnit).where(ArtifactUnit.artifact_id == artifact.id))
    session.execute(delete(ArtifactDomain).where(ArtifactDomain.artifact_id == artifact.id))
    session.add_all([ArtifactUnit(artifact_id=artifact.id, unit_id=u) for u in dict.fromkeys(access.unit_ids)])
    session.add_all([ArtifactDomain(artifact_id=artifact.id, domain_id=d) for d in dict.fromkeys(access.domain_ids)])


def _modes_text(modes: list[str]) -> str:
    return ",".join(m for m in MODE_IDS if m in modes)


@router.get("/artifacts", response_model=ArtifactsOut)
def list_artifacts(session: Session = Depends(get_session)) -> ArtifactsOut:
    artifacts = session.scalars(select(Artifact).order_by(Artifact.name)).all()
    # Costo medio por consulta de cada modo en los últimos 7 días: solo las que llegaron al modelo
    # (con respuesta o "sin información" del modelo), no las rechazadas ni las sin resultados.
    averages = {
        mode: float(avg) if avg is not None else None
        for mode, avg in session.execute(
            select(QueryLog.mode, func.avg(QueryLog.cost_usd))
            .where(
                QueryLog.created_at >= _week_ago(),
                QueryLog.outcome.in_(["answered", "no_info"]),
                QueryLog.model.is_not(None),
            )
            .group_by(QueryLog.mode)
        )
    }
    modes = [
        ModeOut(
            id=mode,
            name=MODES[mode].name,
            available=mode_available(mode)[0],
            avg_cost_usd_7d=averages.get(mode),
        )
        for mode in MODE_IDS
    ]
    return ArtifactsOut(artifacts=[_to_out(session, a) for a in artifacts], modes=modes)


@router.post("/artifacts", response_model=ArtifactCreatedOut, status_code=201)
def create_artifact(payload: ArtifactCreate, session: Session = Depends(get_session)) -> ArtifactCreatedOut:
    if session.scalar(select(Artifact).where(Artifact.name == payload.name)) is not None:
        raise HTTPException(status_code=409, detail=f"Ya existe un artefacto llamado '{payload.name}'.")
    daily = payload.daily_cap_usd if payload.daily_cap_usd is not None else DEFAULT_DAILY_CAP
    _validate_caps(daily, payload.reasoning_daily_cap_usd)
    _validate_access(session, payload.access)

    key = generate_key()
    artifact = Artifact(
        id=str(uuid.uuid4()),
        name=payload.name,
        description=payload.description,
        key_hash=hash_key(key),
        key_prefix=key_prefix(key),
        modes=_modes_text(payload.modes),
        daily_cap_usd=Decimal(str(daily)),
        reasoning_daily_cap_usd=(
            Decimal(str(payload.reasoning_daily_cap_usd)) if payload.reasoning_daily_cap_usd is not None else None
        ),
    )
    session.add(artifact)
    session.flush()
    _set_access(session, artifact, payload.access)
    session.commit()
    session.refresh(artifact)
    return ArtifactCreatedOut(**_to_out(session, artifact).model_dump(), key=key)


@router.patch("/artifacts/{artifact_id}", response_model=ArtifactOut)
def update_artifact(
    artifact_id: str, payload: ArtifactUpdate, session: Session = Depends(get_session)
) -> ArtifactOut:
    artifact = session.get(Artifact, artifact_id)
    if artifact is None:
        raise HTTPException(status_code=404, detail="Artefacto no encontrado.")
    changes = payload.model_fields_set

    # Los topes se validan contra el resultado final, mezclando lo enviado con lo que ya tenía.
    daily = payload.daily_cap_usd if "daily_cap_usd" in changes and payload.daily_cap_usd is not None else float(
        artifact.daily_cap_usd
    )
    if "reasoning_daily_cap_usd" in changes:
        reasoning = payload.reasoning_daily_cap_usd
    else:
        reasoning = float(artifact.reasoning_daily_cap_usd) if artifact.reasoning_daily_cap_usd is not None else None
    _validate_caps(daily, reasoning)

    if payload.access is not None:
        _validate_access(session, payload.access)
        _set_access(session, artifact, payload.access)
    if payload.description is not None:
        artifact.description = payload.description
    if payload.modes is not None:
        artifact.modes = _modes_text(payload.modes)
    if "daily_cap_usd" in changes and payload.daily_cap_usd is not None:
        artifact.daily_cap_usd = Decimal(str(payload.daily_cap_usd))
    if "reasoning_daily_cap_usd" in changes:
        artifact.reasoning_daily_cap_usd = Decimal(str(reasoning)) if reasoning is not None else None
    if payload.active is not None:
        artifact.active = payload.active
    session.commit()
    session.refresh(artifact)
    return _to_out(session, artifact)


@router.post("/artifacts/{artifact_id}/key", response_model=NewKeyOut)
def regenerate_key(artifact_id: str, session: Session = Depends(get_session)) -> NewKeyOut:
    artifact = session.get(Artifact, artifact_id)
    if artifact is None:
        raise HTTPException(status_code=404, detail="Artefacto no encontrado.")
    key = generate_key()
    artifact.key_hash = hash_key(key)
    artifact.key_prefix = key_prefix(key)
    session.commit()
    return NewKeyOut(key=key, key_prefix=key_prefix(key))
