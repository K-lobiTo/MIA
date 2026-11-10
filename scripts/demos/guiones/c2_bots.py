"""C2. Bots (número de WhatsApp y artefacto) e imágenes de documentos (alcance global)."""

import re
from pathlib import Path

from grabador import Grabacion

ID = "c2-bots"
TITULO = "Bots e imágenes de documentos"
URL = "http://localhost:3001/#/bots"
STORAGE: dict = {}
IGNORAR_HTTPS = True
SESION_PANEL = "operador@itcr.ac.cr"

DATOS = Path(__file__).resolve().parents[1] / "datos_demo"
DOCUMENTO = "Programa de curso Taller de Ejemplo A.pdf"


def _tarjeta(p, nombre: str):
    return p.get_by_role("article", name=nombre)


def _imagen(g: Grabacion, archivo: str, descripcion: str) -> None:
    p = g.page
    with p.expect_file_chooser() as elegido:
        g.clic(p.get_by_label("Agregar una imagen"))
    elegido.value.set_files(str(DATOS / archivo))
    g.escribir(p.get_by_label("Descripción (opcional)"), descripcion)
    g.clic(p.get_by_role("button", name=re.compile("^Agregar imagen")))


def guion(g: Grabacion) -> None:
    p = g.page
    _tarjeta(p, "Bot de posgrados (sandbox)").wait_for(timeout=30000)
    g.pausa(1.0)

    with g.sub("Un bot es un número de WhatsApp de Kapso que responde con la información de un artefacto."):
        g.mover(p.get_by_role("heading", name="Bots"))
        g.pausa(1.5)

    with g.sub("La tarjeta muestra el artefacto asignado, la memoria y los dominios que el bot ve."):
        g.mover(_tarjeta(p, "Bot de posgrados (sandbox)").locator("dt", has_text="Artefacto"))
        g.pausa(1.2)
        g.mover(_tarjeta(p, "Bot de posgrados (sandbox)").locator("dt", has_text="Dominios que ve"))
        g.pausa(1.5)

    with g.sub("La barra cuenta los mensajes del mes, recibidos y enviados, frente al tope. Al alcanzarlo el bot deja de responder."):
        g.mover(_tarjeta(p, "Bot de posgrados (sandbox)").get_by_role("progressbar"))
        g.pausa(2.5)

    with g.sub("«Registrar bot» da de alta otro número. El identificador es el phone_number_id de Kapso, no el teléfono de nadie."):
        g.clic(p.get_by_role("button", name="Registrar bot"))
        g.escribir(p.get_by_label("Nombre"), "Bot de ejemplo")
        g.escribir(p.get_by_label("Identificador del número de Kapso"), "demo-numero-2")
        g.pausa(0.6)

    with g.sub("Elige el artefacto: sus dominios, su tope diario y su estado son los del bot."):
        g.clic(p.get_by_label("Artefacto asignado").first)
        g.clic(p.get_by_role("option", name="Artefacto del bot de WhatsApp"))
        g.pausa(0.8)
        g.clic(p.get_by_role("button", name="Continuar"))
        p.get_by_text("Confirmar el artefacto del bot").wait_for()
        g.pausa(1.0)

    with g.sub("Antes de guardar, el panel avisa que el bot responde a cualquiera que escriba al número y muestra los dominios que verá."):
        g.mover(p.get_by_text("Este bot responde a cualquiera"))
        g.pausa(3.5)
        g.clic(p.get_by_role("button", name="Confirmar"))
        _tarjeta(p, "Bot de ejemplo").wait_for()
        g.pausa(1.0)

    with g.sub("Cambiar el artefacto o sus dominios cambia lo que el bot sabe desde el mensaje siguiente, sin reiniciar nada."):
        g.clic(_tarjeta(p, "Bot de ejemplo").get_by_role("button", name="Editar"))
        g.pausa(2.5)
        g.clic(p.get_by_role("button", name="Cancelar"))

    with g.sub("«Desactivar» apaga el bot sin borrarlo; «Reactivar» lo enciende. Mientras está apagado responde que no está disponible."):
        g.clic(_tarjeta(p, "Bot de ejemplo").get_by_role("button", name="Desactivar"))
        _tarjeta(p, "Bot de ejemplo").get_by_role("button", name="Reactivar").wait_for()
        g.pausa(2.0)
        g.clic(_tarjeta(p, "Bot de ejemplo").get_by_role("button", name="Reactivar"))
        g.pausa(1.0)

    with g.sub("Los documentos pueden llevar imágenes que el bot envía. Se agregan en el Inventario."):
        g.clic(p.get_by_role("link", name="Inventario de información"))
        buscador = p.get_by_placeholder("Buscar programa, dominio, carpeta o documento")
        buscador.wait_for()
        g.escribir(buscador, "Taller de Ejemplo A")
        p.get_by_label(f"Imágenes de {DOCUMENTO}").wait_for()
        g.pausa(1.0)

    with g.sub("Cada documento tiene un botón «Imágenes» con la cantidad que lleva."):
        g.clic(p.get_by_label(f"Imágenes de {DOCUMENTO}"))
        p.get_by_role("dialog").wait_for()
        g.pausa(1.5)

    with g.sub("Cuando una respuesta se apoya en este documento, el bot envía además sus imágenes, en este orden."):
        g.mover(p.get_by_text("Cuando una respuesta se apoya en este documento"))
        g.pausa(2.5)

    with g.sub("Las imágenes son públicas: cualquiera que tenga el enlace puede verlas. Sube solo lo que pueda ver cualquiera."):
        g.mover(p.get_by_text("Las imágenes son públicas"))
        g.pausa(3.0)

    with g.sub("Elige un archivo PNG o JPG, escribe una descripción (el bot la envía como pie de foto) y agrégala."):
        _imagen(g, "Mapa de ejemplo.png", "Mapa del edificio")
        p.get_by_label("Imagen 1 de 1").wait_for(timeout=20000)
        g.pausa(1.2)

    with g.sub("Puedes agregar varias. Con las flechas cambias el orden."):
        _imagen(g, "Horario de ejemplo.png", "Horario de las clases")
        p.get_by_label("Imagen 2 de 2").wait_for(timeout=20000)
        g.pausa(1.0)
        g.clic(p.get_by_label("Subir la imagen 2"))
        g.pausa(1.5)

    with g.sub("El bot envía por defecto una imagen por respuesta: la primera de la lista. Por eso el orden importa."):
        g.mover(p.get_by_label("Imagen 1 de 2"))
        g.pausa(2.5)

    with g.sub("«Reemplazar» cambia el archivo y «Quitar» la elimina, con confirmación: su enlace anterior deja de funcionar."):
        g.clic(p.get_by_label("Imagen 2 de 2").get_by_role("button", name="Quitar"))
        g.pausa(2.5)
        g.clic(p.get_by_role("dialog").get_by_role("button", name="Cancelar"))
        g.pausa(0.8)
        g.clic(p.get_by_role("dialog").get_by_role("button", name="Cerrar", exact=True))
        g.pausa(0.8)
