"""SOLO DESARROLLO: entrada al panel sin grabarla.

El panel guarda la sesión de Microsoft en `sessionStorage` (solo vive en la pestaña). Para que cada video del panel empiece ya
con la sesión abierta, se inicia sesión una vez con el Microsoft simulado en un navegador que no graba, se copia su
`sessionStorage` y el navegador que graba lo recibe antes de cargar la página. El video B1 es el único que muestra la entrada.
"""

import json

from playwright.sync_api import sync_playwright

PANEL = "http://localhost:3001"
COORDINACION = "coord.comp@itcr.ac.cr"  # coordinación de la Unidad de Postgrados de Computación (alcance de un programa)
OPERADOR = "operador@itcr.ac.cr"  # alcance global


def sesion_panel(correo: str = COORDINACION) -> dict[str, str]:
    """Inicia sesión con el Microsoft simulado y devuelve el contenido de `sessionStorage`."""
    with sync_playwright() as pw:
        navegador = pw.chromium.launch(headless=True)
        contexto = navegador.new_context(ignore_https_errors=True)
        pagina = contexto.new_page()
        pagina.goto(PANEL)
        pagina.get_by_role("button", name="Iniciar sesión con Microsoft").click()
        pagina.get_by_text(correo).click()
        pagina.get_by_text("Alcance:").first.wait_for(timeout=20000)
        datos = json.loads(pagina.evaluate("JSON.stringify(Object.fromEntries(Object.entries(sessionStorage)))"))
        navegador.close()
    return datos
