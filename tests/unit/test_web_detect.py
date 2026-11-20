"""Clasificación de lo que no se puede leer (feature 022, research R5): sin sesión, anti-bot, sin contenido, errores del sitio."""

import pytest

from mia.config import settings
from mia.ingestion.web.detect import revisar_respuesta, revisar_texto
from mia.ingestion.web.errors import WebRejection
from mia.ingestion.web.extract import extraer
from tests.unit.web_de_prueba import pagina, pagina_leida

URL = "https://ejemplo.test/programa"


def _codigo(funcion, *args):
    with pytest.raises(WebRejection) as error:
        funcion(*args)
    return error.value.code


def _revisar_todo(leida):
    """Lo que hace la ruta: primero la respuesta y luego, ya extraído, el texto."""
    revisar_respuesta(leida)
    revisar_texto(leida, extraer(leida.cuerpo, leida.url_final, leida.codificacion))


def test_una_pagina_normal_pasa():
    _revisar_todo(pagina_leida(pagina("programa.html")))


@pytest.mark.parametrize(
    "leida",
    [
        pagina_leida("x", estado=401),
        pagina_leida("x", estado=403, cabeceras={"www-authenticate": 'Basic realm="intranet"'}),
        pagina_leida("<p>Hola</p>", url="https://ejemplo.test/login?next=/programa"),
        pagina_leida("<p>Hola</p>", url="https://ejemplo.test/cuenta/signin"),
        pagina_leida("<p>Hola</p>", url="https://ejemplo.test/sso/entrar"),
        pagina_leida("<p>Hola</p>", url="https://login.microsoftonline.com/common/oauth2/authorize"),
        pagina_leida("<p>Hola</p>", url="https://accounts.google.com/signin/v2"),
    ],
)
def test_el_inicio_de_sesion_se_reconoce_por_el_estado_o_por_la_redireccion(leida):
    assert _codigo(revisar_respuesta, leida) == "login_required"


def test_un_segmento_de_ruta_parecido_a_un_ingreso_no_cuenta():
    revisar_respuesta(pagina_leida("<p>Hola</p>", url="https://ejemplo.test/authors/lista"))
    revisar_respuesta(pagina_leida("<p>Hola</p>", url="https://ejemplo.test/blog/login-tips"))


@pytest.mark.parametrize("estado", [403, 429, 503])
def test_el_desafio_del_proveedor_es_bot_blocked_con_cualquier_estado(estado):
    por_cabecera = pagina_leida("x", estado=estado, cabeceras={"cf-mitigated": "challenge"})
    por_cuerpo = pagina_leida(pagina("verificacion_antibot.html"), estado=estado)

    assert _codigo(revisar_respuesta, por_cabecera) == "bot_blocked"
    assert _codigo(revisar_respuesta, por_cuerpo) == "bot_blocked"


def test_la_pantalla_de_verificacion_con_codigo_200_es_bot_blocked():
    assert _codigo(_revisar_todo, pagina_leida(pagina("verificacion_antibot.html"))) == "bot_blocked"


def test_una_pagina_legitima_que_menciona_un_captcha_no_se_rechaza():
    texto = "Para proteger el formulario de contacto usamos un captcha sencillo. " + "Contenido útil de la página. " * 30
    _revisar_todo(pagina_leida(f"<html><body><main><p>{texto}</p></main></body></html>"))


def test_un_formulario_de_ingreso_con_codigo_200_es_login_required():
    assert _codigo(_revisar_todo, pagina_leida(pagina("ingreso.html"))) == "login_required"


def test_un_403_sin_ninguna_senal_es_forbidden_y_un_429_rate_limited():
    assert _codigo(revisar_respuesta, pagina_leida("Prohibido", estado=403)) == "forbidden"
    assert _codigo(revisar_respuesta, pagina_leida("Despacio", estado=429)) == "rate_limited"


@pytest.mark.parametrize("estado", [404, 410])
def test_no_encontrada(estado):
    assert _codigo(revisar_respuesta, pagina_leida("No está", estado=estado)) == "not_found"


@pytest.mark.parametrize("estado", [400, 405, 500, 502, 503, 504])
def test_los_demas_errores_son_server_error_con_el_codigo(estado):
    with pytest.raises(WebRejection) as error:
        revisar_respuesta(pagina_leida("Error", estado=estado))

    assert error.value.code == "server_error" and str(estado) in error.value.message


@pytest.mark.parametrize("tipo", ["application/pdf", "image/png", "application/octet-stream", "text/plain", "application/json"])
def test_lo_que_no_es_html_se_rechaza_y_con_un_pdf_se_sugiere_subirlo_como_archivo(tipo):
    with pytest.raises(WebRejection) as error:
        revisar_respuesta(pagina_leida(b"%PDF-1.7", tipo=tipo))

    assert error.value.code == "not_html"
    assert "súbelo como archivo" in error.value.message


@pytest.mark.parametrize("tipo", ["text/html; charset=utf-8", "text/html", "application/xhtml+xml", "TEXT/HTML"])
def test_los_tipos_html_pasan(tipo):
    revisar_respuesta(pagina_leida("<html><body>x</body></html>", tipo=tipo))


def test_sin_tipo_de_contenido_se_decide_por_el_comienzo_del_cuerpo():
    revisar_respuesta(pagina_leida("<!DOCTYPE html><html><body>x</body></html>", tipo=""))
    revisar_respuesta(pagina_leida("  <html><body>x</body></html>", tipo=""))
    assert _codigo(revisar_respuesta, pagina_leida(b"%PDF-1.7 binario", tipo="")) == "not_html"


def test_una_pagina_vacia_por_javascript_es_no_content():
    assert _codigo(_revisar_todo, pagina_leida(pagina("vacia_js.html"))) == "no_content"


def test_el_minimo_de_texto_util_se_ajusta(monkeypatch):
    corta = "<html><body><main><p>" + "Información suficiente para el ajuste. " * 3 + "</p></main></body></html>"
    assert _codigo(_revisar_todo, pagina_leida(corta)) == "no_content"

    monkeypatch.setattr(settings, "web_min_text_chars", 50)
    _revisar_todo(pagina_leida(corta))
