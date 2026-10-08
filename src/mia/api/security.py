from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from mia.access.keys import admin_key_matches, hash_key
from mia.config import settings
from mia.storage.db import get_session
from mia.storage.models import Artifact


def require_admin(x_admin_key: str = Header(default="")) -> None:
    if not settings.admin_key:
        raise HTTPException(
            status_code=503,
            detail="La instancia no tiene configurada la clave de administración (ADMIN_KEY).",
        )
    if not x_admin_key or not admin_key_matches(x_admin_key):
        raise HTTPException(status_code=401, detail="Clave de administración inválida.")


def optional_artifact(
    x_artifact_key: str = Header(default=""), session: Session = Depends(get_session)
) -> Artifact | None:
    """Artefacto dueño de la clave enviada, o None si no se envió. Una clave enviada que no
    corresponde a ningún artefacto es un 401."""
    if not x_artifact_key:
        return None
    artifact = session.scalar(select(Artifact).where(Artifact.key_hash == hash_key(x_artifact_key)))
    if artifact is None:
        raise HTTPException(status_code=401, detail="Clave de artefacto inválida.")
    return artifact


def require_artifact(artifact: Artifact | None = Depends(optional_artifact)) -> Artifact:
    # No se verifica `active` aquí: cada ruta responde 403 y registra el rechazo.
    if artifact is None:
        raise HTTPException(status_code=401, detail="Falta la clave de artefacto (X-Artifact-Key).")
    return artifact
