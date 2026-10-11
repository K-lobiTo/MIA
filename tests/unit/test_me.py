"""Credenciales de administración y GET /me: quién es la persona y con qué alcance."""

from mia.config import settings

CORREO = "coord@itcr.ac.cr"


def test_sin_credencial_es_401(client):
    response = client.get("/me")
    assert response.status_code == 401
    assert response.json()["code"] == "unauthenticated"
    assert response.headers["www-authenticate"] == "Bearer"


def test_clave_de_automatizacion_da_alcance_global(client, admin):
    body = client.get("/me", headers=admin).json()
    assert body == {"email": None, "is_global": True, "units": [], "source": "automation"}


def test_clave_incorrecta_o_con_admin_key_vacia_es_401_no_503(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_key", "la-clave")
    assert client.get("/me", headers={"X-Admin-Key": "otra"}).status_code == 401
    monkeypatch.setattr(settings, "admin_key", "")
    response = client.get("/me", headers={"X-Admin-Key": "la-clave"})
    assert response.status_code == 401 and response.json()["code"] == "unauthenticated"


def test_persona_de_una_unidad(client, units, make_admin, as_user):
    make_admin(CORREO, units=["Computación"])
    body = client.get("/me", headers=as_user(CORREO)).json()
    assert body["email"] == CORREO and body["is_global"] is False and body["source"] == "entra"
    assert body["units"] == [{"id": units.comp, "name": "Computación"}]


def test_persona_global(client, make_admin, as_user):
    make_admin("op@itcr.ac.cr", global_=True)
    body = client.get("/me", headers=as_user("OP@itcr.ac.cr")).json()
    assert body["is_global"] is True and body["units"] == []


def test_correo_fuera_de_la_lista_o_desactivado_es_403(client, units, make_admin, as_user, db):
    response = client.get("/me", headers=as_user("nadie@itcr.ac.cr"))
    assert response.status_code == 403 and response.json()["code"] == "not_authorized"

    from mia.access.admins import deactivate_admin

    make_admin(CORREO, units=["Computación"])
    with db() as session:
        deactivate_admin(session, CORREO)
    assert client.get("/me", headers=as_user(CORREO)).json()["code"] == "not_authorized"


def test_si_llegan_ambas_credenciales_gana_el_token(client, units, make_admin, as_user, admin):
    make_admin(CORREO, units=["Computación"])
    body = client.get("/me", headers={**admin, **as_user(CORREO)}).json()
    assert body["source"] == "entra" and body["is_global"] is False
