"""Validación del token de identidad de Microsoft con tokens firmados por una clave local."""

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from mia.access.entra import MicrosoftKeys, validate_id_token
from mia.access.errors import AuthError
from mia.config import settings


def code_of(token, key_source):
    with pytest.raises(AuthError) as error:
        validate_id_token(token, key_source)
    return error.value.status_code, error.value.code


def test_token_valido_devuelve_el_correo_en_minusculas(token_factory, key_source):
    identity = validate_id_token(token_factory("Persona@ITCR.ac.cr"), key_source)
    assert identity.email == "persona@itcr.ac.cr" and identity.mfa


def test_usa_preferred_username_si_no_hay_email(token_factory, key_source):
    token = token_factory(email=None, preferred_username="Otra@itcr.ac.cr")
    assert validate_id_token(token, key_source).email == "otra@itcr.ac.cr"


def test_sin_correo_es_invalido(token_factory, key_source):
    assert code_of(token_factory(email=None), key_source) == (401, "invalid_token")
    assert code_of(token_factory(email="sin-arroba"), key_source) == (401, "invalid_token")


def test_token_vencido(token_factory, key_source):
    assert code_of(token_factory(exp=1, iat=0), key_source) == (401, "token_expired")


@pytest.mark.parametrize(
    "cambios",
    [
        {"iss": "https://login.microsoftonline.com/otro-tenant/v2.0"},
        {"aud": "otra-aplicacion"},
        {"tid": "otro-tenant"},
        {"tid": None},
        {"exp": None},
        {"iat": None},
    ],
)
def test_emisor_audiencia_o_tenant_ajenos_son_invalidos(token_factory, key_source, cambios):
    assert code_of(token_factory(**cambios), key_source) == (401, "invalid_token")


def test_firmado_con_otra_clave(token_factory, key_source):
    otra = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    assert code_of(token_factory(signing_key=otra), key_source) == (401, "invalid_token")


def test_algoritmos_no_admitidos_y_kid_desconocido(token_factory, key_source):
    assert code_of(token_factory(alg="none"), key_source) == (401, "invalid_token")
    assert code_of(token_factory(alg="HS256"), key_source) == (401, "invalid_token")
    assert code_of(token_factory(kid="desconocido"), key_source) == (401, "invalid_token")
    assert code_of(token_factory(kid=None), key_source) == (401, "invalid_token")
    assert code_of("no-es-un-token", key_source) == (401, "invalid_token")


def test_segundo_factor(token_factory, key_source, monkeypatch):
    sin_mfa = token_factory(amr=["pwd"])
    assert code_of(sin_mfa, key_source) == (403, "mfa_required")
    assert code_of(token_factory(amr=None), key_source) == (403, "mfa_required")
    monkeypatch.setattr(settings, "entra_require_mfa", False)
    assert validate_id_token(sin_mfa, key_source).mfa is False


def test_sin_client_id_configurado(token_factory, key_source, monkeypatch):
    token = token_factory()
    monkeypatch.setattr(settings, "entra_client_id", "")
    assert code_of(token, key_source) == (503, "login_not_configured")


def _claves(rsa_key, kid="k1"):
    import json

    from jwt.algorithms import RSAAlgorithm

    jwk = json.loads(RSAAlgorithm.to_jwk(rsa_key.public_key()))
    return [{**jwk, "kid": kid, "kty": "RSA"}]


class Reloj:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def test_las_claves_se_guardan_una_hora(rsa_key):
    reloj, bajadas = Reloj(), []
    keys = MicrosoftKeys(fetch=lambda: bajadas.append(1) or _claves(rsa_key), clock=reloj)
    assert keys.get_key("k1") is not None
    reloj.now += 3000
    assert keys.get_key("k1") is not None
    assert len(bajadas) == 1
    reloj.now += 700  # pasó más de una hora
    assert keys.get_key("k1") is not None
    assert len(bajadas) == 2


def test_kid_desconocido_baja_una_vez_cada_cinco_minutos(rsa_key):
    reloj, bajadas = Reloj(), []
    keys = MicrosoftKeys(fetch=lambda: bajadas.append(1) or _claves(rsa_key), clock=reloj)
    assert keys.get_key("k1") is not None  # primera bajada
    assert keys.get_key("falso") is None  # kid desconocido: nueva bajada
    assert len(bajadas) == 2
    for _ in range(5):
        assert keys.get_key("falso") is None  # dentro de los 5 minutos: no baja
    assert len(bajadas) == 2
    reloj.now += 301
    assert keys.get_key("falso") is None
    assert len(bajadas) == 3


def test_si_la_bajada_falla_usa_las_claves_guardadas(rsa_key):
    reloj, estado = Reloj(), {"falla": False}

    def fetch():
        if estado["falla"]:
            raise RuntimeError("sin red")
        return _claves(rsa_key)

    keys = MicrosoftKeys(fetch=fetch, clock=reloj)
    assert keys.get_key("k1") is not None
    estado["falla"] = True
    reloj.now += 7200
    assert keys.get_key("k1") is not None


def test_sin_claves_y_sin_red_responde_servicio_no_disponible():
    def fetch():
        raise RuntimeError("sin red")

    with pytest.raises(AuthError) as error:
        MicrosoftKeys(fetch=fetch).get_key("k1")
    assert (error.value.status_code, error.value.code) == (503, "identity_unavailable")
