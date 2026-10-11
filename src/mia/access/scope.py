"""Alcance de una persona que administra MIA: qué unidades, dominios y artefactos puede ver y operar.

Sin dependencias de HTTP, para probarlo sin levantar la API. Alcance global: todo, incluido lo que no
pertenece a ninguna unidad. Alcance de unidad: solo lo que queda dentro de sus unidades.
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from mia.storage.models import Artifact, ArtifactDomain, ArtifactUnit, Domain


@dataclass(frozen=True)
class Principal:
    email: str | None
    is_global: bool
    unit_ids: frozenset[str] = frozenset()
    # "entra" (inicio de sesión con cuenta del TEC) o "automation" (ADMIN_KEY de los scripts)
    source: str = "entra"

    @property
    def label(self) -> str:
        """Quién figura en el registro del servidor."""
        return self.email or "automatizacion"


AUTOMATION = Principal(email=None, is_global=True, source="automation")


def unit_in_scope(principal: Principal, unit_id: str | None) -> bool:
    if principal.is_global:
        return True
    return unit_id is not None and unit_id in principal.unit_ids


def domain_in_scope(principal: Principal, domain: Domain) -> bool:
    # Un dominio sin unidad (anterior a la reorganización) es solo del alcance global.
    return unit_in_scope(principal, domain.unit_id)


def _units_of(session: Session, unit_ids: list[str], domain_ids: list[str]) -> set[str | None]:
    """Unidades que toca un acceso: las dadas más la unidad de cada dominio puntual (None si no tiene)."""
    units: set[str | None] = set(unit_ids)
    if domain_ids:
        found = dict(session.execute(select(Domain.id, Domain.unit_id).where(Domain.id.in_(domain_ids))).all())
        units.update(found.get(domain_id) for domain_id in domain_ids)
    return units


def can_grant_access(
    session: Session, principal: Principal, all_domains: bool, unit_ids: list[str], domain_ids: list[str]
) -> bool:
    """Si el alcance permite dar este acceso a un artefacto: todo el acceso debe caer en sus unidades,
    y "todos los dominios" es solo del alcance global."""
    if principal.is_global:
        return True
    if all_domains:
        return False
    return all(unit_in_scope(principal, unit) for unit in _units_of(session, unit_ids, domain_ids))


def artifact_in_scope(session: Session, principal: Principal, artifact: Artifact) -> bool:
    """Un artefacto es del alcance de unidad si da acceso exclusivamente a dominios de sus unidades."""
    if principal.is_global:
        return True
    if artifact.all_domains:
        return False
    unit_ids = list(session.scalars(select(ArtifactUnit.unit_id).where(ArtifactUnit.artifact_id == artifact.id)))
    domain_ids = list(
        session.scalars(select(ArtifactDomain.domain_id).where(ArtifactDomain.artifact_id == artifact.id))
    )
    if not unit_ids and not domain_ids:
        return False
    return can_grant_access(session, principal, False, unit_ids, domain_ids)


def artifact_ids_in_scope(session: Session, principal: Principal) -> list[str] | None:
    """Ids de los artefactos que cubre el alcance. None (alcance global) significa todos; una lista
    vacía significa ninguno."""
    if principal.is_global:
        return None
    return [a.id for a in session.scalars(select(Artifact)) if artifact_in_scope(session, principal, a)]
