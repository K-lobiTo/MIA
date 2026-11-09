"""A5. Cuenta y conversaciones guardadas."""

import re

from grabador import Grabacion

ID = "a5-conversaciones"
TITULO = "Cuenta y conversaciones guardadas"
URL = "http://localhost:3000"
STORAGE = {"mia-consulta-key": "mia_demo_computacion"}
USUARIO = "estudiante.demo"
CLAVE = "ClaveDemo2026"


def _preguntar(g: Grabacion, texto: str, respuesta: str) -> None:
    p = g.page
    g.escribir(p.get_by_label("Tu pregunta"), texto)
    g.tecla("Enter")
    p.get_by_text(respuesta).first.wait_for(timeout=20000)
    g.pausa(1.2)


def guion(g: Grabacion) -> None:
    p = g.page
    # El cambio de contraseña no se ejecuta de verdad: así el video se puede repetir con la misma base.
    g.simular("**/api/auth/password", lambda route, request: route.fulfill(status=204))
    p.get_by_role("button", name="Todos", exact=True).wait_for()
    g.pausa(0.8)

    with g.sub("Con un usuario, MIA guarda tus conversaciones. Te lo crea quien administra MIA: no hay registro propio."):
        g.mover(p.get_by_text("Guarda tus conversaciones"))
        g.pausa(1.2)

    with g.sub("Pulsa «Iniciar sesión»."):
        g.clic(p.get_by_role("button", name="Iniciar sesión").first)
        p.get_by_label("Usuario").wait_for()
        g.pausa(0.8)

    with g.sub("Escribe tu usuario y tu contraseña. Se guardan 90 días sin actividad y las puedes borrar cuando quieras."):
        g.escribir(p.get_by_label("Usuario"), USUARIO)
        g.escribir(p.get_by_label("Contraseña", exact=True), CLAVE)
        g.clic(p.get_by_role("button", name="Iniciar sesión", exact=True))
        p.get_by_role("button", name="Nueva conversación").wait_for()
        g.pausa(1.0)

    with g.sub("Ahora el menú lateral muestra tus conversaciones, la más reciente primero."):
        g.mover(p.get_by_text("Créditos del Taller de Ejemplo A"))
        g.pausa(1.5)

    with g.sub("Toca una para retomarla. Las guardadas muestran la pregunta, la respuesta y los documentos citados."):
        g.clic(p.get_by_text("Créditos del Taller de Ejemplo A"))
        p.get_by_text("El Taller de Ejemplo A tiene 3 créditos.").wait_for()
        g.pausa(1.5)

    with g.sub("Sigue preguntando: la conversación continúa con lo que ya se habló."):
        _preguntar(g, "¿Y cuántas horas extraclase?", "6 horas")

    with g.sub("«Nueva conversación» empieza otra desde cero. Queda guardada con tu primera pregunta como título."):
        g.clic(p.get_by_role("button", name="Nueva conversación"))
        _preguntar(g, "¿Qué requisitos tiene la tesis?", "propuesta aprobada")

    with g.sub("El menú de tres puntos de cada conversación permite renombrarla."):
        g.clic(p.get_by_role("button", name="Opciones de la conversación: Requisitos de la tesis"))
        g.clic(p.get_by_role("menuitem", name="Renombrar"))
        campo = p.get_by_label("Título")
        campo.fill("")
        g.escribir(campo, "Tesis: requisitos")
        g.clic(p.get_by_role("button", name="Guardar", exact=True))
        p.get_by_text("Tesis: requisitos").first.wait_for()
        g.pausa(1.0)

    with g.sub("También permite borrarla. Pide confirmación porque no se puede deshacer."):
        g.clic(p.get_by_role("button", name="Opciones de la conversación: Tesis: requisitos"))
        g.clic(p.get_by_role("menuitem", name="Borrar"))
        g.pausa(1.5)
        g.clic(p.get_by_role("dialog").get_by_role("button", name="Borrar", exact=True))
        g.pausa(1.0)

    with g.sub("«Borrar todas» elimina todo tu historial de una vez."):
        g.mover(p.get_by_role("button", name="Borrar todas"))
        g.pausa(1.2)

    with g.sub("Desde tu nombre cambias la contraseña. Pide la actual y una nueva de al menos 10 caracteres."):
        g.clic(p.get_by_role("button", name="Cuenta"))
        g.clic(p.get_by_role("menuitem", name="Cambiar contraseña"))
        g.escribir(p.get_by_label("Contraseña actual"), CLAVE)
        g.escribir(p.get_by_label("Contraseña nueva"), "OtraClave2026!")
        g.clic(p.get_by_role("button", name="Cambiar contraseña", exact=True))
        p.get_by_text("Contraseña cambiada").wait_for()
        g.pausa(1.5)
        g.clic(p.get_by_role("button", name="Cerrar", exact=True))

    with g.sub("Cuando termines, abre el mismo menú y elige «Cerrar sesión», sobre todo en un equipo compartido."):
        g.clic(p.get_by_role("button", name="Cuenta"))
        g.clic(p.get_by_role("menuitem", name="Cerrar sesión"))
        p.get_by_text("Guarda tus conversaciones").wait_for()
        g.pausa(1.5)
