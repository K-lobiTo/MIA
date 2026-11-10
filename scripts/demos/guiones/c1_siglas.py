"""C1. Siglas y equivalencias (alcance global)."""

from grabador import Grabacion

ID = "c1-siglas"
TITULO = "Siglas y equivalencias"
URL = "http://localhost:3001/#/siglas"
STORAGE: dict = {}
IGNORAR_HTTPS = True
SESION_PANEL = "operador@itcr.ac.cr"  # alcance global: solo este alcance puede cambiar la lista


def guion(g: Grabacion) -> None:
    p = g.page
    p.get_by_role("region", name="Equivalencias de siglas").wait_for(timeout=30000)
    g.pausa(1.0)

    with g.sub("Las personas escriben siglas como TFG. Esta lista le enseña a la búsqueda que TFG y su forma desarrollada son lo mismo."):
        g.mover(p.get_by_role("heading", name="Siglas y equivalencias"))
        g.pausa(2.0)

    with g.sub("Si la pregunta lleva la sigla, la búsqueda también busca la forma desarrollada, y al revés."):
        g.mover(p.get_by_role("row").filter(has_text="TFG"))
        g.pausa(2.5)

    with g.sub("La lista vale para todos los programas. Un cambio se nota en menos de un minuto y no hay que reindexar los documentos."):
        g.mover(p.get_by_text("Último cambio"))
        g.pausa(2.5)

    with g.sub("«Agregar equivalencia» suma una nueva: escribe la sigla (de 3 a 20 letras o dígitos) y su forma desarrollada."):
        g.clic(p.get_by_role("button", name="Agregar equivalencia"))
        g.escribir(p.get_by_label("Sigla (por ejemplo, TFG)"), "PGE")
        g.escribir(p.get_by_label("Forma desarrollada (por ejemplo, Trabajo Final de Graduación)"), "Programa de Graduación de Ejemplo")
        g.pausa(0.6)
        g.clic(p.get_by_role("button", name="Agregar", exact=True))
        p.get_by_role("row").filter(has_text="PGE").wait_for()
        g.pausa(1.2)

    with g.sub("El lápiz edita una equivalencia, por ejemplo para corregir su forma desarrollada."):
        g.clic(p.get_by_label("Editar PGE"))
        campo = p.get_by_label("Forma desarrollada (por ejemplo, Trabajo Final de Graduación)")
        campo.fill("")
        g.escribir(campo, "Programa de Graduación del Ejemplo")
        g.clic(p.get_by_role("button", name="Guardar", exact=True))
        p.get_by_role("row").filter(has_text="del Ejemplo").wait_for()
        g.pausa(1.0)

    with g.sub("El bote de basura la borra. Los documentos no se tocan: solo la búsqueda deja de hacer esa equivalencia."):
        g.clic(p.get_by_label("Borrar PGE"))
        p.get_by_role("dialog").wait_for()
        g.pausa(2.5)
        g.clic(p.get_by_role("dialog").get_by_role("button", name="Borrar", exact=True))
        g.pausa(1.2)

    with g.sub("Las personas que administran un programa ven la lista, pero solo el alcance global puede cambiarla."):
        g.mover(p.get_by_role("region", name="Equivalencias de siglas"))
        g.pausa(2.0)

    with g.sub("La lista solo tiene efecto cuando la búsqueda híbrida está encendida en la instancia."):
        g.mover(p.get_by_text("Mientras la búsqueda híbrida esté apagada"))
        g.pausa(2.0)
