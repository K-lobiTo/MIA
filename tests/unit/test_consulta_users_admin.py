"""Administración de usuarios de la Consulta (feature 015, US1): contracts/usuarios-admin-api.md."""

import json
import uuid
from datetime import timedelta

import pytest

from mia.chat import passwords, sessions
from mia.chat.throttle import login_throttle
from mia.storage.models import ConsultaSession, ConsultaUser, Conversation, _now

COORD = "coord.comp@itcr.ac.cr"
OPERADOR = "operador@itcr.ac.cr"


@pytest.fixture
def mundo(db, units, make_admin):
    make_admin(COORD, units=["Computación"])
    make_admin(OPERADOR, global_=True)
    return {"units": units}


def _lineas(capsys):
    salida = [
        json.loads(linea) for linea in capsys.readouterr().out.splitlines() if linea.startswith("{")
    ]
    return salida


def _crear(client, headers, nombre="ana.perez", unit_id=None, password=None):
    cuerpo = {"username": nombre, "unit_id": unit_id}
    if password is not None:
        cuerpo["password"] = password
    return client.post("/consulta-users", json=cuerpo, headers=headers)


def _filas(db):
    with db() as session:
        return session.query(ConsultaUser).all()


def test_crear_un_usuario_devuelve_la_contrasena_una_sola_vez_y_guarda_solo_su_hash(
    client, db, mundo, admin
):
    respuesta = _crear(client, admin, "Ana.Perez", mundo["units"].comp)

    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert cuerpo["username"] == "ana.perez" and cuerpo["active"] is True
    assert cuerpo["unit"]["id"] == mundo["units"].comp
    assert len(cuerpo["password"]) == 16  # generada
    assert cuerpo["conversation_count"] == 0 and cuerpo["last_activity_at"] is None
    [fila] = _filas(db)
    assert fila.password_hash.startswith("scrypt$") and cuerpo["password"] not in fila.password_hash
    assert passwords.verify_password(cuerpo["password"], fila.password_hash)
    # El listado nunca trae la contraseña ni su hash.
    listado = client.get("/consulta-users", headers=admin).json()["users"]
    assert [u["username"] for u in listado] == ["ana.perez"]
    assert "password" not in listado[0] and "password_hash" not in listado[0]
    assert "scrypt" not in json.dumps(listado)


def test_una_contrasena_dada_se_usa_tal_cual(client, db, mundo, admin):
    respuesta = _crear(client, admin, "beto", mundo["units"].comp, password="una-clave-muy-larga")

    assert respuesta.json()["password"] == "una-clave-muy-larga"
    assert passwords.verify_password("una-clave-muy-larga", _filas(db)[0].password_hash)


def test_un_nombre_repetido_sin_distinguir_mayusculas_es_409(client, mundo, admin):
    _crear(client, admin, "ana.perez", mundo["units"].comp)

    respuesta = _crear(client, admin, "ANA.PEREZ", mundo["units"].comp)

    assert respuesta.status_code == 409
    assert respuesta.json()["detail"] == "Ya existe un usuario llamado 'ana.perez'."


@pytest.mark.parametrize("nombre", ["", "ab", "x" * 41, "ana perez", "ana@itcr.ac.cr", "año"])
def test_un_nombre_invalido_es_422(client, mundo, admin, nombre):
    assert _crear(client, admin, nombre, mundo["units"].comp).status_code == 422


def test_una_contrasena_corta_es_422_al_crear_y_al_restablecer(client, mundo, admin):
    assert _crear(client, admin, "ana", mundo["units"].comp, password="corta").status_code == 422
    uid = _crear(client, admin, "ana", mundo["units"].comp).json()["id"]
    respuesta = client.post(
        f"/consulta-users/{uid}/reset-password", json={"password": "corta"}, headers=admin
    )
    assert respuesta.status_code == 422


def test_desactivar_y_reactivar_cambia_el_estado_y_desactivar_cierra_las_sesiones(
    client, db, mundo, admin, capsys
):
    uid = _crear(client, admin, "ana", mundo["units"].comp).json()["id"]
    with db() as session:
        sessions.create_session(session, session.get(ConsultaUser, uid))
        sessions.create_session(session, session.get(ConsultaUser, uid))
    capsys.readouterr()

    apagado = client.patch(f"/consulta-users/{uid}", json={"active": False}, headers=admin)

    assert apagado.status_code == 200 and apagado.json()["active"] is False
    with db() as session:
        assert session.query(ConsultaSession).count() == 0
    client.patch(f"/consulta-users/{uid}", json={"active": False}, headers=admin)  # sin cambio
    prendido = client.patch(f"/consulta-users/{uid}", json={"active": True}, headers=admin)
    assert prendido.json()["active"] is True
    lineas = [x for x in _lineas(capsys) if x["action"] == "consulta_user.update"]
    assert [x["detail"] for x in lineas] == ["ana: activo false", "ana: activo true"]


def test_restablecer_devuelve_una_contrasena_nueva_una_vez_e_invalida_la_anterior_y_las_sesiones(
    client, db, mundo, admin
):
    creado = _crear(client, admin, "ana", mundo["units"].comp, password="la-clave-original").json()
    with db() as session:
        sessions.create_session(session, session.get(ConsultaUser, creado["id"]))

    nueva = client.post(f"/consulta-users/{creado['id']}/reset-password", json={}, headers=admin)

    assert nueva.status_code == 200 and len(nueva.json()["password"]) == 16
    with db() as session:
        fila = session.get(ConsultaUser, creado["id"])
        assert not passwords.verify_password("la-clave-original", fila.password_hash)
        assert passwords.verify_password(nueva.json()["password"], fila.password_hash)
        assert session.query(ConsultaSession).count() == 0


