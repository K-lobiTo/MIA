"""Lector de páginas de la feature 022 (núcleo): una dirección, sus redirecciones, la IP validada, topes y errores de red.
Sin red: la resolución de nombres y el transporte de `httpx` son simulados (tests/unit/web_de_prueba.py)."""

import gzip
import ssl

import httpx
import pytest

from mia.config import settings
from mia.ingestion.web.errors import WebRejection
from mia.ingestion.web.fetcher import FetchedPage, HttpPageFetcher, PageFetcher, get_page_fetcher
from tests.unit.web_de_prueba import (
    IP_PUBLICA,
    Respuesta,
    html,
    resolver_de,
    resolver_publico,
    transporte,
)


class Reloj:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def _fetcher(rutas, resolver=None, reloj=None, **kwargs):
    t = transporte(rutas, **kwargs)
    return HttpPageFetcher(resolver=resolver or resolver_publico("ejemplo.test", "otro.test"), transporte=t, reloj=reloj or Reloj()), t


def _codigo(fetcher, url):
    with pytest.raises(WebRejection) as error:
        fetcher.fetch(url)
    return error.value.code


def test_una_pagina_200_devuelve_el_cuerpo_el_tipo_y_la_direccion_final():
    f, _ = _fetcher({"https://ejemplo.test/programa": html("<p>Hola</p>")})

    pagina = f.fetch("https://ejemplo.test/programa")

    assert isinstance(pagina, FetchedPage)
    assert pagina.estado == 200 and pagina.cuerpo == b"<p>Hola</p>"
    assert pagina.tipo_contenido.startswith("text/html")
    assert pagina.url_final == "https://ejemplo.test/programa"


def test_se_conecta_a_la_ip_ya_validada_con_el_nombre_en_host_y_sni():
    f, t = _fetcher({"https://ejemplo.test/programa": html("x")})

    f.fetch("https://ejemplo.test/programa")

    pedida = t.peticiones[0]
    assert pedida.url.startswith(f"https://{IP_PUBLICA}")
    assert pedida.host == "ejemplo.test"
    assert pedida.sni == "ejemplo.test"


def test_las_redirecciones_se_siguen_a_mano_y_la_final_es_la_del_ultimo_salto():
    f, t = _fetcher(
        {
            "https://ejemplo.test/a": Respuesta(301, {"location": "/b"}),
            "https://ejemplo.test/b": Respuesta(302, {"location": "https://otro.test/c"}),
            "https://otro.test/c": html("final"),
        }
    )

    pagina = f.fetch("https://ejemplo.test/a")

    assert pagina.url_final == "https://otro.test/c" and pagina.cuerpo == b"final"
    assert _paginas(t) == ["https://ejemplo.test/a", "https://ejemplo.test/b", "https://otro.test/c"]


def test_demasiadas_redirecciones_y_los_ciclos_se_rechazan(monkeypatch):
    monkeypatch.setattr(settings, "web_max_redirects", 3)
    cadena = {f"https://ejemplo.test/{i}": Respuesta(302, {"location": f"/{i + 1}"}) for i in range(10)}
    f, _ = _fetcher(cadena)
    assert _codigo(f, "https://ejemplo.test/0") == "too_many_redirects"

    f, _ = _fetcher(
        {
            "https://ejemplo.test/a": Respuesta(302, {"location": "/b"}),
            "https://ejemplo.test/b": Respuesta(302, {"location": "/a"}),
        }
    )
    assert _codigo(f, "https://ejemplo.test/a") == "too_many_redirects"


def test_una_redireccion_a_la_red_interna_se_rechaza_sin_pedir_nada_a_esa_ip():
    resolver = resolver_de({"ejemplo.test": [IP_PUBLICA], "interno.test": ["127.0.0.1"]})
    f, t = _fetcher({"https://ejemplo.test/a": Respuesta(302, {"location": "https://interno.test/secreto"})}, resolver)

    assert _codigo(f, "https://ejemplo.test/a") == "private_address"
    assert all("127.0.0.1" not in p.url for p in t.peticiones)
    assert _paginas(t) == ["https://ejemplo.test/a"]


