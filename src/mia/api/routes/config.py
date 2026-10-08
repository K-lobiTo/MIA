from fastapi import APIRouter, Depends
from pydantic import BaseModel

from mia.access.permissions import allowed_modes
from mia.api.security import optional_artifact
from mia.config import settings
from mia.rag.modes import MODE_IDS, MODES, mode_available
from mia.storage.models import Artifact

router = APIRouter(tags=["config"])


class ModeConfigOut(BaseModel):
    id: str
    name: str
    description: str
    available: bool
    reason: str | None


class ArtifactInfo(BaseModel):
    name: str
    active: bool


class ConfigOut(BaseModel):
    ingestion_enabled: bool
    max_upload_mb: int
    modes: list[ModeConfigOut]


class ArtifactConfigOut(ConfigOut):
    # Solo cuando se pidió con la clave de un artefacto.
    artifact: ArtifactInfo


# La variante con artefacto va primero para que no se pierda su campo extra al serializar.
@router.get("/config", response_model=ArtifactConfigOut | ConfigOut)
def get_config(artifact: Artifact | None = Depends(optional_artifact)) -> ConfigOut:
    """Qué puede hacer la instancia. Con la clave de un artefacto, solo lo que ese artefacto puede
    usar: así el artefacto muestra únicamente los modos que le corresponden."""
    visible = allowed_modes(artifact) if artifact is not None else MODE_IDS
    modes = []
    for mode in MODE_IDS:
        if mode not in visible:
            continue
        available, reason = mode_available(mode)
        info = MODES[mode]
        modes.append(
            ModeConfigOut(id=mode, name=info.name, description=info.description, available=available, reason=reason)
        )
    base = {
        "ingestion_enabled": settings.ingestion_enabled,
        "max_upload_mb": settings.max_upload_mb,
        "modes": modes,
    }
    if artifact is None:
        return ConfigOut(**base)
    return ArtifactConfigOut(**base, artifact=ArtifactInfo(name=artifact.name, active=artifact.active))
