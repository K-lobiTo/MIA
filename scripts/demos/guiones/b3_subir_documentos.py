"""B3. Subir documentos y seguir su estado."""

from pathlib import Path

from grabador import Grabacion

ID = "b3-subir-documentos"
TITULO = "Subir documentos"
URL = "http://localhost:3001/#/inventario"
STORAGE: dict = {}
IGNORAR_HTTPS = True
SESION_PANEL = "coord.comp@itcr.ac.cr"

DATOS = Path(__file__).resolve().parents[1] / "datos_demo"
ARCHIVOS = [str(DATOS / "Reglamento de ejemplo.txt"), str(DATOS / "Preguntas frecuentes de ejemplo.txt")]
DOMINIO = "Proyectos de graduación: Tesis"


def _fila(p, titulo: str):
    return p.locator(".branch-head").filter(has=p.locator(".branch-title", has_text=titulo))


def _subir(g: Grabacion, archivos: list[str]) -> None:
    with g.page.expect_file_chooser() as elegido:
        g.clic(_fila(g.page, DOMINIO).get_by_role("button", name="Subir"))
    elegido.value.set_files(archivos)


def guion(g: Grabacion) -> None:
    p = g.page
    p.get_by_label("Contraer Unidad de Postgrados de Computación").wait_for()
    g.pausa(1.0)

    with g.sub("Los documentos se suben a un dominio o a una carpeta. Aquí usaremos el dominio de tesis."):
        g.clic(p.get_by_label(f"Expandir {DOMINIO}"))
        g.pausa(1.0)

    with g.sub("Pulsa «Subir» y elige los archivos. Se aceptan PDF, DOCX y TXT, y puedes elegir varios a la vez."):
        _subir(g, ARCHIVOS)
        p.get_by_text("Subidas", exact=True).wait_for()
        g.pausa(1.0)

    with g.sub("La lista «Subidas» muestra cada archivo, su destino y si se subió bien."):
        g.mover(p.get_by_text("Subido: en cola para procesarse.").first)
        g.pausa(1.5)

    with g.sub("Ya están en el dominio, con el estado «En cola»: MIA los va a leer y a prepararlos para las consultas."):
        g.mover(p.locator(".doc-row").filter(has_text="Reglamento de ejemplo.txt"))
        g.pausa(2.5)

    with g.sub("El estado pasa a «Procesando» y, cuando termina, a «Listo». La página se actualiza sola."):
        p.locator(".doc-row").filter(has_text="Reglamento de ejemplo.txt").get_by_text("Procesando").wait_for(timeout=40000)
        g.pausa(1.5)
        p.locator(".doc-row").filter(has_text="Reglamento de ejemplo.txt").get_by_text("Listo").wait_for(timeout=40000)
        g.pausa(1.5)

    with g.sub("Solo cuando el documento está «Listo» sus respuestas pueden usarlo. Si algo falla, el estado es «Error»."):
        g.mover(p.locator(".doc-row").filter(has_text="Preguntas frecuentes de ejemplo.txt").get_by_text("Listo"))
        g.pausa(1.5)

    with g.sub("Si subes un archivo que ya está en el dominio, MIA te avisa y no lo procesa de nuevo."):
        _subir(g, [ARCHIVOS[0]])
        p.get_by_text("Ya existía en este dominio").wait_for(timeout=20000)
        g.pausa(2.0)

    with g.sub("«Limpiar terminadas» vacía la lista de subidas. También puedes arrastrar archivos sobre un dominio o una carpeta."):
        g.clic(p.get_by_role("button", name="Limpiar terminadas"))
        g.pausa(1.5)
