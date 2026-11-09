"""B5. Artefactos y accesos: crear un artefacto, su clave, y editar, desactivar o regenerar."""

import re

from grabador import Grabacion

ID = "b5-artefactos"
TITULO = "Artefactos y accesos"
URL = "http://localhost:3001/#/artefactos"
STORAGE: dict = {}
IGNORAR_HTTPS = True
SESION_PANEL = "coord.comp@itcr.ac.cr"

NOMBRE = "Consulta de ejemplo"


def _tarjeta(p, nombre: str):
    return p.get_by_role("article", name=nombre)


def _marcar(g: Grabacion, casilla) -> None:
    if not casilla.is_checked():
        g.clic(casilla)


def guion(g: Grabacion) -> None:
    p = g.page
    _tarjeta(p, "Consulta Postgrados de Computación").wait_for()
    g.pausa(1.0)

    with g.sub("Un artefacto es una aplicación que consulta a MIA, como la Consulta administrativa. Aquí defines qué puede hacer."):
        g.mover(p.get_by_role("heading", name="Artefactos y accesos"))
        g.pausa(1.5)

    with g.sub("Cada tarjeta muestra su estado, los dominios, los modos, la memoria y el gasto de hoy frente a su tope."):
        g.mover(_tarjeta(p, "Consulta Postgrados de Computación").get_by_text("Gasto de hoy"))
        g.pausa(2.5)

    with g.sub("«Nuevo artefacto» registra otra aplicación. Empieza con su nombre y una descripción."):
        g.clic(p.get_by_role("button", name="Nuevo artefacto"))
        g.escribir(p.get_by_label("Nombre"), NOMBRE)
        g.escribir(p.get_by_label("Descripción"), "Prueba para el personal de la unidad")
        g.pausa(0.5)

    with g.sub("Elige qué información puede consultar: un programa completo, o solo algunos dominios."):
        g.mover(p.get_by_text("Información que puede consultar"))
        g.pausa(1.0)
        _marcar(g, p.get_by_role("checkbox", name=re.compile("^Currículum")))
        _marcar(g, p.get_by_role("checkbox", name=re.compile("^Memoria del Consejo")))
        g.pausa(0.8)

    with g.sub("Elige los modos de respuesta. Cada uno muestra su costo aproximado por consulta."):
        _marcar(g, p.get_by_role("checkbox", name=re.compile("^Literal")))
        _marcar(g, p.get_by_role("checkbox", name=re.compile("^Con razonamiento")))
        g.pausa(1.0)

    with g.sub("Fija un tope de gasto diario en dólares. Al alcanzarlo, el artefacto deja de responder hasta la medianoche."):
        campo = p.get_by_label(re.compile("^Tope total"))
        campo.fill("")
        g.escribir(campo, "0.30")
        g.pausa(1.0)

    with g.sub("Opcionalmente, un tope menor para el modo con razonamiento, que suele costar más."):
        campo = p.get_by_label(re.compile("^Tope menor"))
        g.escribir(campo, "0.10")
        g.pausa(0.8)

    with g.sub("La memoria define cuántas preguntas anteriores recuerda (de 0 a 10) para entender los seguimientos. Más memoria cuesta más."):
        campo = p.get_by_role("textbox", name=re.compile(r"^Memoria de conversación \(vueltas"))
        campo.fill("")
        g.escribir(campo, "2")
        g.pausa(1.0)

    with g.sub("Puedes exigir inicio de sesión: así solo responde a personas con usuario. Déjalo apagado si no lo necesitas."):
        g.mover(p.get_by_text("Exigir inicio de sesión para consultar"))
        g.pausa(1.8)

    with g.sub("Al registrarlo, MIA genera su clave y la muestra una sola vez. Cópiala y entrégala a quien instalará el sitio."):
        g.clic(p.get_by_role("button", name="Registrar artefacto"))
        p.get_by_text("Copia la clave ahora").wait_for()
        g.pausa(1.5)
        g.clic(p.get_by_role("button", name="Copiar clave"))
        g.pausa(1.2)
        g.clic(p.get_by_role("button", name="Ya la guardé"))
        _tarjeta(p, NOMBRE).wait_for()
        g.pausa(0.8)

    with g.sub("Después solo se ve el comienzo de la clave. Si se pierde, hay que regenerarla."):
        g.mover(_tarjeta(p, NOMBRE).locator(".art-key"))
        g.pausa(1.8)

    with g.sub("«Editar» cambia los dominios, los modos, los topes, la memoria y la sesión. Rige desde la consulta siguiente."):
        g.clic(_tarjeta(p, NOMBRE).get_by_role("button", name="Editar"))
        p.get_by_text(f"Editar {NOMBRE}").wait_for()
        g.pausa(2.0)
        g.clic(p.get_by_role("button", name="Cancelar"))

    with g.sub("«Desactivar» detiene el artefacto sin borrarlo. «Reactivar» lo vuelve a encender."):
        g.clic(_tarjeta(p, NOMBRE).get_by_role("button", name="Desactivar"))
        _tarjeta(p, NOMBRE).get_by_text("Desactivado").wait_for()
        g.pausa(1.5)
        g.clic(_tarjeta(p, NOMBRE).get_by_role("button", name="Reactivar"))
        _tarjeta(p, NOMBRE).get_by_text("Activo").wait_for()
        g.pausa(0.8)

    with g.sub("«Regenerar clave» crea una nueva y la anterior deja de funcionar de inmediato: el sitio que la usa debe actualizarse."):
        g.clic(_tarjeta(p, NOMBRE).get_by_role("button", name="Regenerar clave"))
        g.pausa(2.5)
        g.clic(p.get_by_role("dialog").get_by_role("button", name="Regenerar", exact=True))
        p.get_by_text("Clave regenerada").wait_for()
        g.pausa(1.5)
        g.clic(p.get_by_role("button", name="Ya la guardé"))
        g.pausa(0.8)
