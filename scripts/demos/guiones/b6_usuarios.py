"""B6. Usuarios de la Consulta: registrar, entregar la contraseña, restablecerla y desactivar."""

from grabador import Grabacion

ID = "b6-usuarios"
TITULO = "Usuarios de la Consulta"
URL = "http://localhost:3001/#/usuarios"
STORAGE: dict = {}
IGNORAR_HTTPS = True
SESION_PANEL = "coord.comp@itcr.ac.cr"

NUEVO = "asistente.nuevo"


def _tarjeta(p, usuario: str):
    return p.get_by_role("article", name=usuario)


def guion(g: Grabacion) -> None:
    p = g.page
    _tarjeta(p, "estudiante.demo").wait_for()
    g.pausa(1.0)

    with g.sub("Aquí registras a las personas que inician sesión en la Consulta para guardar sus conversaciones."):
        g.mover(p.get_by_role("heading", name="Usuarios de la Consulta"))
        g.pausa(1.5)

    with g.sub("Cada tarjeta muestra su programa, su último acceso y cuántas conversaciones tiene."):
        g.mover(_tarjeta(p, "estudiante.demo").locator("dt", has_text="Conversaciones"))
        g.pausa(2.0)

    with g.sub("Quien administra no puede leer las conversaciones: solo ve cuántas hay y cuándo fue la última."):
        g.mover(p.get_by_text("quien administra no puede leerlas"))
        g.pausa(2.5)

    with g.sub("«Registrar usuario» crea una cuenta. Escribe el nombre de usuario."):
        g.clic(p.get_by_role("button", name="Registrar usuario"))
        g.escribir(p.get_by_role("dialog").get_by_label("Usuario"), NUEVO)
        g.pausa(0.6)

    with g.sub("El programa decide qué cuentas de administración la gestionan. No limita lo que puede consultar."):
        g.mover(p.get_by_text("Decide qué cuentas de administración lo gestionan"))
        g.pausa(2.0)

    with g.sub("La contraseña inicial es opcional: si la dejas vacía, MIA genera una."):
        g.mover(p.get_by_text("Déjala vacía para que se genere una"))
        g.pausa(1.8)
        g.clic(p.get_by_role("dialog").get_by_role("button", name="Registrar", exact=True))
        p.get_by_text("Esta contraseña se muestra una sola vez").wait_for()
        g.pausa(1.0)

    with g.sub("La contraseña se muestra una sola vez. Cópiala y entrégala a la persona; no se podrá volver a ver."):
        g.mover(p.get_by_test_id("contrasena-completa"))
        g.pausa(1.5)
        g.clic(p.get_by_role("button", name="Copiar contraseña"))
        g.pausa(1.0)
        g.clic(p.get_by_role("button", name="Ya la entregué"))
        _tarjeta(p, NUEVO).wait_for()
        g.pausa(0.8)

    with g.sub("Si alguien olvida su contraseña, restablécela. La anterior deja de funcionar y se cierran sus sesiones."):
        g.clic(_tarjeta(p, NUEVO).get_by_role("button", name="Restablecer contraseña"))
        g.pausa(2.5)
        g.clic(p.get_by_role("dialog").get_by_role("button", name="Restablecer", exact=True))
        p.get_by_text("Contraseña restablecida").wait_for()
        g.pausa(1.5)
        g.clic(p.get_by_role("button", name="Ya la entregué"))
        g.pausa(0.6)

    with g.sub("«Desactivar» impide que la persona entre, sin borrar sus datos. «Reactivar» le devuelve el acceso."):
        g.clic(_tarjeta(p, NUEVO).get_by_role("button", name="Desactivar"))
        _tarjeta(p, NUEVO).get_by_role("button", name="Reactivar").wait_for()
        g.pausa(2.0)
        g.clic(_tarjeta(p, NUEVO).get_by_role("button", name="Reactivar"))
        _tarjeta(p, NUEVO).get_by_role("button", name="Desactivar").wait_for()
        g.pausa(1.2)
