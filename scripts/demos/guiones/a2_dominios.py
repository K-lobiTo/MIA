"""A2. Elegir los dominios donde se busca."""

import re

from grabador import Grabacion

ID = "a2-dominios"
TITULO = "Elegir dominios"
URL = "http://localhost:3000"
STORAGE = {"mia-consulta-key": "mia_demo_computacion"}


def guion(g: Grabacion) -> None:
    p = g.page
    p.get_by_role("button", name="Todos", exact=True).wait_for()
    g.pausa(0.8)

    with g.sub("Un dominio es un conjunto de documentos del mismo tema, como Currículum o Memoria del Consejo."):
        g.mover(p.locator('input[aria-label="Dominios a consultar"]'))
        g.pausa(1.0)

    with g.sub("Al abrir la Consulta, todos los dominios vienen elegidos. El contador muestra cuántos llevas."):
        g.mover(p.get_by_text(re.compile(r"4 de 4")))
        g.pausa(1.2)

    with g.sub("«Ninguno» los quita todos. Sin dominios elegidos no se puede preguntar, y el campo te lo recuerda."):
        g.clic(p.get_by_role("button", name="Ninguno", exact=True))
        g.mover(p.get_by_text("Elige al menos un dominio.").last)
        g.pausa(1.2)

    with g.sub("Abre la lista para elegir. Cada dominio trae su descripción."):
        g.clic(p.locator('input[aria-label="Dominios a consultar"]'))
        g.pausa(1.2)

    with g.sub("La etiqueta «Dinámico» indica que el contenido cambia cada periodo y solo trae información vigente."):
        g.mover(p.get_by_text("Dinámico").first)
        g.pausa(1.5)

    with g.sub("Marca los dominios que necesites. La respuesta solo usa documentos de los dominios elegidos."):
        g.clic(p.get_by_role("option", name=re.compile("Currículum")))
        g.clic(p.get_by_role("option", name=re.compile("Memoria del Consejo")))
        g.pausa(0.8)

    with g.sub("También puedes escribir para filtrar la lista, por ejemplo «tesis»."):
        g.escribir(p.locator('input[aria-label="Dominios a consultar"]'), "tesis")
        g.pausa(0.8)
        g.clic(p.get_by_role("option", name=re.compile("Tesis")))
        g.pausa(0.8)

    with g.sub("Para quitar uno, usa la x de su etiqueta."):
        g.tecla("Escape")
        g.clic(p.locator(".mantine-Pill-remove").first)
        g.pausa(1.0)

    with g.sub("«Todos» vuelve a elegirlos. El navegador recuerda tu selección para la próxima vez."):
        g.clic(p.get_by_role("button", name="Todos", exact=True))
        g.pausa(1.5)
