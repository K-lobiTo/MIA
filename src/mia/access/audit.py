"""Registro de quién hizo cada escritura de administración: una línea JSON por el logger `mia.admin`
(sin tabla; en Railway queda en los logs del servicio). Solo recibe ids y nombres: nunca tokens, la
clave de automatización ni claves de artefacto."""

import json
import logging
import sys
from datetime import UTC, datetime


class _StdoutHandler(logging.StreamHandler):
    """Escribe en la salida estándar vigente (así también la captura quien la redirige)."""

    def __init__(self):
        super().__init__()

    @property
    def stream(self):
        return sys.stdout

    @stream.setter
    def stream(self, value):
        pass


logger = logging.getLogger("mia.admin")
logger.setLevel(logging.INFO)
logger.propagate = False
if not logger.handlers:
    _handler = _StdoutHandler()
    _handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(_handler)


def log_write(principal, action: str, target: str = "", detail: str = "", result: str = "ok") -> None:
    """`principal.label` es el correo o "automatizacion". `result` es "ok" o "rechazado"."""
    logger.info(
        json.dumps(
            {
                "ts": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "actor": principal.label,
                "action": action,
                "target": target,
                "detail": detail,
                "result": result,
            },
            ensure_ascii=False,
        )
    )