def test_una_redireccion_a_un_esquema_no_web_se_rechaza():
    f, t = _fetcher({"https://ejemplo.test/a": Respuesta(302, {"location": "ftp://ejemplo.test/archivo"})})

    assert _codigo(f, "https://ejemplo.test/a") == "invalid_url"
    assert _paginas(t) == ["https://ejemplo.test/a"]


def test_un_cuerpo_mayor_que_el_tope_se_rechaza_sin_leerlo_entero(monkeypatch):
    monkeypatch.setattr(settings, "web_max_page_kb", 64)
    leidos = []

    def bloques():
        for _ in range(1000):
            leidos.append(1)
            yield b"x" * 16384

    f, _ = _fetcher({"https://ejemplo.test/grande": Respuesta(200, {"content-type": "text/html"}, bloques())})

    assert _codigo(f, "https://ejemplo.test/grande") == "too_large"
    assert len(leidos) * 16384 <= 64 * 1024 + 2 * 16384


def test_un_content_length_mayor_que_el_tope_se_rechaza_antes_de_leer(monkeypatch):
    monkeypatch.setattr(settings, "web_max_page_kb", 64)
    f, _ = _fetcher({"https://ejemplo.test/grande": Respuesta(200, {"content-length": str(10 * 1024 * 1024)}, b"x")})

    assert _codigo(f, "https://ejemplo.test/grande") == "too_large"


@pytest.mark.parametrize(
    "error,esperado",
    [
        (httpx.ConnectTimeout("t"), "unreachable"),
        (httpx.ReadTimeout("t"), "unreachable"),
        (httpx.ConnectError("c"), "unreachable"),
        (httpx.RemoteProtocolError("p"), "unreachable"),
    ],
)
def test_los_errores_de_red_son_inalcanzable(error, esperado):
    f, _ = _fetcher({"https://ejemplo.test/a": error})

    assert _codigo(f, "https://ejemplo.test/a") == esperado


def test_un_nombre_que_no_resuelve_es_inalcanzable():
    f, t = _fetcher({}, resolver=resolver_de({}))

    assert _codigo(f, "https://nada.test/a") == "unreachable"
    assert t.peticiones == []


def test_un_error_de_tls_es_tls_error():
    error = httpx.ConnectError("fallo")
    error.__cause__ = ssl.SSLCertVerificationError("certificado vencido")
    f, _ = _fetcher({"https://ejemplo.test/a": error})

    assert _codigo(f, "https://ejemplo.test/a") == "tls_error"


def test_el_plazo_total_se_respeta_entre_peticiones(monkeypatch):
    monkeypatch.setattr(settings, "web_fetch_timeout_seconds", 15)
    reloj = Reloj()

    def lenta(request):
        reloj.t += 10
        return Respuesta(302, {"location": "/siguiente"})

    f, t = _fetcher({"https://ejemplo.test/a": lenta, "https://ejemplo.test/siguiente": lenta}, reloj=reloj)

    assert _codigo(f, "https://ejemplo.test/a") == "unreachable"
    assert len(_paginas(t)) == 2  # no hace una tercera


def test_el_plazo_total_se_revisa_tambien_mientras_se_lee_el_cuerpo(monkeypatch):
    monkeypatch.setattr(settings, "web_fetch_timeout_seconds", 15)
    reloj = Reloj()
    leidos = []

    def gota_a_gota():
        for _ in range(10):
            reloj.t += 6  # cada bloque tarda 6 s: el plazo se pasa dentro de una sola petición
            leidos.append(1)
            yield b"x" * 100

    f, _ = _fetcher({"https://ejemplo.test/lenta": Respuesta(200, {"content-type": "text/html"}, gota_a_gota())}, reloj=reloj)

    assert _codigo(f, "https://ejemplo.test/lenta") == "unreachable"
    assert len(leidos) <= 4


def test_un_cuerpo_comprimido_que_se_expande_mas_alla_del_tope_se_rechaza(monkeypatch):
    monkeypatch.setattr(settings, "web_max_page_kb", 64)
    bomba = gzip.compress(b"a" * (5 * 1024 * 1024))
    assert len(bomba) < 64 * 1024  # el cuerpo que viaja es pequeño; ya descomprimido supera el tope
    f, _ = _fetcher(
        {"https://ejemplo.test/bomba": Respuesta(200, {"content-type": "text/html", "content-encoding": "gzip"}, bomba)}
    )

    assert _codigo(f, "https://ejemplo.test/bomba") == "too_large"


