"""B4. Eliminar documentos, uno o varios."""

from grabador import Grabacion

ID = "b4-eliminar-documentos"
TITULO = "Eliminar documentos"
URL = "http://localhost:3001/#/inventario"
STORAGE: dict = {}
IGNORAR_HTTPS = True
SESION_PANEL = "coord.comp@itcr.ac.cr"


def guion(g: Grabacion) -> None:
    p = g.page
    p.get_by_label("Contraer Unidad de Postgrados de Computación").wait_for()
    g.pausa(1.0)

    with g.sub("Para eliminar un documento, búscalo en el inventario. Cada fila tiene su botón «Eliminar»."):
        g.clic(p.get_by_label("Expandir Memoria del Consejo"))
        g.clic(p.get_by_label("Expandir Actas 2026"))
        g.mover(p.get_by_label("Eliminar Acta de ejemplo 01-2026.pdf"))
        g.pausa(1.0)

    with g.sub("Antes de borrar, la ventana te dice qué documento es y qué se pierde: el archivo, sus imágenes y su contenido en las respuestas."):
        g.clic(p.get_by_label("Eliminar Acta de ejemplo 01-2026.pdf"))
        p.get_by_role("dialog").wait_for()
        g.mover(p.get_by_role("dialog").get_by_text("Se pierden el documento"))
        g.pausa(2.0)

    with g.sub("También avisa que no se puede deshacer: para recuperarlo hay que volver a subir el archivo original."):
        g.mover(p.get_by_role("dialog").get_by_text("No se puede deshacer"))
        g.pausa(2.5)

    with g.sub("Si estás de acuerdo, confirma con «Eliminar». El panel avisa que el documento se eliminó."):
        g.clic(p.get_by_role("dialog").get_by_role("button", name="Eliminar", exact=True))
        p.get_by_text("Documento eliminado").wait_for()
        g.pausa(2.0)
        g.clic(p.get_by_role("button", name="Cerrar", exact=True))

    with g.sub("Para eliminar varios a la vez, pulsa «Seleccionar». Cada documento muestra una casilla."):
        g.clic(p.get_by_role("button", name="Seleccionar", exact=True))
        g.pausa(1.2)

    with g.sub("La casilla de una carpeta, un dominio o un programa marca todos sus documentos. La barra cuenta cuántos llevas."):
        g.clic(p.get_by_label("Seleccionar todos los documentos de Actas 2026"))
        p.get_by_text("2 seleccionados").wait_for()
        g.pausa(1.8)

    with g.sub("«Eliminar seleccionados» abre una sola confirmación para todos, con la lista de lo que se va a borrar."):
        g.clic(p.get_by_role("button", name="Eliminar seleccionados (2)"))
        p.get_by_role("dialog").wait_for()
        g.pausa(3.0)

    with g.sub("Al confirmar, el aviso dice cuántos documentos se eliminaron."):
        g.clic(p.get_by_role("dialog").get_by_role("button", name="Eliminar 2 documentos"))
        p.get_by_text("2 documentos eliminados").wait_for()
        g.pausa(2.0)

    with g.sub("«Cancelar selección» vuelve a la vista normal. Lo que borres solo afecta a tu programa."):
        g.clic(p.get_by_role("button", name="Cancelar selección"))
        g.pausa(1.5)
