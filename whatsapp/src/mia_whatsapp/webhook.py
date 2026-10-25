"""El aviso (webhook) de Kapso: verificación de la firma y lectura del mensaje.

Kapso firma el cuerpo crudo con HMAC-SHA256 y el secreto del webhook, en hexadecimal minúscula, en el encabezado
`X-Webhook-Signature`. Solo se atiende `whatsapp.message.received`. El aviso puede llegar agrupado (`batch: true` con
`data`) y puede no traer el teléfono de la persona (identificadores de usuario): ningún campo de teléfono se da por
seguro. Funciones puras: nunca lanzan ante un aviso malformado. Ver specs/011-bot-whatsapp-kapso/contracts/servicio-whatsapp.md.
"""

import hashlib
import hmac
import json
import secrets
from collections.abc import Mapping
from dataclasses import dataclass, field

EVENT = "whatsapp.message.received"

# Sal aleatoria del proceso: la clave de persona no se puede revertir al teléfono ni con un volcado de memoria, y cambia
# en cada reinicio (reiniciar reinicia los límites por persona, algo aceptado para el prototipo).
_SALT = secrets.token_bytes(16)


@dataclass(frozen=True)
class IncomingMessage:
    message_id: str
    idempotency_key: str | None
    # `phone_number_id` de Kapso: el número de la institución al que escribió la persona.
    number_id: str
    type: str
    text: str | None
    # Hash con sal del identificador de la persona; None si el aviso no trae ninguno.
    person_key: str | None
    # ("to", teléfono) o ("recipient", identificador de usuario); None si no hay a quién responder.
    destination: tuple[str, str] | None


@dataclass
class ParsedEvent:
    messages: list[IncomingMessage] = field(default_factory=list)
    # El cuerpo no se pudo leer como un aviso (no es JSON o no es un objeto).
    unreadable: bool = False
    # Nombre del evento cuando no es el de mensaje recibido ("" si el aviso no trae evento).
    ignored_event: str | None = None


def verify_signature(body: bytes, header: str | None, secret: str) -> bool:
    """La firma es el HMAC-SHA256 hexadecimal del cuerpo crudo. Sin secreto configurado nunca verifica."""
    if not secret or not header:
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected.encode(), header.strip().encode())


def _text(value) -> str | None:
    return value.strip() or None if isinstance(value, str) else None


def _person_key(*identifiers) -> str | None:
    for identifier in identifiers:
        value = _text(identifier)
        if value:
            return hashlib.sha256(_SALT + value.encode()).hexdigest()[:32]
    return None


def _destination(message: Mapping, conversation: Mapping) -> tuple[str, str] | None:
    phone = _text(message.get("from")) or _text(conversation.get("phone_number"))
    if phone:
        return ("to", phone)
    user_id = _text(message.get("from_user_id"))
    return ("recipient", user_id) if user_id else None


def _message_from(item, idempotency_key: str | None) -> IncomingMessage | None:
    if not isinstance(item, dict):
        return None
    message = item.get("message")
    conversation = item.get("conversation")
    if not isinstance(message, dict):
        return None
    conversation = conversation if isinstance(conversation, dict) else {}
    message_id = _text(message.get("id"))
    number_id = _text(item.get("phone_number_id")) or _text(conversation.get("phone_number_id"))
    if not message_id or not number_id:
        return None
    kapso = message.get("kapso")
    if isinstance(kapso, dict) and kapso.get("direction") == "outbound":
        return None
    body = message.get("text")
    return IncomingMessage(
        message_id=message_id,
        idempotency_key=idempotency_key,
        number_id=number_id,
        type=_text(message.get("type")) or "unknown",
        text=body.get("body") if isinstance(body, dict) and isinstance(body.get("body"), str) else None,
        person_key=_person_key(
            message.get("from_user_id"), message.get("from"), conversation.get("phone_number"), conversation.get("id")
        ),
        destination=_destination(message, conversation),
    )


def parse_event(headers: Mapping[str, str], body: bytes) -> ParsedEvent:
    """Los mensajes de un aviso, sin importar las mayúsculas de los encabezados. Nunca lanza."""
    lowered = {k.lower(): v for k, v in headers.items()}
    try:
        payload = json.loads(body.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return ParsedEvent(unreadable=True)
    if not isinstance(payload, dict):
        return ParsedEvent(unreadable=True)

    event = lowered.get("x-webhook-event", "")
    if event != EVENT:
        return ParsedEvent(ignored_event=event)

    data = payload.get("data")
    if payload.get("batch") is True and isinstance(data, list):
        # La clave de idempotencia es de la entrega entera, no de cada mensaje: en un lote solo valen los ids.
        items, key = data, None
    else:
        items, key = [payload], _text(lowered.get("x-idempotency-key"))
    messages = [m for m in (_message_from(item, key) for item in items) if m is not None]
    return ParsedEvent(messages=messages)
