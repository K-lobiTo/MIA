"""Sesiones de los usuarios de la Consulta (feature 015, research R2) y las dependencias que las usan."""

import uuid
from datetime import timedelta

import pytest
from fastapi import APIRouter, Depends
from fastapi.testclient import TestClient

from mia.access.keys import hash_key
from mia.api.main import app
from mia.api.security import optional_user, require_user
from mia.chat import sessions
from mia.config import settings
from mia.storage.models import ConsultaSession, ConsultaUser, _now


def _usuario(db, nombre="ana", activo=True) -> str:
    uid = str(uuid.uuid4())
    with db() as session:
        session.add(
            ConsultaUser(
                id=uid, username=nombre, password_hash="x", active=activo, created_by="prueba"
            )
        )
        session.commit()
    return uid


def _crear(db, uid):
    with db() as session:
        usuario = session.get(ConsultaUser, uid)
        token, fila = sessions.create_session(session, usuario)
        return token, fila.id


def test_el_token_tiene_prefijo_y_en_la_base_solo_queda_su_hash(db):
    uid = _usuario(db)
    token, _ = _crear(db, uid)

    assert token.startswith("mias_") and len(token) > 30
    with db() as session:
        fila = session.query(ConsultaSession).one()
        assert fila.token_hash == hash_key(token)
        for columna in ("id", "user_id", "token_hash"):
            assert token not in str(getattr(fila, columna))


def test_resolve_devuelve_al_usuario_activo_y_nada_para_los_demas_casos(db):
    uid = _usuario(db)
    token, _ = _crear(db, uid)

    with db() as session:
        info = sessions.resolve_session(session, token)
        assert info is not None and info.user.id == uid and info.expires_at > _now()
        assert sessions.resolve_session(session, "mias_inventado") is None
        assert sessions.resolve_session(session, "") is None
        # Un usuario desactivado ya no tiene sesión que valga.
        session.get(ConsultaUser, uid).active = False
        session.commit()
        assert sessions.resolve_session(session, token) is None


def test_una_sesion_vencida_o_pasada_del_tope_absoluto_no_vale(db):
    uid = _usuario(db)
    token, _ = _crear(db, uid)

    with db() as session:
        assert (
            sessions.resolve_session(
                session, token, now=_now() + timedelta(hours=settings.session_hours + 1)
            )
            is None
        )
    with db() as session:
        # Con uso constante la vigencia se desliza, pero nunca pasa de SESSION_MAX_DAYS desde que se creó.
        ahora = _now()
        for dia in range(1, settings.session_max_days + 2):
            info = sessions.resolve_session(
                session, token, now=ahora + timedelta(days=dia, minutes=dia)
            )
            if info is None:
                break
        assert info is None
        assert dia <= settings.session_max_days + 1


def test_la_vigencia_se_desliza_y_la_renovacion_se_escribe_como_maximo_una_vez_por_minuto(db):
    uid = _usuario(db)
    token, sid = _crear(db, uid)
    base = _now()

    with db() as session:
        creada = session.get(ConsultaSession, sid)
        original = creada.expires_at
        sessions.resolve_session(session, token, now=base + timedelta(seconds=20))
        session.expire_all()
        assert (
            session.get(ConsultaSession, sid).expires_at == original
        )  # menos de un minuto: no escribe

        sessions.resolve_session(session, token, now=base + timedelta(hours=2))
        session.expire_all()
        renovada = session.get(ConsultaSession, sid)
        assert renovada.expires_at > original
        assert renovada.last_seen_at == base + timedelta(hours=2)


def test_close_session_borra_esa_fila_y_close_user_sessions_todas_o_todas_menos_una(db):
    uid = _usuario(db)
    otro = _usuario(db, "beto")
    t1, _ = _crear(db, uid)
    t2, s2 = _crear(db, uid)
    t3, _ = _crear(db, otro)

    with db() as session:
        sessions.close_session(session, t1)
        assert sessions.resolve_session(session, t1) is None
        assert sessions.resolve_session(session, t2) is not None
        sessions.close_user_sessions(session, uid, except_id=s2)
        assert sessions.resolve_session(session, t2) is not None
        sessions.close_user_sessions(session, uid)
        assert sessions.resolve_session(session, t2) is None
        assert sessions.resolve_session(session, t3) is not None  # la de otro usuario no se toca


def test_purge_expired_sessions_borra_solo_las_vencidas(db):
    uid = _usuario(db)
    vigente, _ = _crear(db, uid)
    _, sid = _crear(db, uid)
    with db() as session:
        session.get(ConsultaSession, sid).expires_at = _now() - timedelta(minutes=1)
        session.commit()
        assert sessions.purge_expired_sessions(session) == 1
        assert session.query(ConsultaSession).count() == 1
        assert sessions.resolve_session(session, vigente) is not None


# --- Dependencias de la API ---------------------------------------------------------------------------------------

_ruta = APIRouter()


@_ruta.get("/_prueba/opcional")
def _opcional(user=Depends(optional_user)):
    return {"user": user.username if user else None}


@_ruta.get("/_prueba/requerida")
def _requerida(user=Depends(require_user)):
    return {"user": user.username}


@pytest.fixture
def cliente(db):
    app.include_router(_ruta)
    yield TestClient(app)
    app.router.routes[:] = [
        r for r in app.router.routes if not getattr(r, "path", "").startswith("/_prueba")
    ]


def test_optional_user_devuelve_none_sin_encabezado_y_el_usuario_con_sesion_valida(cliente, db):
    token, _ = _crear(db, _usuario(db))

    assert cliente.get("/_prueba/opcional").json() == {"user": None}
    assert cliente.get("/_prueba/opcional", headers={"X-Session-Token": token}).json() == {
        "user": "ana"
    }


def test_un_token_invalido_es_401_session_invalid_incluso_en_la_dependencia_opcional(cliente):
    for ruta in ("/_prueba/opcional", "/_prueba/requerida"):
        respuesta = cliente.get(ruta, headers={"X-Session-Token": "mias_malo"})
        assert respuesta.status_code == 401
        assert respuesta.json()["code"] == "session_invalid"


def test_require_user_sin_encabezado_tambien_es_session_invalid(cliente):
    respuesta = cliente.get("/_prueba/requerida")

    assert respuesta.status_code == 401 and respuesta.json()["code"] == "session_invalid"


def test_los_errores_de_sesion_traen_su_codigo_y_el_de_demasiados_intentos_su_espera():
    from mia.access import errors

    assert errors.session_invalid().code == "session_invalid"
    assert (
        errors.login_required().code == "login_required"
        and errors.login_required().status_code == 401
    )
    assert errors.invalid_credentials().detail == "Usuario o contraseña incorrectos."
    espera = errors.too_many_attempts(900)
    assert espera.status_code == 429 and espera.code == "too_many_attempts"
    assert espera.headers["Retry-After"] == "900" and "15 minutos" in espera.detail


def test_cors_permite_el_encabezado_de_sesion():
    from mia.api.main import CORS_ALLOW_HEADERS

    assert "X-Session-Token" in CORS_ALLOW_HEADERS and "X-Artifact-Key" in CORS_ALLOW_HEADERS