def test_la_peticion_se_identifica_y_no_lleva_cookies(monkeypatch):
    monkeypatch.setattr(settings, "web_user_agent", "MIA-Lector/9.9 (prueba)")
    f, t = _fetcher(
        {
            "https://ejemplo.test/a": Respuesta(302, {"location": "/b", "set-cookie": "sesion=abc; Path=/"}),
            "https://ejemplo.test/b": html("ok"),
        }
    )

    f.fetch("https://ejemplo.test/a")

    assert len(t.peticiones) == 3  # robots.txt y los dos saltos
    for pedida in t.peticiones:
        assert pedida.cabeceras["user-agent"] == "MIA-Lector/9.9 (prueba)"
        assert pedida.cabeceras["accept-language"] == "es"
        assert "cookie" not in pedida.cabeceras
        assert pedida.cabeceras["accept-encoding"] == "identity"


def test_solo_se_piden_la_direccion_y_sus_redirecciones():
    f, t = _fetcher(
        {
            "https://ejemplo.test/a": Respuesta(301, {"location": "/b"}),
            "https://ejemplo.test/b": html('<a href="/otra">otra</a><img src="/imagen.png">'),
        }
    )

    f.fetch("https://ejemplo.test/a")

    assert _paginas(t) == ["https://ejemplo.test/a", "https://ejemplo.test/b"]
    assert set(t.logicas()) - set(_paginas(t)) <= {"https://ejemplo.test/robots.txt"}


def test_la_codificacion_sale_de_la_cabecera_content_type():
    f, _ = _fetcher({"https://ejemplo.test/a": html("x", tipo="text/html; charset=ISO-8859-1")})

    assert f.fetch("https://ejemplo.test/a").codificacion == "iso-8859-1"


def test_la_factory_devuelve_el_lector_http_y_rechaza_un_nombre_desconocido():
    assert isinstance(get_page_fetcher("http"), HttpPageFetcher)
    assert isinstance(get_page_fetcher(), PageFetcher)
    with pytest.raises(ValueError):
        get_page_fetcher("navegador")


# ---------- robots.txt (RFC 9309) ----------


def _robots(contenido, estado=200):
    return Respuesta(estado, {"content-type": "text/plain"}, contenido)


def _paginas(transporte_):
    """Direcciones pedidas sin las de robots.txt."""
    return [u for u in transporte_.logicas() if not u.endswith("/robots.txt")]


def test_antes_de_pedir_la_pagina_se_pide_robots_txt_con_la_misma_identificacion():
    f, t = _fetcher({"https://ejemplo.test/a": html("x")})

    f.fetch("https://ejemplo.test/a")

    assert t.logicas() == ["https://ejemplo.test/robots.txt", "https://ejemplo.test/a"]
    assert t.peticiones[0].cabeceras["user-agent"] == t.peticiones[1].cabeceras["user-agent"]


def test_una_ruta_prohibida_se_rechaza_sin_pedir_la_pagina():
    reglas = "User-agent: *\nDisallow: /privado/\n"
    f, t = _fetcher({"https://ejemplo.test/robots.txt": _robots(reglas), "https://ejemplo.test/publico/a": html("ok")})

    assert f.fetch("https://ejemplo.test/publico/a").cuerpo == b"ok"
    assert _codigo(f, "https://ejemplo.test/privado/a") == "robots_disallowed"
    assert "https://ejemplo.test/privado/a" not in t.logicas()


def test_la_regla_del_token_de_este_cliente_tiene_prioridad_sobre_el_comodin():
    reglas = "User-agent: *\nDisallow: /\n\nUser-agent: MIA-Lector\nAllow: /\n"
    f, _ = _fetcher({"https://ejemplo.test/robots.txt": _robots(reglas), "https://ejemplo.test/a": html("ok")})

    assert f.fetch("https://ejemplo.test/a").cuerpo == b"ok"

    solo_comodin = "User-agent: *\nDisallow: /\n"
    f, _ = _fetcher({"https://ejemplo.test/robots.txt": _robots(solo_comodin), "https://ejemplo.test/a": html("ok")})
    assert _codigo(f, "https://ejemplo.test/a") == "robots_disallowed"


