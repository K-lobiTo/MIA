"""Direcciones de la lectura de una página web (feature 022): validación, clave de comparación y red interna."""

import socket

import pytest

from mia.ingestion.web import urls
from mia.ingestion.web.errors import WebRejection
from tests.unit.web_de_prueba import resolver_de


def _codigo(funcion, *args, **kwargs):
    with pytest.raises(WebRejection) as error:
        funcion(*args, **kwargs)
    return error.value.code


def test_normalizar_entrada_recorta_y_antepone_https_a_lo_que_parece_un_sitio():
    assert urls.normalizar_entrada("  https://ejemplo.test/a  ") == "https://ejemplo.test/a"
    assert urls.normalizar_entrada("ejemplo.test/programa") == "https://ejemplo.test/programa"
    assert urls.normalizar_entrada("http://ejemplo.test/a?x=1") == "http://ejemplo.test/a?x=1"
    assert urls.normalizar_entrada("ejemplo.test:8443/a") == "https://ejemplo.test:8443/a"
    assert urls.normalizar_entrada("HTTPS://Ejemplo.TEST/Ruta") == "https://ejemplo.test/Ruta"


def test_normalizar_entrada_quita_el_fragmento_y_conserva_la_consulta():
    assert urls.normalizar_entrada("https://ejemplo.test/a?utm_source=correo#seccion") == (
        "https://ejemplo.test/a?utm_source=correo"
    )


@pytest.mark.parametrize(
    "texto",
    [
        "",
        "   ",
        "ftp://ejemplo.test/a",
        "file:///etc/passwd",
        "javascript:alert(1)",
        "data:text/html,hola",
        "mailto:a@ejemplo.test",
        "https://usuario:clave@ejemplo.test/",
        "https://usuario@ejemplo.test/",
        "ejemplo",
        "dos palabras.test",
        "https://ejemplo.test:0/",
        "https://ejemplo.test:99999/",
        "https:///sin-sitio",
        "https://ejemplo.test/" + "a" * 2100,
    ],
)
def test_normalizar_entrada_rechaza_lo_que_no_es_una_direccion_web(texto):
    assert _codigo(urls.normalizar_entrada, texto) == "invalid_url"


def test_normalizar_entrada_acepta_nombres_con_tildes_y_ip_literal():
    assert urls.normalizar_entrada("https://ejemplo.test/") == "https://ejemplo.test/"
    assert urls.normalizar_entrada("http://93.184.216.34/a") == "http://93.184.216.34/a"
    assert urls.normalizar_entrada("http://[2606:2800:220:1::1]/a") == "http://[2606:2800:220:1::1]/a"
    assert urls.normalizar_entrada("https://bücher.test/a").startswith("https://xn--bcher-kva.test")


def test_clave_de_comparacion():
    clave = urls.clave_de_comparacion
    assert clave("http://Ejemplo.test/a/") == clave("https://ejemplo.test/a")
    assert clave("https://ejemplo.test/a#x") == clave("https://ejemplo.test/a")
    assert clave("https://ejemplo.test:443/a") == clave("https://ejemplo.test/a")
    assert clave("http://ejemplo.test:80/a") == clave("https://ejemplo.test/a")
    assert clave("http://ejemplo.test:8080/a") != clave("http://ejemplo.test/a")
    assert clave("https://ejemplo.test/a?a=1") != clave("https://ejemplo.test/a")
    assert clave("https://ejemplo.test/a?a=1") == clave("https://ejemplo.test/a/?a=1")
    assert clave("https://www.ejemplo.test/a") != clave("https://ejemplo.test/a")
    assert clave("https://ejemplo.test/") == clave("https://ejemplo.test")
    assert clave("https://ejemplo.test/A") != clave("https://ejemplo.test/a")


@pytest.mark.parametrize(
    "ip",
    [
        "127.0.0.1", "10.0.0.5", "172.16.0.1", "192.168.1.1", "169.254.169.254", "0.0.0.0", "::1", "fe80::1",
        "fc00::1", "::ffff:127.0.0.1", "100.64.0.1", "224.0.0.1", "ff02::1", "192.0.2.1", "64:ff9b::7f00:1",
        "fe80::1%eth0",
    ],
)
def test_exigir_ip_publica_rechaza_las_redes_internas(ip):
    assert _codigo(urls.exigir_ip_publica, [ip]) == "private_address"


@pytest.mark.parametrize("ip", ["93.184.216.34", "2606:2800:220:1::1", "8.8.8.8"])
def test_exigir_ip_publica_acepta_las_publicas(ip):
    urls.exigir_ip_publica([ip])


def test_resolver_publica_devuelve_la_primera_ip_publica():
    resolver = resolver_de({"ejemplo.test": ["93.184.216.34", "93.184.216.35"]})

    assert urls.resolver_publica("ejemplo.test", 443, resolver) == "93.184.216.34"


def test_resolver_publica_rechaza_si_cualquiera_de_las_ip_es_privada():
    resolver = resolver_de({"mixto.test": ["93.184.216.34", "10.0.0.5"], "localhost": ["127.0.0.1"]})

    assert _codigo(urls.resolver_publica, "mixto.test", 443, resolver) == "private_address"
    assert _codigo(urls.resolver_publica, "localhost", 80, resolver) == "private_address"


def test_resolver_publica_traduce_los_errores_de_resolucion():
    assert _codigo(urls.resolver_publica, "no-existe.test", 443, resolver_de({})) == "unreachable"

    def falla(*args, **kwargs):
        raise socket.gaierror(socket.EAI_AGAIN, "temporal")

    assert _codigo(urls.resolver_publica, "ejemplo.test", 443, falla) == "unreachable"
    assert _codigo(urls.resolver_publica, "ejemplo.test", 443, lambda *a, **k: []) == "unreachable"


@pytest.mark.parametrize("nombre", ["2130706433", "0x7f.1", "017700000001"])
def test_las_formas_raras_de_ipv4_acaban_como_red_interna(nombre):
    # getaddrinfo las interpreta como 127.0.0.1; se simula con el mismo resultado.
    resolver = resolver_de({nombre: ["127.0.0.1"]})

    assert _codigo(urls.resolver_publica, nombre, 80, resolver) == "private_address"


def test_direccion_para_auditoria_quita_consulta_fragmento_y_credenciales():
    f = urls.direccion_para_auditoria
    assert f("https://ejemplo.test/a?token=1#x") == "https://ejemplo.test/a"
    assert f("https://usuario:secreto@ejemplo.test:8443/a/b?x=1") == "https://ejemplo.test:8443/a/b"
    assert "secreto" not in f("https://usuario:secreto@ejemplo.test/")
    assert f("  https://ejemplo.test/a  ") == "https://ejemplo.test/a"


@pytest.mark.parametrize("texto", ["", "no es una direccion", "javascript:alert(1)", "ftp://ejemplo.test/a", "https://"])
def test_direccion_para_auditoria_no_copia_lo_que_no_puede_interpretar(texto):
    assert urls.direccion_para_auditoria(texto) == "(dirección no interpretable)"
