"""Registro del servicio: una línea JSON por mensaje procesado, en la salida estándar (la recoge Railway).

Nunca incluye teléfonos, identificadores de usuario, el texto de la pregunta ni el de la respuesta. El identificador de
mensaje solo con sus primeros 12 caracteres, y el número de la institución (`number_id`, que no es dato de una persona)
solo cuando hace falta para descubrirlo (`bot_desconocido`). Ver contracts/servicio-whatsapp.md, "Registro del servicio".
"""

import json
import logging
import sys

logger = logging.getLogger("mia_whatsapp")


class _StdoutHandler(logging.StreamHandler):
    """Escribe en la salida estándar vigente (así también la captura quien la redirige, como las pruebas)."""

    def __init__(self):
        super().__init__()

    @property
    def stream(self):
        return sys.stdout

    @stream.setter
    def stream(self, value):
        pass


if not logger.handlers:
    _handler = _StdoutHandler()
    _handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


def log_result(
    resultado: str,
    ms: int,
    mensajes_enviados: int = 0,
    imagenes: int = 0,
    number_id: str | None = None,
    message_id: str | None = None,
) -> None:
    line: dict = {
        "evento": "mensaje",
        "resultado": resultado,
        "ms": ms,
        "mensajes_enviados": mensajes_enviados,
        "imagenes": imagenes,
    }
    if number_id:
        line["number_id"] = number_id
    if message_id:
        line["message_id"] = message_id[:12]
    print(json.dumps(line, ensure_ascii=False), flush=True)
