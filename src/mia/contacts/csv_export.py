"""CSV de los contactos de WhatsApp (feature 017): BOM UTF-8 para que Excel respete los acentos y neutralización de fórmulas
(la misma del CSV del registro de consultas, incluido el teléfono, que empieza con `+`)."""

import csv
import io

from mia.storage.models import WhatsAppContact
from mia.usage.log import safe_cell

COLUMNS = ["telefono", "bot", "nombre", "correo", "estado", "creado", "ultimo_mensaje", "actualizado"]


def _iso(value) -> str:
    return value.isoformat() + "Z"


def to_csv(contacts: list[WhatsAppContact], bot_names: dict[str, str]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(COLUMNS)
    for c in contacts:
        values = [
            c.phone, bot_names.get(c.bot_id, c.bot_id), c.name, c.email, c.status,
            _iso(c.created_at), _iso(c.last_seen_at), _iso(c.updated_at),
        ]
        writer.writerow([safe_cell(v) for v in values])
    return "﻿" + buffer.getvalue()
