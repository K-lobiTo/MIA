"""B9. Plantillas de un artefacto: el catálogo del modo Plantilla (panel)."""

import re
from pathlib import Path

from grabador import Grabacion

ID = "b9-plantillas-artefacto"
TITULO = "Plantillas de un artefacto"
URL = "http://localhost:3001/#/artefactos"
STORAGE: dict = {}
IGNORAR_HTTPS = True
SESION_PANEL = "coord.comp@itcr.ac.cr"

ARTEFACTO = "Consulta Postgrados de Computación"
COMPARACION_DOCX = str(Path(__file__).resolve().parents[3] / "docs" / "plantillas_ejemplo" / "Comparacion_de_programas.docx")


def _fila(p, nombre: str):
    return p.get_by_role("dialog").locator("li").filter(has_text=nombre)


def guion(g: Grabacion) -> None:
    p = g.page
    tarjeta = p.get_by_role("article", name=ARTEFACTO)
    tarjeta.wait_for(timeout=30000)
    g.pausa(1.0)

    with g.sub("Un artefacto con el modo Plantilla tiene un catálogo de plantillas. Se administra desde el botón «Plantillas»."):
        g.mover(tarjeta.get_by_role("button", name=re.compile("^Plantillas")))
        g.pausa(1.8)
        g.clic(tarjeta.get_by_role("button", name=re.compile("^Plantillas")))
        p.get_by_role("dialog").wait_for()
        g.pausa(1.0)

    with g.sub("Una plantilla es la estructura de la respuesta: secciones, títulos y orden. Los datos salen siempre de los documentos."):
        g.mover(p.get_by_text("Una plantilla es la estructura de la respuesta"))
        g.pausa(3.0)

    with g.sub("Las ve toda persona que consulte con este artefacto, con o sin sesión, en el grupo «Del artefacto»."):
        g.mover(p.get_by_role("dialog").get_by_text("Informe de programa"))
        g.pausa(2.5)

    with g.sub("«Agregar plantilla» abre el formulario. Escribe el nombre."):
        g.clic(p.get_by_role("button", name="Agregar plantilla"))
        g.escribir(p.get_by_label("Nombre de la plantilla"), "Comparación de programas")
        g.pausa(0.6)

    with g.sub("El contenido se escribe, o se carga desde un archivo Word (.docx) o de texto (.txt) para revisarlo antes de guardar."):
        with p.expect_file_chooser() as elegido:
            g.clic(p.get_by_role("button", name="Cargar archivo (.docx o .txt)"))
        elegido.value.set_files(COMPARACION_DOCX)
        p.wait_for_function("[...document.querySelectorAll('textarea')].some(t => t.value.length > 20)", timeout=15000)
        g.pausa(1.0)
        g.mover(p.get_by_label("Contenido"))
        g.pausa(3.0)

    with g.sub("No incluyas datos personales ni información confidencial: la plantilla se guarda tal cual."):
        g.mover(p.get_by_text("No incluyas datos personales"))
        g.pausa(2.5)
        g.clic(p.get_by_role("button", name="Guardar", exact=True))
        _fila(p, "Comparación de programas").wait_for()
        g.pausa(1.2)

    with g.sub("«Editar» cambia el nombre o el contenido. Las consultas siguientes usan la versión nueva."):
        g.clic(_fila(p, "Ficha corta").get_by_role("button", name="Editar"))
        p.get_by_label("Contenido").wait_for()
        g.pausa(3.0)
        g.clic(p.get_by_role("button", name="Cancelar", exact=True))
        g.pausa(0.8)

    with g.sub("«Eliminar» pide confirmación. Las respuestas ya entregadas no cambian, pero la plantilla ya no se podrá elegir."):
        g.clic(_fila(p, "Comparación de programas").get_by_role("button", name="Eliminar"))
        p.get_by_text("Las respuestas ya entregadas no cambian").wait_for()
        g.pausa(2.5)
        g.clic(p.get_by_role("button", name="Sí, eliminar"))
        g.pausa(1.2)

    with g.sub("Las plantillas personales de cada persona son aparte: las administra ella misma desde la Consulta."):
        g.clic(p.get_by_role("button", name="Cerrar", exact=True))
        g.mover(tarjeta.get_by_role("button", name=re.compile("^Plantillas")))
        g.pausa(2.0)
