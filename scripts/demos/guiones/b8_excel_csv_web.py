"""B8. Subir libros de Excel y archivos CSV, y agregar una página web como fuente."""

from pathlib import Path

from grabador import Grabacion

ID = "b8-excel-csv-web"
TITULO = "Excel, CSV y páginas web"
URL = "http://localhost:3001/#/inventario"
STORAGE: dict = {}
IGNORAR_HTTPS = True
SESION_PANEL = "coord.comp@itcr.ac.cr"

DATOS = Path(__file__).resolve().parents[1] / "datos_demo"
EXCEL = str(DATOS / "Cursos de ejemplo.xlsx")
CSV = str(DATOS / "Cursos de ejemplo.csv")
CSV_VACIO = str(DATOS / "Archivo vacio de ejemplo.csv")
DOMINIO = "Currículum"
PAGINA = "https://programas.ejemplo.cr/calendario"


def _fila(p, titulo: str):
    return p.locator(".branch-head").filter(has=p.locator(".branch-title", has_text=titulo))


def _documento(p, nombre: str):
    return p.locator(".doc-row").filter(has_text=nombre)


def _subir(g: Grabacion, archivos: list[str]) -> None:
    with g.page.expect_file_chooser() as elegido:
        g.clic(_fila(g.page, DOMINIO).get_by_role("button", name="Subir"))
    elegido.value.set_files(archivos)


def guion(g: Grabacion) -> None:
    p = g.page
    p.get_by_label("Contraer Unidad de Postgrados de Computación").wait_for()
    g.pausa(1.0)

    with g.sub("Además de PDF, DOCX y TXT, MIA acepta libros de Excel (.xlsx) y archivos CSV. Se suben igual: con «Subir»."):
        g.clic(p.get_by_label(f"Expandir {DOMINIO}"))
        g.mover(_fila(p, DOMINIO).get_by_role("button", name="Subir"))
        g.pausa(1.5)

    with g.sub("Elige el Excel y el CSV. Cada fila se convierte en texto que se puede consultar, con el nombre de sus columnas."):
        _subir(g, [EXCEL, CSV])
        p.get_by_text("Subidas", exact=True).wait_for()
        g.pausa(1.5)

    with g.sub("Un CSV suele traer datos de personas. El panel avisa antes: quita o anonimiza esas columnas si no hacen falta."):
        g.mover(p.get_by_text("Los archivos CSV suelen traer datos de personas"))
        g.pausa(4.0)
        g.clic(p.get_by_role("button", name="Cerrar", exact=True).first)

    with g.sub("El CSV exportado de Excel en español, con tildes y punto y coma, se lee sin que lo prepares."):
        g.mover(_documento(p, "Cursos de ejemplo.csv"))
        g.pausa(2.0)

    with g.sub("Pasan por los mismos estados que cualquier documento: En cola, Procesando y Listo."):
        _documento(p, "Cursos de ejemplo.xlsx").get_by_text("Listo").wait_for(timeout=60000)
        _documento(p, "Cursos de ejemplo.csv").get_by_text("Listo").wait_for(timeout=60000)
        g.mover(_documento(p, "Cursos de ejemplo.xlsx").get_by_text("Listo"))
        g.pausa(2.0)

    with g.sub("Si un archivo no se puede leer, queda en «Error» y el motivo se ve debajo. Aquí, un CSV vacío."):
        _subir(g, [CSV_VACIO])
        _documento(p, "Archivo vacio de ejemplo.csv").get_by_text("Error").wait_for(timeout=60000)
        g.mover(p.get_by_text("El archivo CSV no tiene contenido."))
        g.pausa(3.0)
        g.clic(p.get_by_role("button", name="Cerrar", exact=True).first)  # el aviso del CSV vuelve a salir con cada CSV

    with g.sub("También puedes agregar una página web como fuente: «Agregar página web» en el dominio o en una carpeta."):
        g.clic(_fila(p, DOMINIO).get_by_role("button", name="Agregar página web"))
        p.get_by_role("dialog").wait_for()
        g.pausa(1.5)

    with g.sub("MIA lee solo esa página, sin seguir sus enlaces. Si no se puede leer, te dice por qué y no crea nada."):
        g.escribir(p.get_by_label("Dirección de la página"), "https://programas.ejemplo.cr/no-existe")
        g.clic(p.get_by_role("dialog").get_by_role("button", name="Agregar página", exact=True))
        p.get_by_text("No se encontró la página").wait_for(timeout=20000)
        g.pausa(2.5)

    with g.sub("Corrige la dirección. El nombre es opcional: si lo dejas vacío, se usa el título de la página."):
        campo = p.get_by_label("Dirección de la página")
        campo.fill("")
        g.escribir(campo, PAGINA)
        g.mover(p.get_by_text("Es lo que se cita como fuente"))
        g.pausa(2.0)

    with g.sub("El panel recuerda que el contenido será consultable y que MIA no filtra datos personales de la página."):
        g.mover(p.get_by_text("El contenido de la página se podrá consultar"))
        g.pausa(3.5)
        g.clic(p.get_by_role("dialog").get_by_role("button", name="Agregar página", exact=True))
        _documento(p, "Calendario de ejemplo del periodo").wait_for(timeout=30000)
        g.pausa(1.0)

    with g.sub("La página queda como un documento de tipo web, con su dirección y la fecha en que se leyó."):
        g.mover(_documento(p, "Calendario de ejemplo del periodo").get_by_text("WEB"))
        g.pausa(2.5)

    with g.sub("«Ver texto» muestra lo que se extrajo de la página, para contrastarlo con ella antes de usarla."):
        g.clic(p.get_by_label("Ver el texto de Calendario de ejemplo del periodo"))
        p.get_by_text("Texto extraído de la página").wait_for()
        g.pausa(4.0)
        g.clic(p.get_by_role("dialog").get_by_role("button", name="Cerrar", exact=True))
        g.pausa(0.8)
