"""Eliminación de programas y dominios (feature 023). Contrato en
specs/023-eliminar-programas-dominios/contracts/eliminar-estructura-api.md.

Un dominio lo elimina quien puede crearlo (alcance global o su programa); un programa, solo el alcance global. La API
elimina al recibir el pedido: la confirmación es del panel, que antes consulta `.../deletion`."""

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from mia.access import audit, structure
from mia.access.guards import ensure_domain, ensure_global
from mia.access.scope import Principal
from mia.api.security import require_admin
from mia.storage.db import get_session
from mia.storage.models import Domain, Unit
from mia.storage.vector_store import get_vector_store

router = APIRouter(tags=["structure"])

CHANGED_MESSAGE = "Algo cambió mientras se eliminaba (por ejemplo, alguien agregó contenido). No se eliminó nada; vuelve a intentarlo."
STORE_MESSAGE = "No se pudo revisar el almacén de búsqueda. No se eliminó nada; intenta de nuevo en un momento."


class DeletionItem(BaseModel):
    kind: str
    count: int
    names: list[str]
    hint: str


class DeletionCheck(BaseModel):
    name: str
    can_delete: bool
    blockers: list[DeletionItem]
    affects: list[DeletionItem]


def _check(name: str, blockers: list[structure.Item], affects: list[structure.Item]) -> DeletionCheck:
    return DeletionCheck(
        name=name,
        can_delete=not blockers,
        blockers=[DeletionItem(**vars(item)) for item in blockers],
        affects=[DeletionItem(**vars(item)) for item in affects],
    )


def _domain(session: Session, principal: Principal, domain_id: str) -> Domain:
    domain = session.get(Domain, domain_id)
    if domain is None:
        raise HTTPException(status_code=404, detail="Dominio no encontrado.")
    ensure_domain(principal, domain, "domain.delete")
    return domain


def _unit(session: Session, principal: Principal, unit_id: str) -> Unit:
    ensure_global(principal, "unit.delete", unit_id)
    unit = session.get(Unit, unit_id)
    if unit is None:
        raise HTTPException(status_code=404, detail="Programa no encontrado.")
    return unit


@router.get("/domains/{domain_id}/deletion", response_model=DeletionCheck)
def check_domain(
    domain_id: str, principal: Principal = Depends(require_admin), session: Session = Depends(get_session)
) -> DeletionCheck:
    domain = _domain(session, principal, domain_id)
    blockers = structure.domain_blockers(session, domain_id)
    # Con impedimentos no se llega a eliminar: no hace falta decir a quién afectaría.
    affects = [] if blockers else structure.domain_affects(session, principal, domain_id)
    return _check(domain.name, blockers, affects)


@router.delete("/domains/{domain_id}", status_code=204)
def delete_domain(
    domain_id: str, principal: Principal = Depends(require_admin), session: Session = Depends(get_session)
) -> Response:
    _domain(session, principal, domain_id)
    try:
        name = structure.delete_domain(session, get_vector_store(), domain_id)
    except structure.NotFound as exc:
        raise HTTPException(status_code=404, detail="Dominio no encontrado.") from exc
    except structure.Blocked as exc:
        raise HTTPException(status_code=409, detail=structure.blocked_message("dominio", exc.name, exc.blockers)) from exc
    except structure.Changed as exc:
        raise HTTPException(status_code=409, detail=CHANGED_MESSAGE) from exc
    except structure.StoreUnavailable as exc:
        raise HTTPException(status_code=503, detail=STORE_MESSAGE) from exc
    audit.log_write(principal, "domain.delete", domain_id, name)
    return Response(status_code=204)


@router.get("/units/{unit_id}/deletion", response_model=DeletionCheck)
def check_unit(
    unit_id: str, principal: Principal = Depends(require_admin), session: Session = Depends(get_session)
) -> DeletionCheck:
    unit = _unit(session, principal, unit_id)
    return _check(unit.name, structure.unit_blockers(session, unit_id), [])


@router.delete("/units/{unit_id}", status_code=204)
def delete_unit(
    unit_id: str, principal: Principal = Depends(require_admin), session: Session = Depends(get_session)
) -> Response:
    _unit(session, principal, unit_id)
    try:
        name = structure.delete_unit(session, unit_id)
    except structure.NotFound as exc:
        raise HTTPException(status_code=404, detail="Programa no encontrado.") from exc
    except structure.Blocked as exc:
        raise HTTPException(status_code=409, detail=structure.blocked_message("programa", exc.name, exc.blockers)) from exc
    except structure.Changed as exc:
        raise HTTPException(status_code=409, detail=CHANGED_MESSAGE) from exc
    audit.log_write(principal, "unit.delete", unit_id, name)
    return Response(status_code=204)
