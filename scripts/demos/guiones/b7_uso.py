"""B7. Uso y gasto: filtros, indicadores, gráfica, tablas, registro y CSV."""

import re

from grabador import Grabacion

ID = "b7-uso"
TITULO = "Uso y gasto"
URL = "http://localhost:3001/#/uso"
STORAGE: dict = {}
IGNORAR_HTTPS = True
SESION_PANEL = "coord.comp@itcr.ac.cr"


def _segmento(p, etiqueta: str, opcion: str):
    return p.locator(f'[aria-label="{etiqueta}"]').get_by_text(opcion, exact=True)


def guion(g: Grabacion) -> None:
    p = g.page
    p.get_by_role("region", name="Indicadores del período").wait_for(timeout=30000)
    g.pausa(1.0)

    with g.sub("Uso muestra cuánto se usa MIA y cuánto cuesta. Sale del registro de todas las consultas, incluso las rechazadas."):
        g.mover(p.get_by_role("heading", name="Uso", exact=True))
        g.pausa(1.5)

    with g.sub("Elige el período: hoy, 7 días, 30 días o un rango de fechas."):
        g.clic(_segmento(p, "Período", "30 días"))
        p.get_by_role("region", name="Indicadores del período").wait_for()
        g.pausa(1.5)

    with g.sub("También puedes filtrar por artefacto y por modo de respuesta. Todo el módulo se ajusta al filtro."):
        g.clic(p.get_by_role("search", name="Filtros del uso").get_by_label("Modo", exact=True))
        g.clic(p.get_by_role("option", name="Con razonamiento"))
        g.pausa(1.5)
        g.clic(p.get_by_role("search", name="Filtros del uso").get_by_label("Modo", exact=True))
        g.clic(p.get_by_role("option", name="Todos", exact=True))
        g.pausa(1.0)

    with g.sub("Los indicadores resumen el período y lo comparan con el anterior: gasto, consultas, tokens, tiempos, errores y respuestas útiles."):
        for nombre in ("Gasto", "Consultas", "Tiempo de respuesta (mediana)", "Respuestas útiles"):
            g.mover(p.get_by_role("region", name="Indicadores del período").get_by_text(nombre, exact=True).first)
            g.pausa(0.8)

    with g.sub("«Sin información» y «Errores» te dicen qué porcentaje de preguntas no se pudo responder."):
        g.mover(p.get_by_role("region", name="Indicadores del período").get_by_text("Sin información", exact=True))
        g.pausa(1.2)
        g.mover(p.get_by_role("region", name="Indicadores del período").get_by_text("Errores", exact=True))
        g.pausa(1.2)

    with g.sub("La gráfica muestra la evolución. Cambia la métrica entre gasto, consultas y tokens."):
        g.mover(p.get_by_role("region", name="Uso a lo largo del tiempo"))
        g.clic(_segmento(p, "Métrica", "Consultas"))
        g.pausa(1.5)

    with g.sub("El desglose separa la gráfica por artefacto, por modo o por modelo."):
        g.clic(_segmento(p, "Desglose", "Modo"))
        g.pausa(2.0)

    with g.sub("«Ver como tabla» muestra los mismos números en filas."):
        g.clic(p.get_by_role("button", name="Ver como tabla"))
        g.pausa(2.0)
        g.clic(p.get_by_role("button", name="Ver gráfica"))
        g.pausa(0.6)

    with g.sub("Las tablas comparan los artefactos, con el gasto de hoy frente a su tope, y los modelos usados."):
        g.mover(p.get_by_role("region", name="Por artefacto"))
        g.pausa(2.0)
        g.mover(p.get_by_role("region", name="Por modelo"))
        g.pausa(2.0)

    with g.sub("El registro lista cada consulta, la más reciente primero. Filtra por resultado, por ejemplo «Sin información»."):
        g.mover(p.get_by_role("region", name="Registro de consultas"))
        g.clic(p.get_by_label("Resultado", exact=True).first)
        g.clic(p.get_by_role("option", name="Sin información"))
        g.pausa(1.8)
        g.clic(p.get_by_label("Resultado", exact=True).first)
        g.clic(p.get_by_role("option", name="Todos", exact=True))
        g.pausa(0.8)

    with g.sub("Toca la fecha de una consulta para ver su detalle: dominios, documentos citados, modelo, costo y calificación."):
        g.clic(p.get_by_role("region", name="Registro de consultas").locator("tr").filter(has_text="Respondida").first.get_by_role("button", name=re.compile("^Ver el detalle")))
        p.get_by_text("Detalle de la consulta").wait_for()
        g.pausa(3.0)
        g.clic(p.get_by_role("button", name="Cerrar", exact=True))

    with g.sub("«Descargar CSV» baja el registro. Las preguntas solo se incluyen si marcas la casilla, porque pueden tener datos personales."):
        g.mover(p.get_by_text("Incluir las preguntas"))
        g.pausa(1.5)
        with p.expect_download():
            g.clic(p.get_by_role("button", name="Descargar CSV"))
        g.pausa(1.5)
