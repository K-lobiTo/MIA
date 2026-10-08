from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from mia.access.caps import artifact_status
from mia.access.permissions import allowed_modes
from mia.api.security import optional_artifact
from mia.config import settings
from mia.rag.modes import MODE_IDS, MODES, RAZONAMIENTO, mode_available
from mia.storage.db import get_session
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


class CapsOut(BaseModel):
    cap_reached: bool
    reasoning_cap_reached: bool
    global_cap_reached: bool
    resets_at: str


class ArtifactConfigOut(ConfigOut):
    # Solo cuando se pidió con la clave de un artefacto.
    artifact: ArtifactInfo
    caps: CapsOut


# La variante con artefacto va primero para que no se pierda su campo extra al serializar.
@router.get("/config", response_model=ArtifactConfigOut | ConfigOut)
def get_config(
    artifact: Artifact | None = Depends(optional_artifact), session: Session = Depends(get_session)
) -> ConfigOut:
    """Qué puede hacer la instancia. Con la clave de un artefacto, solo lo que ese artefacto puede
    usar: así el artefacto muestra únicamente los modos que le corresponden."""
    visible = allowed_modes(artifact) if artifact is not None else MODE_IDS
    state = artifact_status(session, artifact) if artifact is not None else None
    modes = []
    for mode in MODE_IDS:
        if mode not in visible:
            continue
        available, reason = mode_available(mode)
        # Un tope alcanzado deshabilita el modo (o todos) en la configuración que ve el artefacto,
        # para que muestre el motivo en vez de dejar que la consulta falle (CON-3).
        if available and state is not None:
            if state.global_cap_reached:
                available, reason = False, "Se alcanzó el tope diario de gasto de toda la API. Se reinicia a la medianoche."
            elif state.cap_reached:
                available, reason = False, "Este artefacto alcanzó su tope diario de gasto. Se reinicia a la medianoche."
            elif mode == RAZONAMIENTO and state.reasoning_cap_reached:
                available, reason = False, "Este artefacto alcanzó su tope diario del modo con razonamiento. Se reinicia a la medianoche."
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
    return ArtifactConfigOut(
        **base,
        artifact=ArtifactInfo(name=artifact.name, active=artifact.active),
        caps=CapsOut(
            cap_reached=state.cap_reached,
            reasoning_cap_reached=state.reasoning_cap_reached,
            global_cap_reached=state.global_cap_reached,
            resets_at=state.resets_at.isoformat() + "Z",
        ),
    )
