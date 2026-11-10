"""B1. Entrar al panel con la cuenta del TEC y qué ve cada alcance."""

import html
from urllib.parse import quote

from grabador import Grabacion

ID = "b1-entrar-panel"
TITULO = "Entrar al panel"
URL = "http://localhost:3001"
STORAGE: dict = {}
IGNORAR_HTTPS = True  # el Microsoft simulado usa un certificado autofirmado

CUENTA = "coord.comp@itcr.ac.cr"

TARJETA = """<!doctype html><meta charset="utf-8"><title>Inicio de sesión</title>
<style>body{margin:0;min-height:100vh;display:grid;place-items:center;background:#f2f8fa;color:#1c2f45;font:18px/1.5 system-ui,sans-serif}
.c{background:#fff;border:1px solid #c9dde6;border-radius:10px;padding:32px 36px;max-width:520px;text-align:center}
h1{font-size:1.3rem;margin:0 0 12px}p{margin:0 0 22px}
a{display:inline-block;background:#3d5a80;color:#fff;text-decoration:none;padding:10px 26px;border-radius:6px;font-weight:700}</style>
<div class="c"><h1>Inicio de sesión de Microsoft</h1>
<p>Aquí Microsoft te pide tu cuenta del TEC (@itcr.ac.cr) y la verificación en dos pasos. Esa pantalla no se muestra en esta guía.</p>
<a href="{enlace}">Continuar</a></div>"""


def _microsoft(route, request):
    """Sustituye la pantalla del Microsoft simulado (una página de prueba) por una tarjeta que explica el paso."""
    if "cuenta=" in request.url:
        route.continue_()
        return
    enlace = html.escape(f"{request.url}&cuenta={quote(CUENTA)}")
    route.fulfill(status=200, content_type="text/html; charset=utf-8", body=TARJETA.replace("{enlace}", enlace))


def guion(g: Grabacion) -> None:
    p = g.page
    g.simular("https://localhost:9000/**/oauth2/v2.0/authorize*", _microsoft)
    boton = p.get_by_role("button", name="Iniciar sesión con Microsoft")
    boton.wait_for()
    g.pausa(1.0)

    with g.sub("El panel pide iniciar sesión con tu cuenta institucional del TEC (@itcr.ac.cr), con verificación en dos pasos."):
        g.mover(boton)
        g.pausa(1.0)

    with g.sub("Pulsa «Iniciar sesión con Microsoft». Microsoft te pide la cuenta y el segundo factor, y luego te devuelve al panel."):
        g.clic(boton)
        p.get_by_role("link", name="Continuar").wait_for()
        g.pausa(2.5)
        g.clic(p.get_by_role("link", name="Continuar"))
        p.get_by_text("Alcance:").first.wait_for(timeout=20000)
        g.pausa(1.0)

    with g.sub("Si tu cuenta no está autorizada, el panel te lo explica y no muestra ningún dato. Pide acceso a quien opera MIA."):
        g.pausa(1.5)

    with g.sub("El menú tiene un módulo por tarea: Inventario, Artefactos y accesos, Uso, Siglas y Usuarios de la Consulta."):
        for nombre in ("Inventario de información", "Artefactos y accesos", "Uso", "Siglas y equivalencias", "Usuarios de la Consulta"):
            g.mover(p.get_by_role("link", name=nombre))
            g.pausa(0.6)

    with g.sub("Abajo ves con qué cuenta entraste y tu alcance. Solo ves y cambias lo de tu programa."):
        g.mover(p.get_by_text("Alcance:").first)
        g.pausa(1.8)

    with g.sub("Quien opera MIA tiene alcance Global: ve todos los programas, el saldo de OpenRouter y el módulo Bots."):
        g.pausa(2.0)

    with g.sub("También puedes elegir la apariencia del panel: clara, oscura o la del sistema."):
        g.clic(p.locator("label:visible").filter(has=p.get_by_text("Modo oscuro")))
        g.pausa(1.5)
        g.clic(p.locator("label:visible").filter(has=p.get_by_text("Modo claro")))
        g.pausa(0.8)

    with g.sub("«Cerrar sesión» termina tu sesión. Úsala siempre en un equipo compartido."):
        g.mover(p.get_by_role("button", name="Cerrar sesión"))
        g.pausa(1.5)
