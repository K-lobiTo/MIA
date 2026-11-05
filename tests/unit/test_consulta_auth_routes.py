"""Inicio y cierre de sesión de la Consulta (feature 015, US2): contracts/auth-api.md. (Las pruebas de acceso del panel, feature 004, están en test_auth_routes.py.)"""

import base64
import hashlib
import logging
import uuid

import pytest

from mia.api.routes import auth as auth_routes
from mia.chat import passwords, sessions
from mia.chat.throttle import LoginThrottle
from mia.config import settings
from mia.storage.models import ConsultaSession, ConsultaUser, _now

CLAVE = "una-clave-larga-123"
MENSAJE = "Usuario o contraseña incorrectos."


class Reloj:
    def __init__(self):
        self.ahora = 1_000.0

    def __call__(self):
        return self.ahora


@pytest.fixture
def reloj(monkeypatch):
    reloj = Reloj()
    monkeypatch.setattr(auth_routes, "login_throttle", LoginThrottle(clock=reloj))
    return reloj


@pytest.fixture
def usuario(db, reloj):
    uid = str(uuid.uuid4())
    with db() as session:
        session.add(
            ConsultaUser(
                id=uid,
                username="ana",
                password_hash=passwords.hash_password(CLAVE),
                active=True,
                created_by="prueba",
            )
        )
        session.commit()
    return uid


def _entrar(client, usuario="ana", clave=CLAVE):
    return client.post("/auth/login", json={"username": usuario, "password": clave})


def test_un_inicio_correcto_devuelve_token_vencimiento_y_usuario_y_actualiza_el_ultimo_acceso(
    client, db, usuario
):
    respuesta = _entrar(client, "  ANA ")

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["token"].startswith("mias_") and cuerpo["user"] == {"username": "ana"}
    assert cuerpo["expires_at"].endswith("Z")
    with db() as session:
        assert session.get(ConsultaUser, usuario).last_login_at is not None
        assert session.query(ConsultaSession).count() == 1


def test_inexistente_desactivado_y_clave_equivocada_dan_el_mismo_401(client, db, usuario):
    with db() as session:
        session.add(
            ConsultaUser(
                id=str(uuid.uuid4()),
                username="baja",
                password_hash=passwords.hash_password(CLAVE),
                active=False,
                created_by="prueba",
            )
        )
        session.commit()

    casos = [
        _entrar(client, "no.existe", CLAVE),
        _entrar(client, "baja", CLAVE),  # desactivado, con la contraseña correcta
        _entrar(client, "ana", "clave-equivocada-1"),
    ]

    cuerpos = [c.json() for c in casos]
    assert all(c.status_code == 401 for c in casos)
    assert cuerpos[0] == cuerpos[1] == cuerpos[2]
    assert cuerpos[0] == {"detail": MENSAJE, "code": "invalid_credentials"}


def test_el_usuario_inexistente_hace_la_misma_verificacion_que_uno_real(
    client, usuario, monkeypatch
):
    llamadas = []
    original = passwords.verify_password
    monkeypatch.setattr(
        passwords,
        "verify_password",
        lambda clave, guardado: llamadas.append(guardado) or original(clave, guardado),
    )

    _entrar(client, "no.existe")
    _entrar(client, "ana", "clave-equivocada-1")

    assert len(llamadas) == 2
    assert llamadas[0] == passwords.DUMMY_HASH and llamadas[1] != passwords.DUMMY_HASH


def test_tras_el_maximo_de_fallos_responde_429_aunque_la_clave_sea_correcta(client, usuario, reloj):
    for _ in range(settings.login_max_attempts):
        assert _entrar(client, "ana", "clave-equivocada-1").status_code == 401

    bloqueado = _entrar(client, "ana", CLAVE)

    assert bloqueado.status_code == 429
    assert bloqueado.json()["code"] == "too_many_attempts"
    assert int(bloqueado.headers["Retry-After"]) > 0
    assert "Espera" in bloqueado.json()["detail"]
    # Otro usuario no se bloquea por los fallos de ana.
    assert _entrar(client, "otra.persona").status_code == 401


def test_pasado_el_plazo_se_puede_volver_a_entrar(client, usuario, reloj):
    for _ in range(settings.login_max_attempts):
        _entrar(client, "ana", "clave-equivocada-1")
    assert _entrar(client, "ana", CLAVE).status_code == 429

    reloj.ahora += settings.login_lock_minutes * 60 + 1

    assert _entrar(client, "ana", CLAVE).status_code == 200


def test_el_origen_se_bloquea_aunque_cada_intento_sea_de_un_usuario_distinto(
    client, usuario, monkeypatch
):
    monkeypatch.setattr(settings, "login_max_attempts_per_origin", 6)
    for i in range(6):
        assert _entrar(client, f"usuario{i}").status_code == 401

    assert _entrar(client, "usuario-nuevo").status_code == 429


def test_cerrar_sesion_invalida_el_token_y_cerrarla_de_nuevo_o_con_uno_malo_tambien_es_204(
    client, usuario
):
    token = _entrar(client).json()["token"]
    cabecera = {"X-Session-Token": token}
    assert client.get("/auth/me", headers=cabecera).status_code == 200

    assert client.post("/auth/logout", headers=cabecera).status_code == 204
    assert client.get("/auth/me", headers=cabecera).status_code == 401
    assert client.post("/auth/logout", headers=cabecera).status_code == 204
    assert client.post("/auth/logout", headers={"X-Session-Token": "mias_malo"}).status_code == 204
    assert client.post("/auth/logout").status_code == 204


