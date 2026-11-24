"""A7. Responder con la estructura de una plantilla (modo Plantilla de la Consulta)."""

import re
from pathlib import Path

from grabador import Grabacion

ID = "a7-plantillas"
TITULO = "Responder con una plantilla"
URL = "http://localhost:3000"
STORAGE = {"mia-consulta-key": "mia_demo_computacion"}
USUARIO = "estudiante.demo"
CLAVE = "ClaveDemo2026"

RAIZ = Path(__file__).resolve().parents[3]
FICHA_DOCX = str(RAIZ / "docs" / "plantillas_ejemplo" / "Ficha_corta.docx")
PREGUNTA = "Prepárame el informe del Taller de Ejemplo A."


def _preguntar(g: Grabacion, texto: str, esperar: str) -> None:
    p = g.page
    g.escribir(p.get_by_label("Tu pregunta"), texto)
    g.tecla("Enter")
    p.get_by_text(esperar).first.wait_for(timeout=30000)
    g.pausa(1.2)


def guion(g: Grabacion) -> None:
    p = g.page
    p.get_by_role("button", name="Todos", exact=True).wait_for()
    g.pausa(1.0)

    with g.sub("El modo «Plantilla» responde con la estructura que tú eliges: sus secciones, sus títulos y su orden."):
        g.clic(p.locator(".mode-button"))
        g.pausa(1.0)
        g.clic(p.get_by_role("option", name=re.compile("^Plantilla")))
        p.get_by_label("Plantilla de la respuesta").wait_for()
        g.pausa(1.0)

    with g.sub("Elige una plantilla. Las del grupo «Del artefacto» las prepara quien administra MIA."):
        selector = p.get_by_label("Plantilla de la respuesta")
        g.mover(selector)
        g.pausa(1.0)
        selector.select_option(label="Informe de programa")
        g.pausa(1.2)

    with g.sub("Escribe tu pregunta. Los datos salen siempre de los documentos: la plantilla solo da la forma."):
        _preguntar(g, PREGUNTA, "Sin información en los documentos.")

    with g.sub("La respuesta trae las mismas secciones, en el mismo orden. Si los documentos no tienen un dato, la sección lo dice."):
        g.mover(p.get_by_text("Requisitos de ingreso").last)
        g.pausa(2.5)
        g.mover(p.get_by_text("Sin información en los documentos.").first)
        g.pausa(2.0)

    with g.sub("Sin iniciar sesión solo ves las plantillas del artefacto. Para guardar las tuyas, inicia sesión."):
        g.mover(p.get_by_text("Inicia sesión para guardar tus propias plantillas."))
        g.pausa(2.0)
        g.clic(p.get_by_role("button", name="Iniciar sesión").first)
        p.get_by_label("Usuario").wait_for()
        g.escribir(p.get_by_label("Usuario"), USUARIO)
        g.escribir(p.get_by_label("Contraseña", exact=True), CLAVE)
        g.clic(p.get_by_role("button", name="Iniciar sesión", exact=True))
        p.get_by_role("button", name="Administrar mis plantillas").wait_for(timeout=20000)
        g.pausa(1.0)

    with g.sub("Con sesión aparece «Administrar mis plantillas». Ahí agregas, editas y eliminas las tuyas."):
        g.clic(p.get_by_role("button", name="Administrar mis plantillas"))
        p.get_by_text("Todavía no tienes plantillas personales").wait_for()
        g.pausa(1.5)

    with g.sub("«Agregar plantilla» abre el formulario. Escribe un nombre y elige dónde se usa: solo en este artefacto o en todos."):
        g.clic(p.get_by_role("button", name="Agregar plantilla"))
        g.escribir(p.get_by_label("Nombre de la plantilla"), "Mi ficha corta")
        g.mover(p.get_by_label("Dónde se usa"))
        g.pausa(1.5)

    with g.sub("Puedes escribir el contenido o cargarlo desde un archivo Word (.docx) o de texto (.txt)."):
        with p.expect_file_chooser() as elegido:
            g.clic(p.get_by_role("button", name="Cargar archivo (.docx o .txt)"))
        elegido.value.set_files(FICHA_DOCX)
        p.get_by_label("Contenido").wait_for()
        p.wait_for_function("[...document.querySelectorAll('textarea')].some(t => t.value.length > 20)", timeout=15000)
        g.pausa(1.5)

    with g.sub("Del archivo se toma solo el texto: lo revisas y lo editas antes de guardar. El archivo no se guarda."):
        g.mover(p.get_by_label("Contenido"))
        g.pausa(3.0)

    with g.sub("No incluyas datos personales ni información confidencial: la plantilla se guarda tal cual."):
        g.mover(p.get_by_text("No incluyas datos personales"))
        g.pausa(2.5)
        g.clic(p.get_by_role("button", name="Guardar", exact=True))
        p.get_by_role("dialog").get_by_text("Mi ficha corta").wait_for()
        g.pausa(1.2)

    with g.sub("Cada plantilla muestra dónde se usa. «Eliminar» pide confirmación y no borra las respuestas que ya recibiste."):
        g.clic(p.get_by_role("button", name="Eliminar", exact=True).first)
        p.get_by_text("Las conversaciones que la usaron conservan sus respuestas").wait_for()
        g.pausa(2.5)
        g.clic(p.get_by_role("button", name="Cancelar", exact=True))
        g.clic(p.get_by_role("button", name="Cerrar", exact=True))
        g.pausa(0.8)

    with g.sub("Tus plantillas aparecen en el grupo «Mías». Elige la nueva y vuelve a preguntar."):
        selector = p.get_by_label("Plantilla de la respuesta")
        g.mover(selector)
        selector.select_option(label="Mi ficha corta")
        g.pausa(1.0)
        _preguntar(g, PREGUNTA, "Modalidad")

    with g.sub("La respuesta sigue ahora la estructura de tu ficha. Usa la plantilla que mejor sirva para cada informe."):
        g.mover(p.get_by_text("Duración").last)
        g.pausa(3.0)
