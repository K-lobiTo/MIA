"""Inicio y cierre de sesión de los usuarios de la Consulta (feature 015): POST /auth/login, POST /auth/logout,
GET /auth/me y POST /auth/password.

No exigen la clave del artefacto (la persona se identifica con su usuario y contraseña); consultar sí la sigue exigiendo.
Un fallo de inicio de sesión da siempre el mismo mensaje (no revela si el usuario existe) y, antes de verificar, se
consulta el límite de intentos: bloqueado, responde 429 aunque la contraseña sea correcta. El registro del servidor escribe
solo el resultado, el usuario normalizado y el origen: nunca la contraseña ni el token.
Contrato en specs/015-historial-chats/contracts/auth-api.md."""

import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from mia.access.errors import invalid_credentials, too_many_attempts
from mia.api.security import require_session
from mia.chat import passwords, retention, sessions
from mia.chat.sessions import SessionInfo
from mia.chat.throttle import client_origin, login_throttle
from mia.storage.db import get_session
from mia.storage.models import ConsultaUser, _now

logger = logging.getLogger("mia.chat")

router = APIRouter(tags=["auth"])


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=200)
    password: str = Field(min_length=1, max_length=1000)


class UserRef(BaseModel):
    username: str


class LoginOut(BaseModel):
    token: str
    expires_at: str
    user: UserRef


class MeOut(BaseModel):
    username: str
    expires_at: str


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=1000)
    new_password: str = Field(min_length=1, max_length=1000)


def _iso(value) -> str:
    return value.isoformat() + "Z"


def _logged_name(username: str) -> str:
    """El nombre para el registro: solo si tiene forma de usuario (así no queda copiado algo que se escribió por error)."""
    return username if passwords.validate_username(username) is None else "(invalido)"


@router.post("/auth/login", response_model=LoginOut)
def login(payload: LoginIn, request: Request, session: Session = Depends(get_session)) -> LoginOut:
    username = passwords.normalize_username(payload.username)
    origin = client_origin(request)
    retention.maybe_purge(session)
    wait = login_throttle.check(username, origin)
    if wait > 0:
        logger.info(
            "Inicio de sesión resultado=bloqueado usuario=%s origen=%s",
            _logged_name(username),
            origin,
        )
        raise too_many_attempts(wait)
    user = session.scalar(select(ConsultaUser).where(ConsultaUser.username == username))
    # Se hace siempre una verificación (con un hash de relleno si el usuario no existe) para igualar el trabajo y el tiempo.
    stored = user.password_hash if user is not None else passwords.DUMMY_HASH
    correct = passwords.verify_password(payload.password, stored)
    if user is None or not user.active or not correct:
        login_throttle.fail(username, origin)
        logger.info(
            "Inicio de sesión resultado=fallo usuario=%s origen=%s", _logged_name(username), origin
        )
        raise invalid_credentials()
    login_throttle.clear_user(username)
    if passwords.needs_rehash(user.password_hash):
        user.password_hash = passwords.hash_password(payload.password)
    user.last_login_at = _now()
    session.commit()
    token, row = sessions.create_session(session, user)
    logger.info("Inicio de sesión resultado=ok usuario=%s origen=%s", user.username, origin)
    return LoginOut(
        token=token, expires_at=_iso(row.expires_at), user=UserRef(username=user.username)
    )


@router.post("/auth/logout", status_code=204, response_class=Response)
def logout(
    x_session_token: str = Header(default=""), session: Session = Depends(get_session)
) -> Response:
    """Cierra la sesión. Con un token inválido o ya cerrado también responde 204: cerrar lo ya cerrado no es un error."""
    if x_session_token:
        sessions.close_session(session, x_session_token.strip())
    return Response(status_code=204)


@router.get("/auth/me", response_model=MeOut)
def me(info: SessionInfo = Depends(require_session)) -> MeOut:
    return MeOut(username=info.user.username, expires_at=_iso(info.expires_at))


@router.post("/auth/password", status_code=204, response_class=Response)
def change_password(
    payload: PasswordChange,
    request: Request,
    info: SessionInfo = Depends(require_session),
    session: Session = Depends(get_session),
) -> Response:
    user = info.user
    origin = client_origin(request)
    wait = login_throttle.check(user.username, origin)
    if wait > 0:
        raise too_many_attempts(wait)
    if not passwords.verify_password(payload.current_password, user.password_hash):
        login_throttle.fail(user.username, origin)
        raise invalid_credentials()
    problem = passwords.validate_password(payload.new_password)
    if problem is None and payload.new_password == payload.current_password:
        problem = "La contraseña nueva debe ser distinta de la actual."
    if problem is not None:
        raise HTTPException(status_code=422, detail=problem)
    user.password_hash = passwords.hash_password(payload.new_password)
    session.commit()
    sessions.close_user_sessions(session, user.id, except_id=info.session_id)
    login_throttle.clear_user(user.username)
    logger.info("Cambio de contraseña resultado=ok usuario=%s", user.username)
    return Response(status_code=204)