def test_me_responde_con_sesion_valida_y_session_invalid_sin_ella_vencida_o_de_un_usuario_desactivado(
    client, db, usuario
):
    token = _entrar(client).json()["token"]
    cabecera = {"X-Session-Token": token}

    me = client.get("/auth/me", headers=cabecera)
    assert (
        me.status_code == 200
        and me.json()["username"] == "ana"
        and me.json()["expires_at"].endswith("Z")
    )
    sin = client.get("/auth/me")
    assert sin.status_code == 401 and sin.json()["code"] == "session_invalid"
    with db() as session:
        fila = session.query(ConsultaSession).one()
        fila.expires_at = _now()
        session.commit()
    assert client.get("/auth/me", headers=cabecera).json()["code"] == "session_invalid"

    nuevo = _entrar(client).json()["token"]
    with db() as session:
        session.get(ConsultaUser, usuario).active = False
        session.commit()
    assert (
        client.get("/auth/me", headers={"X-Session-Token": nuevo}).json()["code"]
        == "session_invalid"
    )


def test_cambiar_la_contrasena_cierra_las_demas_sesiones_y_deja_la_actual(client, db, usuario):
    primera = _entrar(client).json()["token"]
    segunda = _entrar(client).json()["token"]

    cambio = client.post(
        "/auth/password",
        json={"current_password": CLAVE, "new_password": "otra-clave-nueva-456"},
        headers={"X-Session-Token": primera},
    )

    assert cambio.status_code == 204
    assert client.get("/auth/me", headers={"X-Session-Token": primera}).status_code == 200
    assert client.get("/auth/me", headers={"X-Session-Token": segunda}).status_code == 401
    assert _entrar(client, "ana", CLAVE).status_code == 401
    assert _entrar(client, "ana", "otra-clave-nueva-456").status_code == 200


def test_cambiar_la_contrasena_valida_la_actual_y_la_nueva(client, usuario):
    token = _entrar(client).json()["token"]
    cabecera = {"X-Session-Token": token}

    mala = client.post(
        "/auth/password",
        json={"current_password": "equivocada-123", "new_password": "otra-clave-nueva-456"},
        headers=cabecera,
    )
    corta = client.post(
        "/auth/password",
        json={"current_password": CLAVE, "new_password": "corta"},
        headers=cabecera,
    )
    igual = client.post(
        "/auth/password", json={"current_password": CLAVE, "new_password": CLAVE}, headers=cabecera
    )
    sin_sesion = client.post(
        "/auth/password", json={"current_password": CLAVE, "new_password": "otra-clave-nueva-456"}
    )

    assert mala.status_code == 401 and mala.json()["code"] == "invalid_credentials"
    assert corta.status_code == 422 and igual.status_code == 422
    assert sin_sesion.status_code == 401 and sin_sesion.json()["code"] == "session_invalid"


def test_la_contrasena_actual_equivocada_cuenta_como_intento_fallido_del_usuario(client, usuario):
    token = _entrar(client).json()["token"]
    cabecera = {"X-Session-Token": token}
    for _ in range(settings.login_max_attempts):
        client.post(
            "/auth/password",
            json={"current_password": "equivocada-123", "new_password": "otra-clave-nueva-456"},
            headers=cabecera,
        )

    assert _entrar(client, "ana", CLAVE).status_code == 429


def test_un_cuerpo_incompleto_es_422(client, usuario):
    assert client.post("/auth/login", json={"username": "ana"}).status_code == 422
    assert client.post("/auth/login", json={"username": "", "password": ""}).status_code == 422


def test_un_hash_con_parametros_viejos_se_vuelve_a_guardar_con_los_vigentes(client, db, usuario):
    sal = b"0123456789abcdef"
    crudo = hashlib.scrypt(CLAVE.encode(), salt=sal, n=2**13, r=8, p=1, dklen=32)
    viejo = f"scrypt$8192$8$1${base64.b64encode(sal).decode()}${base64.b64encode(crudo).decode()}"
    with db() as session:
        session.get(ConsultaUser, usuario).password_hash = viejo
        session.commit()

    assert _entrar(client).status_code == 200

    with db() as session:
        nuevo = session.get(ConsultaUser, usuario).password_hash
    assert nuevo != viejo and not passwords.needs_rehash(nuevo)
    assert passwords.verify_password(CLAVE, nuevo)


def test_ni_el_token_ni_la_contrasena_aparecen_en_el_registro(client, usuario, caplog, capsys):
    with caplog.at_level(logging.DEBUG):
        token = _entrar(client).json()["token"]
        _entrar(client, "ana", "clave-equivocada-secreta-9")
        client.post(
            "/auth/password",
            json={"current_password": CLAVE, "new_password": "clave-nueva-secreta-77"},
            headers={"X-Session-Token": token},
        )
        client.post("/auth/logout", headers={"X-Session-Token": token})

    salida = caplog.text + capsys.readouterr().out
    for secreto in (token, CLAVE, "clave-equivocada-secreta-9", "clave-nueva-secreta-77"):
        assert secreto not in salida
    assert "resultado=ok" in caplog.text and "resultado=fallo" in caplog.text


def test_el_registro_no_copia_un_nombre_que_no_parece_un_usuario(client, usuario, caplog):
    with caplog.at_level(logging.DEBUG):
        _entrar(client, "mi contraseña es hunter2 por si acaso")

    assert "hunter2" not in caplog.text


def test_create_session_ya_no_deja_el_token_en_claro_en_la_base(client, db, usuario):
    token = _entrar(client).json()["token"]

    with db() as session:
        fila = session.query(ConsultaSession).one()
        assert token not in (fila.token_hash, fila.id, fila.user_id)
        assert sessions.resolve_session(session, token) is not None
