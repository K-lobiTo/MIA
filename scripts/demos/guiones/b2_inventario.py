"""B2. Organizar el inventario: programas, dominios, carpetas y la etiqueta Dinámico."""

from grabador import Grabacion

ID = "b2-inventario"
TITULO = "Organizar el inventario"
URL = "http://localhost:3001/#/inventario"
STORAGE: dict = {}
IGNORAR_HTTPS = True
SESION_PANEL = "coord.comp@itcr.ac.cr"


def _fila(p, titulo: str):
    """La cabecera de un programa, dominio o carpeta, para tomar sus botones."""
    return p.locator(".branch-head").filter(has=p.locator(".branch-title", has_text=titulo))


def guion(g: Grabacion) -> None:
    p = g.page
    p.get_by_text("Inventario de información").first.wait_for()
    p.get_by_label("Contraer Unidad de Postgrados de Computación").wait_for()
    g.pausa(1.0)

    with g.sub("El inventario organiza la información en niveles: programa, dominio, carpeta y documento."):
        g.mover(_fila(p, "Unidad de Postgrados de Computación"))
        g.pausa(1.2)

    with g.sub("Un dominio agrupa documentos del mismo tema y es lo que se elige al consultar. Ábrelo con la flecha."):
        g.clic(p.get_by_label("Expandir Currículum"))
        g.pausa(1.2)

    with g.sub("Las carpetas solo ordenan los documentos dentro de un dominio y se pueden anidar."):
        g.clic(p.get_by_label("Expandir Programas de curso"))
        g.pausa(1.2)

    with g.sub("Cada documento muestra su tipo, su fecha y su estado: En cola, Procesando, Listo o Error."):
        g.mover(p.get_by_text("Programa de curso Taller de Ejemplo A.pdf"))
        g.pausa(1.0)
        g.mover(p.locator(".doc-row").first.get_by_text("Listo"))
        g.pausa(1.2)

    with g.sub("La búsqueda encuentra programas, dominios, carpetas y documentos, y abre lo que coincide."):
        g.escribir(p.get_by_placeholder("Buscar programa, dominio, carpeta o documento"), "acta")
        g.pausa(1.8)
        campo = p.get_by_placeholder("Buscar programa, dominio, carpeta o documento")
        campo.fill("")
        g.pausa(0.8)
        g.clic(p.get_by_label("Expandir Currículum"))  # al limpiar la búsqueda el árbol vuelve a su estado plegado

    with g.sub("«+ Carpeta» crea una carpeta en el dominio. La consulta sigue siendo por dominio: las carpetas no la cambian."):
        g.clic(_fila(p, "Currículum").get_by_role("button", name="+ Carpeta"))
        g.escribir(p.get_by_label("Nombre"), "Reglamentos")
        g.clic(p.get_by_role("button", name="Crear carpeta"))
        _fila(p, "Reglamentos").wait_for()
        g.pausa(1.0)

    with g.sub("Una carpeta se puede renombrar..."):
        g.clic(_fila(p, "Reglamentos").get_by_role("button", name="Renombrar"))
        campo = p.get_by_label("Nombre")
        campo.fill("")
        g.escribir(campo, "Reglamentos 2026")
        g.clic(p.get_by_role("button", name="Guardar", exact=True))
        _fila(p, "Reglamentos 2026").wait_for()
        g.pausa(0.8)

    with g.sub("...y borrar, pero solo si está vacía. Pide confirmación."):
        g.clic(_fila(p, "Reglamentos 2026").get_by_role("button", name="Borrar"))
        g.pausa(1.5)
        g.clic(p.get_by_role("dialog").get_by_role("button", name="Borrar", exact=True))
        g.pausa(1.0)

    with g.sub("«+ Dominio» crea un dominio nuevo dentro del programa, con su nombre y una descripción."):
        g.clic(_fila(p, "Unidad de Postgrados de Computación").get_by_role("button", name="+ Dominio"))
        g.escribir(p.get_by_label("Nombre"), "Normativa de ejemplo")
        g.escribir(p.get_by_label("Descripción"), "Reglamentos del programa (ejemplo)")
        g.pausa(0.6)
        g.clic(p.get_by_role("button", name="Crear dominio"))
        p.get_by_text("Lo verán de inmediato").wait_for()
        g.pausa(1.0)

    with g.sub("El panel te dice qué artefactos lo verán enseguida y cuáles hay que habilitar en Artefactos y accesos."):
        g.mover(p.get_by_text("Hay que habilitarlo en Artefactos y accesos"))
        g.pausa(2.5)
        g.clic(p.get_by_role("button", name="Cerrar", exact=True))
        _fila(p, "Normativa de ejemplo").wait_for()
        g.pausa(0.6)

    with g.sub("«Marcar dinámico» etiqueta un dominio cuyo contenido cambia cada periodo. Es solo una etiqueta: no cambia la búsqueda."):
        g.clic(_fila(p, "Normativa de ejemplo").get_by_role("button", name="Marcar dinámico"))
        _fila(p, "Normativa de ejemplo").get_by_text("Dinámico").first.wait_for()
        g.pausa(1.8)
