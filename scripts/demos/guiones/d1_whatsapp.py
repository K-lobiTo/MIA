"""D1. Preguntar por WhatsApp: una conversación simulada con los mensajes reales del servicio del bot.

Los textos salen de `datos_demo/whatsapp.json`, que genera `capturar_whatsapp.py` ejecutando el servicio real del bot.
"""

import json
from pathlib import Path

from grabador import Grabacion

ID = "d1-whatsapp"
TITULO = "Preguntar por WhatsApp"
RAIZ = Path(__file__).resolve().parents[1]
URL = (RAIZ / "chat_whatsapp" / "index.html").as_uri()
STORAGE: dict = {}

ESCENAS = {e["id"]: e for e in json.loads((RAIZ / "datos_demo" / "whatsapp.json").read_text(encoding="utf-8"))["escenarios"]}
IMAGEN = (RAIZ / "datos_demo" / "Horario de ejemplo.png").as_uri()


def _recibir(g: Grabacion, id_: str, espera: float = 1.8) -> None:
    """Muestra "escribiendo..." y luego cada mensaje que el bot respondió de verdad en esa escena."""
    p = g.page
    p.evaluate("escena.escribiendo(true)")
    g.pausa(espera)
    p.evaluate("escena.escribiendo(false)")
    for mensaje in ESCENAS[id_]["mensajes"]:
        if mensaje["tipo"] == "texto":
            p.evaluate("t => escena.bot(t)", mensaje["texto"])
        else:
            p.evaluate("([src, pie]) => escena.imagen(src, pie)", [IMAGEN, mensaje["pie"]])
        g.pausa(1.0)


def _enviar(g: Grabacion, id_: str) -> None:
    p = g.page
    g.escribir(p.locator("#entrada"), ESCENAS[id_]["entrada"], retardo_ms=45)
    g.clic(p.locator("#enviar"))
    g.pausa(0.5)


def guion(g: Grabacion) -> None:
    p = g.page
    p.locator("#entrada").wait_for()
    g.pausa(1.0)

    with g.sub("El bot de WhatsApp responde preguntas sobre los documentos de los posgrados. Esta es una conversación simulada con sus mensajes reales."):
        g.pausa(2.0)

    with g.sub("Por ahora funciona solo con el número de pruebas (sandbox). Escribe tu pregunta en un mensaje de texto, de hasta 500 caracteres."):
        _enviar(g, "aclaracion-pregunta")
        _recibir(g, "aclaracion-pregunta")

    with g.sub("La primera respuesta de cada 24 horas trae un saludo: el bot es automático, tus preguntas pasan por Meta, Kapso y un proveedor de modelos, y no debes enviar datos personales."):
        g.pausa(5.5)

    with g.sub("Si la pregunta puede ser de varios programas, el bot te pregunta a cuál te refieres. Responde con el nombre o con su número."):
        _enviar(g, "aclaracion-respuesta")
        _recibir(g, "aclaracion-respuesta")
        g.pausa(1.5)

    with g.sub("Con el programa elegido responde solo con lo que dicen los documentos y termina con las fuentes."):
        g.pausa(3.5)

    with g.sub("Si el documento tiene imágenes, el bot envía la primera después del texto, con su descripción como pie de foto."):
        _enviar(g, "respuesta")
        _recibir(g, "respuesta")
        g.pausa(2.5)

    with g.sub("Si la información no está en los documentos, el bot lo dice y sugiere otros temas."):
        _enviar(g, "sin-informacion")
        _recibir(g, "sin-informacion")
        g.pausa(2.0)

    with g.sub("El bot solo entiende texto: un audio, una imagen o un sticker recibe un aviso."):
        g.clic(p.locator("#audio"))
        _recibir(g, "no-texto", espera=1.2)
        g.pausa(2.0)

    with g.sub("Hay un límite de mensajes por persona: 10 por hora y 30 por día. Al pasarlo, el bot avisa una vez y deja de responder un rato."):
        p.evaluate("escena.nota('Después de varios mensajes seguidos')")
        g.pausa(1.0)
        _enviar(g, "limite")
        _recibir(g, "limite", espera=1.0)
        g.pausa(3.0)

    with g.sub("El bot no entrega teléfonos ni correos de los programas: solo responde con lo que dicen los documentos."):
        g.pausa(3.0)
