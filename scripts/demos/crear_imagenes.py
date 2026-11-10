"""SOLO DESARROLLO: crea las imágenes ficticias de `datos_demo/` (el mapa y el horario de ejemplo) con Playwright.

    python scripts/demos/crear_imagenes.py
"""

from pathlib import Path

from playwright.sync_api import sync_playwright

DESTINO = Path(__file__).resolve().parent / "datos_demo"

MAPA = """<body style="margin:0;width:800px;height:450px;background:#e3f0f5;font:20px system-ui,sans-serif;color:#1c2f45">
<div style="padding:18px 26px;background:#3d5a80;color:#fff;font-size:26px;font-weight:700">Mapa de ejemplo del edificio</div>
<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:14px;padding:22px 26px">
<div style="background:#fff;border:2px solid #3d5a80;border-radius:8px;padding:28px 10px;text-align:center">Oficina del programa</div>
<div style="background:#fff;border:2px solid #3d5a80;border-radius:8px;padding:28px 10px;text-align:center">Aula 1</div>
<div style="background:#fff;border:2px solid #3d5a80;border-radius:8px;padding:28px 10px;text-align:center">Aula 2</div>
<div style="background:#fff;border:2px solid #98c1d9;border-radius:8px;padding:28px 10px;text-align:center;grid-column:span 2">Pasillo central</div>
<div style="background:#ee6c4d;color:#fff;border-radius:8px;padding:28px 10px;text-align:center;font-weight:700">Entrada</div>
</div><div style="padding:0 26px;font-size:16px">Imagen ficticia para la guía de uso</div></body>"""

HORARIO = """<body style="margin:0;width:800px;height:450px;background:#fff;font:20px system-ui,sans-serif;color:#1c2f45">
<div style="padding:18px 26px;background:#3d5a80;color:#fff;font-size:26px;font-weight:700">Horario de ejemplo</div>
<table style="margin:22px 26px;border-collapse:collapse;width:748px">
<tr style="background:#e3f0f5"><th style="padding:12px;border:1px solid #c9dde6;text-align:left">Curso</th><th style="padding:12px;border:1px solid #c9dde6">Día</th><th style="padding:12px;border:1px solid #c9dde6">Hora</th></tr>
<tr><td style="padding:12px;border:1px solid #c9dde6">Taller de Ejemplo A</td><td style="padding:12px;border:1px solid #c9dde6;text-align:center">Martes</td><td style="padding:12px;border:1px solid #c9dde6;text-align:center">6:00 p. m.</td></tr>
<tr><td style="padding:12px;border:1px solid #c9dde6">Taller de Ejemplo B</td><td style="padding:12px;border:1px solid #c9dde6;text-align:center">Jueves</td><td style="padding:12px;border:1px solid #c9dde6;text-align:center">6:00 p. m.</td></tr>
<tr><td style="padding:12px;border:1px solid #c9dde6">Seminario de Ejemplo</td><td style="padding:12px;border:1px solid #c9dde6;text-align:center">Sábado</td><td style="padding:12px;border:1px solid #c9dde6;text-align:center">8:00 a. m.</td></tr>
</table><div style="padding:0 26px;font-size:16px">Imagen ficticia para la guía de uso</div></body>"""


def main() -> None:
    with sync_playwright() as pw:
        navegador = pw.chromium.launch()
        pagina = navegador.new_page(viewport={"width": 800, "height": 450})
        for nombre, html in (("Mapa de ejemplo.png", MAPA), ("Horario de ejemplo.png", HORARIO)):
            pagina.set_content(html)
            pagina.screenshot(path=str(DESTINO / nombre))
            print("creada", DESTINO / nombre)
        navegador.close()


if __name__ == "__main__":
    main()
