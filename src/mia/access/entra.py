"""Validación del token de identidad (ID token) de Microsoft Entra ID, sin dependencias de FastAPI.

El emisor y la dirección de las claves salen del tenant configurado (el del TEC), nunca del token.
Decisiones en specs/004-acceso-panel-tec/research.md.
"""

import json
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

import httpx
import jwt
from jwt.algorithms import RSAAlgorithm

from mia.access.errors import (
    AuthError,
    identity_unavailable,
    invalid_token,
    login_not_configured,
    mfa_required,
    token_expired,
)
from mia.config import settings

KEYS_TTL_SECONDS = 3600
# Mínimo entre bajadas de claves ante un kid desconocido, para que tokens falsos no obliguen a
# consultar a Microsoft sin fin.
UNKNOWN_KID_MIN_SECONDS = 300
CLOCK_LEEWAY_SECONDS = 60


class KeySource(Protocol):
    def get_key(self, kid: str): ...


@dataclass(frozen=True)
class Identity:
    email: str
    mfa: bool


def _fetch_microsoft_keys() -> list[dict]:
    url = f"https://login.microsoftonline.com/{settings.entra_tenant_id}/discovery/v2.0/keys"
    response = httpx.get(url, timeout=5)
    response.raise_for_status()
    return response.json()["keys"]


class MicrosoftKeys:
    """Claves públicas de firma del directorio, en memoria. Se renuevan cada hora y ante un kid
    desconocido (con un mínimo entre bajadas). Si la bajada falla se siguen usando las que hay."""

    def __init__(self, fetch: Callable[[], list[dict]] = _fetch_microsoft_keys, clock=time.monotonic):
        self._fetch = fetch
        self._clock = clock
        self._lock = threading.Lock()
        self._keys: dict | None = None
        self._fetched_at = 0.0
        self._last_unknown_refresh = float("-inf")

    def _refresh(self) -> None:
        try:
            keys = {
                k["kid"]: RSAAlgorithm.from_jwk(json.dumps(k)) for k in self._fetch() if k.get("kty") == "RSA"
            }
        except Exception as error:  # red caída, respuesta inesperada
            if self._keys is None:
                raise identity_unavailable() from error
            return  # se siguen usando las claves guardadas
        self._keys = keys
        self._fetched_at = self._clock()

    def get_key(self, kid: str):
        with self._lock:
            now = self._clock()
            refreshed = False
            if self._keys is None or now - self._fetched_at > KEYS_TTL_SECONDS:
                self._refresh()
                refreshed = True
            key = self._keys.get(kid) if self._keys is not None else None
            if key is None and not refreshed and now - self._last_unknown_refresh >= UNKNOWN_KID_MIN_SECONDS:
                self._last_unknown_refresh = now
                self._refresh()
                key = self._keys.get(kid) if self._keys is not None else None
            return key


def validate_id_token(token: str, key_source: KeySource) -> Identity:
    """Valida firma, emisor, audiencia, tenant, vigencia y segundo factor, y devuelve el correo."""
    if not settings.entra_client_id:
        raise login_not_configured()
    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError as error:
        raise invalid_token() from error
    kid = header.get("kid")
    if header.get("alg") != "RS256" or not kid:
        raise invalid_token()
    key = key_source.get_key(kid)
    if key is None:
        raise invalid_token()
    tenant = settings.entra_tenant_id
    try:
        claims = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            audience=settings.entra_client_id,
            issuer=f"https://login.microsoftonline.com/{tenant}/v2.0",
            leeway=CLOCK_LEEWAY_SECONDS,
            options={"require": ["exp", "iat", "aud", "iss"]},
        )
    except jwt.ExpiredSignatureError as error:
        raise token_expired() from error
    except jwt.PyJWTError as error:
        raise invalid_token() from error
    if claims.get("tid") != tenant:
        raise invalid_token()
    amr = claims.get("amr")
    mfa = isinstance(amr, list) and "mfa" in amr
    if settings.entra_require_mfa and not mfa:
        raise mfa_required()
    email = claims.get("email") or claims.get("preferred_username")
    if not isinstance(email, str) or "@" not in email:
        raise invalid_token()
    return Identity(email=email.strip().lower(), mfa=mfa)


__all__ = ["AuthError", "Identity", "KeySource", "MicrosoftKeys", "validate_id_token"]
