"""Límite de intentos fallidos de inicio de sesión (feature 015, research R3 y R4)."""

from types import SimpleNamespace

import pytest

from mia.chat.throttle import LoginThrottle, client_origin
from mia.config import settings


class Reloj:
    def __init__(self):
        self.ahora = 1_000.0

    def __call__(self):
        return self.ahora


@pytest.fixture
def reloj():
    return Reloj()


@pytest.fixture
def limite(reloj):
    return LoginThrottle(clock=reloj)


def test_hasta_el_maximo_de_fallos_no_bloquea_y_el_siguiente_intento_si(limite, reloj):
    for _ in range(settings.login_max_attempts):
        assert limite.check("ana", "1.1.1.1") == 0
        limite.fail("ana", "1.1.1.1")

    espera = limite.check("ana", "1.1.1.1")
    assert 0 < espera <= settings.login_lock_minutes * 60


def test_el_bloqueo_se_libera_pasados_los_minutos_configurados(limite, reloj):
    for _ in range(settings.login_max_attempts):
        limite.fail("ana", "1.1.1.1")
    assert limite.check("ana", "1.1.1.1") > 0

    reloj.ahora += settings.login_lock_minutes * 60 + 1

    assert limite.check("ana", "1.1.1.1") == 0


def test_un_inicio_correcto_limpia_el_contador_del_usuario(limite):
    for _ in range(settings.login_max_attempts - 1):
        limite.fail("ana", "1.1.1.1")
    limite.clear_user("ana")
    limite.fail("ana", "1.1.1.1")

    assert limite.check("ana", "1.1.1.1") == 0


def test_otro_usuario_no_se_bloquea_por_los_fallos_de_ana(limite):
    for _ in range(settings.login_max_attempts):
        limite.fail("ana", "1.1.1.1")

    assert limite.check("beto", "2.2.2.2") == 0


def test_el_origen_tiene_su_propio_tope_aunque_cambie_el_usuario(limite):
    for i in range(settings.login_max_attempts_per_origin):
        assert limite.check(f"usuario{i}", "9.9.9.9") == 0
        limite.fail(f"usuario{i}", "9.9.9.9")

    assert limite.check("otro-usuario-mas", "9.9.9.9") > 0
    assert limite.check("otro-usuario-mas", "8.8.8.8") == 0


def test_los_intentos_contra_usuarios_inexistentes_cuentan_igual(limite):
    for _ in range(settings.login_max_attempts):
        limite.fail("no-existe", "1.1.1.1")

    assert limite.check("no-existe", "1.1.1.1") > 0


def test_el_estado_esta_acotado(reloj):
    pequeno = LoginThrottle(clock=reloj, max_entries=50)
    for i in range(500):
        pequeno.fail(f"usuario{i}", f"10.0.{i // 250}.{i % 250}")

    assert pequeno.size <= 100  # usuarios y orígenes, 50 cada uno como máximo


def _peticion(host="3.3.3.3", forwarded=None):
    headers = {} if forwarded is None else {"x-forwarded-for": forwarded}
    return SimpleNamespace(client=SimpleNamespace(host=host), headers=headers)


def test_el_origen_es_la_direccion_directa_por_defecto(monkeypatch):
    monkeypatch.setattr(settings, "trust_forwarded_for", "off")

    assert client_origin(_peticion(forwarded="7.7.7.7, 8.8.8.8")) == "3.3.3.3"


def test_con_el_proxy_de_confianza_se_usa_el_ultimo_valor_y_no_el_primero(monkeypatch):
    monkeypatch.setattr(settings, "trust_forwarded_for", "on")

    assert client_origin(_peticion(forwarded="1.2.3.4, 7.7.7.7, 8.8.8.8")) == "8.8.8.8"
    assert client_origin(_peticion(forwarded="8.8.8.8")) == "8.8.8.8"
    assert client_origin(_peticion()) == "3.3.3.3"  # sin el encabezado, la dirección directa
    sin_cliente = SimpleNamespace(client=None, headers={})
    assert client_origin(sin_cliente) == "desconocido"