def test_alcance_la_cuenta_global_ve_todo_y_la_de_programa_solo_lo_suyo(
    client, mundo, admin, as_user
):
    units = mundo["units"]
    ana = _crear(client, admin, "ana", units.comp).json()
    beto = _crear(client, admin, "beto", units.adm).json()
    sin_programa = _crear(client, admin, "global.user", None).json()

    nombres = lambda h: sorted(
        u["username"] for u in client.get("/consulta-users", headers=h).json()["users"]
    )
    assert nombres(admin) == ["ana", "beto", "global.user"]
    assert nombres(as_user(OPERADOR)) == ["ana", "beto", "global.user"]
    assert nombres(as_user(COORD)) == ["ana"]
    coord = as_user(COORD)
    assert (
        client.patch(
            f"/consulta-users/{ana['id']}", json={"active": False}, headers=coord
        ).status_code
        == 200
    )
    for ajeno in (beto["id"], sin_programa["id"]):
        assert (
            client.patch(
                f"/consulta-users/{ajeno}", json={"active": False}, headers=coord
            ).status_code
            == 404
        )
        assert (
            client.post(
                f"/consulta-users/{ajeno}/reset-password", json={}, headers=coord
            ).status_code
            == 404
        )
    # Crear: solo en sus programas y nunca sin programa.
    assert _crear(client, coord, "nuevo", units.comp).status_code == 201
    assert _crear(client, coord, "ajeno", units.adm).status_code == 403
    sin = _crear(client, coord, "huerfano", None)
    assert sin.status_code == 403 and sin.json()["code"] == "global_only"


def test_sin_credenciales_de_administracion_es_401(client, mundo):
    assert client.get("/consulta-users").status_code == 401
    assert client.post("/consulta-users", json={"username": "ana"}).status_code == 401


def test_un_usuario_inexistente_es_404(client, mundo, admin):
    id_falso = str(uuid.uuid4())

    assert (
        client.patch(
            f"/consulta-users/{id_falso}", json={"active": False}, headers=admin
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/consulta-users/{id_falso}/reset-password", json={}, headers=admin
        ).status_code
        == 404
    )


def test_las_tres_acciones_dejan_su_linea_de_registro_sin_contrasenas(client, mundo, admin, capsys):
    creado = _crear(
        client, admin, "ana", mundo["units"].comp, password="clave-que-no-debe-salir"
    ).json()
    client.patch(f"/consulta-users/{creado['id']}", json={"active": False}, headers=admin)
    nueva = client.post(
        f"/consulta-users/{creado['id']}/reset-password", json={}, headers=admin
    ).json()["password"]

    crudo = capsys.readouterr().out
    lineas = [json.loads(x) for x in crudo.splitlines() if x.startswith("{")]
    por_accion = {x["action"]: x for x in lineas if x["action"].startswith("consulta_user.")}
    assert set(por_accion) == {
        "consulta_user.create",
        "consulta_user.update",
        "consulta_user.reset_password",
    }
    assert por_accion["consulta_user.create"]["target"] == creado["id"]
    assert por_accion["consulta_user.create"]["detail"].startswith("ana -> ")
    assert por_accion["consulta_user.reset_password"]["detail"] == "ana"
    assert "clave-que-no-debe-salir" not in crudo and nueva not in crudo and "scrypt" not in crudo


def test_el_listado_trae_solo_cantidad_y_ultima_actividad_de_las_conversaciones(
    client, db, mundo, admin, as_user
):
    creado = _crear(client, admin, "ana", mundo["units"].comp).json()
    ahora = _now()
    with db() as session:
        for i, titulo in enumerate(["secreto-conv-77 primera", "secreto-conv-77 segunda"]):
            session.add(
                Conversation(
                    id=str(uuid.uuid4()),
                    user_id=creado["id"],
                    title=titulo,
                    created_at=ahora - timedelta(days=3),
                    updated_at=ahora - timedelta(days=2 - i),
                )
            )
        session.commit()

    for cabecera in (admin, as_user(OPERADOR), as_user(COORD)):
        cuerpo = client.get("/consulta-users", headers=cabecera).text
        assert "secreto-conv-77" not in cuerpo
    [usuario] = client.get("/consulta-users", headers=admin).json()["users"]
    assert usuario["conversation_count"] == 2
    assert usuario["last_activity_at"].startswith((ahora - timedelta(days=1)).strftime("%Y-%m-%d"))


def test_restablecer_la_contrasena_libera_el_bloqueo_por_intentos_fallidos(client, mundo, admin):
    creado = _crear(client, admin, "ana", mundo["units"].comp, password="la-clave-original").json()
    login_throttle.reset()
    for _ in range(5):
        login_throttle.fail("ana", "origen-1")
    assert login_throttle.check("ana", "origen-2") > 0

    nueva = client.post(f"/consulta-users/{creado['id']}/reset-password", json={}, headers=admin)

    assert nueva.status_code == 200
    assert login_throttle.check("ana", "origen-2") == 0
    login_throttle.reset()
