from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from mia.access.admins import find_active_admin
from mia.access.entra import KeySource, MicrosoftKeys, validate_id_token
from mia.access.errors import not_authorized, unauthenticated
from mia.access.keys import admin_key_matches, bot_service_key_matches, hash_key
from mia.access.scope import AUTOMATION, Principal
from mia.storage.db import get_session
from mia.storage.models import Artifact

_microsoft_keys = MicrosoftKeys()


def get_key_source() -> KeySource:
    """Claves con que se verifican los tokens. Las pruebas la sustituyen con dependency_overrides."""
    return _microsoft_keys


def optional_admin(
    authorization: str = Header(default=""),
    x_admin_key: str = Header(default=""),
    session: Session = Depends(get_session),
    key_source: KeySource = Depends(get_key_source),
) -> Principal | None:
    """Quién administra: la persona del token de Microsoft (si está en la lista), o la clave de
    automatización de los scripts. None si no llegó ninguna credencial."""
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() == "bearer" and token.strip():
        identity = validate_id_token(token.strip(), key_source)
        principal = find_active_admin(session, identity.email)
        if principal is None:
            raise not_authorized()
        return principal
    if x_admin_key:
        # Con ADMIN_KEY vacía la clave está desactivada: se rechaza igual que una incorrecta.
        if admin_key_matches(x_admin_key):
            return AUTOMATION
        raise unauthenticated("Credenciales inválidas.")
    return None


def require_admin(principal: Principal | None = Depends(optional_admin)) -> Principal:
    if principal is None:
        raise unauthenticated()
    return principal


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


def require_bot_service(x_bot_service_key: str = Header(default="")) -> None:
    """Exige la credencial de servicio del bot de WhatsApp (X-Bot-Service-Key). No acepta claves de artefacto ni de
    administración: abre solo las rutas /bot/... Con BOT_SERVICE_KEY vacía responde 401 como con una incorrecta."""
    if not bot_service_key_matches(x_bot_service_key):
        raise HTTPException(status_code=401, detail="Credencial del servicio del bot inválida.")