@pytest.mark.parametrize("respuesta", [_robots("", 404), _robots("Attention Required! | Cloudflare", 403), _robots("", 410)])
def test_robots_txt_con_un_error_4xx_es_sin_restricciones(respuesta):
    f, _ = _fetcher({"https://ejemplo.test/robots.txt": respuesta, "https://ejemplo.test/a": html("ok")})

    assert f.fetch("https://ejemplo.test/a").cuerpo == b"ok"


@pytest.mark.parametrize(
    "respuesta",
    [_robots("", 500), _robots("", 503), httpx.ReadTimeout("t"), httpx.ConnectError("c")],
)
def test_robots_txt_inalcanzable_se_trata_como_prohibido(respuesta):
    f, t = _fetcher({"https://ejemplo.test/robots.txt": respuesta, "https://ejemplo.test/a": html("ok")})

    assert _codigo(f, "https://ejemplo.test/a") == "robots_disallowed"
    assert _paginas(t) == []


def test_un_robots_txt_que_redirige_se_sigue_y_se_valida_como_cualquier_direccion():
    resolver = resolver_de({"ejemplo.test": [IP_PUBLICA], "interno.test": ["127.0.0.1"]})
    f, t = _fetcher(
        {
            "https://ejemplo.test/robots.txt": Respuesta(301, {"location": "https://ejemplo.test/reglas.txt"}),
            "https://ejemplo.test/reglas.txt": _robots("User-agent: *\nDisallow: /x\n"),
            "https://ejemplo.test/a": html("ok"),
        },
        resolver,
    )
    assert f.fetch("https://ejemplo.test/a").cuerpo == b"ok"

    f, t = _fetcher(
        {
            "https://ejemplo.test/robots.txt": Respuesta(302, {"location": "https://interno.test/robots.txt"}),
            "https://ejemplo.test/a": html("ok"),
        },
        resolver,
    )
    assert _codigo(f, "https://ejemplo.test/a") == "private_address"
    assert all("127.0.0.1" not in p.url for p in t.peticiones)


def test_si_la_redireccion_cambia_de_origen_se_consulta_el_robots_txt_del_nuevo_origen_antes():
    f, t = _fetcher(
        {
            "https://ejemplo.test/a": Respuesta(302, {"location": "https://otro.test/b"}),
            "https://otro.test/robots.txt": _robots("User-agent: *\nDisallow: /b\n"),
            "https://otro.test/b": html("no debe pedirse"),
        }
    )

    assert _codigo(f, "https://ejemplo.test/a") == "robots_disallowed"
    assert "https://otro.test/b" not in t.logicas()
    assert t.logicas().index("https://otro.test/robots.txt") > t.logicas().index("https://ejemplo.test/a")


def test_el_cuerpo_de_robots_txt_se_corta_en_256_kb():
    enorme = "User-agent: *\nDisallow: /nada\n" + "# relleno\n" * 100000  # más de 1 MB
    f, _ = _fetcher({"https://ejemplo.test/robots.txt": _robots(enorme), "https://ejemplo.test/a": html("ok")})

    assert f.fetch("https://ejemplo.test/a").cuerpo == b"ok"  # no falla con too_large y respeta las reglas del comienzo


def test_robots_txt_se_pide_una_sola_vez_por_origen_en_el_mismo_intento():
    f, t = _fetcher(
        {
            "https://ejemplo.test/a": Respuesta(302, {"location": "/b"}),
            "https://ejemplo.test/b": Respuesta(302, {"location": "/c"}),
            "https://ejemplo.test/c": html("ok"),
        }
    )

    f.fetch("https://ejemplo.test/a")

    assert t.logicas().count("https://ejemplo.test/robots.txt") == 1


# ---------- una sola página (US3) ----------


def test_leer_una_pagina_con_enlaces_no_visita_ninguno_de_ellos():
    from tests.unit.web_de_prueba import pagina

    f, t = _fetcher({"https://ejemplo.test/seccion/pagina": html(pagina("enlaces.html"))})

    f.fetch("https://ejemplo.test/seccion/pagina")

    # Solo robots.txt y la página: ni la otra página, ni el sitio externo, ni el PDF, ni la imagen, ni el marco.
    assert t.logicas() == ["https://ejemplo.test/robots.txt", "https://ejemplo.test/seccion/pagina"]
