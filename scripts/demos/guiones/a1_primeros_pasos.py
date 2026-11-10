"""A1. Primeros pasos en la Consulta: la clave, la pantalla, la apariencia y el menú lateral."""

import re

from grabador import Grabacion

ID = "a1-primeros-pasos"
TITULO = "Primeros pasos"
URL = "http://localhost:3000"
STORAGE: dict = {}  # sin clave guardada: se ve la pantalla de entrada


def guion(g: Grabacion) -> None:
    p = g.page
    p.get_by_label("Clave de la Consulta").wait_for()
    g.pausa(1.0)

    with g.sub("Abre la dirección de tu Consulta. La primera vez te pide la clave que te entregó quien administra MIA."):
        g.mover(p.get_by_label("Clave de la Consulta"))
        g.pausa(1.0)

    with g.sub("Escribe la clave y pulsa Entrar. El navegador la recuerda para la próxima vez."):
        g.escribir(p.get_by_label("Clave de la Consulta"), "mia_demo_computacion", retardo_ms=70)
        g.clic(p.get_by_role("button", name="Entrar"))
        p.get_by_role("button", name="Todos", exact=True).wait_for()
        g.pausa(1.0)

    with g.sub("A la izquierda eliges los dominios (vienen todos elegidos). Abajo están el modo y el campo de tu pregunta."):
        g.mover(p.locator('input[aria-label="Dominios a consultar"]'))
        g.pausa(1.2)
        g.mover(p.get_by_label("Tu pregunta"))
        g.pausa(1.2)

    with g.sub("En el centro aparece la conversación. Al empezar ves ejemplos de preguntas que puedes tocar."):
        g.mover(p.get_by_text("Pregunta sobre los documentos de tu programa"))
        g.pausa(1.5)

    with g.sub("Arriba a la derecha cambias la apariencia: modo claro, modo oscuro o el del sistema."):
        g.clic(p.locator("label:visible").filter(has=p.get_by_text("Modo oscuro")))  # el rótulo oculto de la opción
        g.pausa(2.0)
        g.clic(p.locator("label:visible").filter(has=p.get_by_text("Modo claro")))
        g.pausa(1.2)

    with g.sub("El botón de la esquina oculta o muestra el menú lateral cuando necesitas más espacio."):
        g.clic(p.get_by_role("button", name=re.compile("Ocultar el menú lateral")))
        g.pausa(1.6)
        g.clic(p.get_by_role("button", name=re.compile("Mostrar el menú lateral")))
        g.pausa(1.0)

    with g.sub("Si te dan una clave nueva, usa «Cambiar clave». Con «Iniciar sesión» guardas tus conversaciones (video A5)."):
        g.mover(p.get_by_role("button", name="Cambiar clave"))
        g.pausa(1.0)
        g.mover(p.get_by_role("button", name="Iniciar sesión").first)
        g.pausa(1.0)
