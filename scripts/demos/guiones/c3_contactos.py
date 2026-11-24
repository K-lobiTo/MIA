"""C3. Contactos de WhatsApp (alcance global): quién escribió al bot y los datos que dejó."""

import re

from grabador import Grabacion

ID = "c3-contactos"
TITULO = "Contactos de WhatsApp"
URL = "http://localhost:3001/#/contactos"
STORAGE: dict = {}
IGNORAR_HTTPS = True
SESION_PANEL = "operador@itcr.ac.cr"  # solo el alcance global ve este módulo


def guion(g: Grabacion) -> None:
    p = g.page
    p.get_by_label("Contactos por estado").wait_for(timeout=30000)
    g.pausa(1.0)

    with g.sub("Cuando alguien escribe al bot, MIA guarda su teléfono y, si quiere, su nombre y su correo para que la Coordinación lo contacte."):
        g.mover(p.get_by_role("heading", name="Contactos de WhatsApp"))
        g.pausa(2.0)

    with g.sub("Son datos personales. Solo el alcance global ve este módulo, y cada descarga y cada borrado queda registrado, sin los datos."):
        g.mover(p.get_by_text("Son datos personales"))
        g.pausa(3.5)

    with g.sub("Los cuadros cuentan los contactos por estado: dejó sus datos, invitada, pendiente y no quiso dejar datos."):
        for estado in ("Dejó sus datos", "Invitada", "Pendiente", "No quiso dejar datos"):
            g.mover(p.get_by_label("Contactos por estado").get_by_text(estado, exact=True))
            g.pausa(0.9)

    with g.sub("Filtra por bot, por estado o por si dejaron correo. Por ejemplo, solo quienes dejaron sus datos."):
        filtros = p.locator(".contactos-filters")
        g.clic(filtros.get_by_label("Estado"))
        g.clic(p.get_by_role("option", name="Dejó sus datos"))
        g.pausa(2.0)
        g.tecla("Escape")

    with g.sub("La tabla muestra el teléfono, el nombre y el correo si los dejó, el estado y las fechas del primer y del último mensaje."):
        g.mover(p.get_by_role("table").get_by_role("row").nth(1))
        g.pausa(3.5)

    with g.sub("«Descargar CSV» baja los contactos que ves con el filtro actual."):
        with p.expect_download():
            g.clic(p.get_by_role("button", name="Descargar CSV"))
        g.pausa(2.0)

    with g.sub("El bote de basura borra un contacto, con su nombre y su correo. Si esa persona vuelve a escribir, será una persona nueva."):
        g.clic(p.get_by_label(re.compile("^Borrar el contacto")).first)
        p.get_by_role("dialog").wait_for()
        g.pausa(3.0)
        g.clic(p.get_by_role("dialog").get_by_role("button", name="Borrar contacto", exact=True))
        p.get_by_text("Se borró 1 contacto.").wait_for()
        g.pausa(2.0)

    with g.sub("«Borrar los filtrados» elimina de una vez todos los contactos que ves. También pide confirmación."):
        g.clic(p.get_by_role("button", name=re.compile("^Borrar los")))
        p.get_by_role("dialog").wait_for()
        g.pausa(3.5)
        g.clic(p.get_by_role("dialog").get_by_role("button", name="Cancelar"))
        g.pausa(1.0)
