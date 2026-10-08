from sqlalchemy import select
from sqlalchemy.orm import Session

from mia.rag.modes import MODE_IDS
from mia.storage.models import Artifact, ArtifactDomain, ArtifactUnit, Domain


def allowed_domain_ids(session: Session, artifact: Artifact) -> set[str]:
    """Dominios que el artefacto puede consultar ahora: ninguno si está desactivado."""
    return configured_domain_ids(session, artifact) if artifact.active else set()


def configured_domain_ids(session: Session, artifact: Artifact) -> set[str]:
    """Dominios que cubre el acceso configurado, esté o no activo el artefacto: todos, o los de sus
    unidades más sus dominios puntuales. Se calcula en cada consulta: un dominio nuevo de una unidad
    permitida queda visible de inmediato, y un cambio de acceso rige desde la consulta siguiente."""
    if artifact.all_domains:
        return set(session.scalars(select(Domain.id)))
    unit_ids = list(session.scalars(select(ArtifactUnit.unit_id).where(ArtifactUnit.artifact_id == artifact.id)))
    from_units = set(session.scalars(select(Domain.id).where(Domain.unit_id.in_(unit_ids)))) if unit_ids else set()
    own = set(session.scalars(select(ArtifactDomain.domain_id).where(ArtifactDomain.artifact_id == artifact.id)))
    return from_units | own


def allowed_modes(artifact: Artifact) -> list[str]:
    """Modos permitidos, sin repetir ni valores desconocidos y en el orden configurado."""
    modes: list[str] = []
    for mode in artifact.modes.split(","):
        mode = mode.strip()
        if mode in MODE_IDS and mode not in modes:
            modes.append(mode)
    return modes
