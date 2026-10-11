"""Cada código de error de acceso, sobre rutas reales de administración (specs/004-acceso-panel-tec, US2)."""

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from mia.access.admins import add_admin, deactivate_admin
from mia.api.main import app
from mia.api.security import get_key_source
from mia.config import settings

CORREO = "coord@itcr.ac.cr"

# Rutas de administración de distintas familias: todas deben comportarse igual ante cada rechazo.
RUTAS = [
    ("get", "/inventory", None),
    ("post", "/domains", {"unit_id": "x", "name": "N"}),
    ("get", "/artifacts", None),
    ("get", "/usage", None),
]


def llamar(client, ruta, headers=None):
    metodo, url, cuerpo = ruta
    return getattr(client, metodo)(url, headers=headers or {}, **({"json": cuerpo} if cuerpo else {}))


@pytest.fixture
def listo(client, units, make_admin):
    make_admin(CORREO, units=["Computación"])


@pytest.mark.parametrize("ruta", RUTAS)
def test_sin_credencial_es_401(client, listo, ruta):
    response = llamar(client, ruta)
    assert response.status_code == 401 and response.json()["code"] == "unauthenticated"


@pytest.mark.parametrize("ruta", RUTAS)
def test_token_vencido_es_401(client, listo, as_user, ruta):
    response = llamar(client, ruta, as_user(CORREO, exp=1, iat=0))
    assert response.status_code == 401 and response.json()["code"] == "token_expired"


@pytest.mark.parametrize(
    "cambios",
    [
        {"tid": "otro-tenant"},
        {"iss": "https://login.microsoftonline.com/otro-tenant/v2.0"},
        {"aud": "otra-aplicacion"},
    ],
)
def test_tenant_emisor_o_audiencia_ajenos_son_401(client, listo, as_user, cambios):
    response = client.get("/inventory", headers=as_user(CORREO, **cambios))
    assert response.status_code == 401 and response.json()["code"] == "invalid_token"


def test_firmado_con_otra_clave_es_401(client, listo, token_factory, key_source_override):
    otra = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    headers = {"Authorization": f"Bearer {token_factory(CORREO, signing_key=otra)}"}
    response = client.get("/inventory", headers=headers)
    assert response.status_code == 401 and response.json()["code"] == "invalid_token"


@pytest.mark.parametrize("ruta", RUTAS)
def test_sin_segundo_factor_es_403(client, listo, as_user, ruta):
    response = llamar(client, ruta, as_user(CORREO, amr=["pwd"]))
    assert response.status_code == 403 and response.json()["code"] == "mfa_required"


def test_sin_exigir_segundo_factor_pasa(client, listo, as_user, monkeypatch):
    monkeypatch.setattr(settings, "entra_require_mfa", False)
    assert client.get("/inventory", headers=as_user(CORREO, amr=["pwd"])).status_code == 200


@pytest.mark.parametrize("ruta", RUTAS)
def test_correo_fuera_de_la_lista_es_403(client, listo, as_user, ruta):
    response = llamar(client, ruta, as_user("otra.persona@itcr.ac.cr"))
    assert response.status_code == 403 and response.json()["code"] == "not_authorized"
    assert "no está autorizada" in response.json()["detail"]


def test_desactivar_rige_desde_la_siguiente_peticion_con_el_mismo_token(client, listo, as_user, db):
    headers = as_user(CORREO)
    assert client.get("/inventory", headers=headers).status_code == 200
    with db() as session:
        deactivate_admin(session, CORREO)
    response = client.get("/inventory", headers=headers)
    assert response.status_code == 403 and response.json()["code"] == "not_authorized"


def test_cambiar_el_alcance_rige_desde_la_siguiente_peticion(client, listo, units, as_user, db):
    headers = as_user(CORREO)
    assert [u["name"] for u in client.get("/inventory", headers=headers).json()["units"]] == ["Computación"]
    with db() as session:
        add_admin(session, CORREO, is_global=False, unit_names=["Administración de Empresas"])
    assert [u["name"] for u in client.get("/inventory", headers=headers).json()["units"]] == [
        "Administración de Empresas"
    ]


def test_sin_client_id_responde_503_y_la_clave_de_automatizacion_sigue(client, listo, as_user, admin, monkeypatch):
    headers = as_user(CORREO)
    monkeypatch.setattr(settings, "entra_client_id", "")
    response = client.get("/inventory", headers=headers)
    assert response.status_code == 503 and response.json()["code"] == "login_not_configured"
    assert client.get("/inventory", headers=admin).status_code == 200


def test_sin_claves_de_microsoft_responde_503(client, listo, token_factory, entra_config, db):
    class SinRed:
        def get_key(self, kid):
            from mia.access.errors import identity_unavailable

            raise identity_unavailable()

    app.dependency_overrides[get_key_source] = lambda: SinRed()
    try:
        headers = {"Authorization": f"Bearer {token_factory(CORREO)}"}
        response = client.get("/inventory", headers=headers)
    finally:
        app.dependency_overrides.pop(get_key_source, None)
    assert response.status_code == 503 and response.json()["code"] == "identity_unavailable"


def test_el_cuerpo_trae_detail_en_espanol_y_code(client, listo):
    body = client.get("/inventory").json()
    assert set(body) == {"detail", "code"} and body["detail"]
