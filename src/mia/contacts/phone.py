"""Normalización del teléfono de un contacto: solo dígitos, de 7 a 15, guardado con prefijo `+`."""

import re

_ALLOWED = re.compile(r"[\d\s().\-]+")


class InvalidPhone(ValueError):
    """Teléfono inválido. El mensaje NUNCA repite el valor recibido."""


def normalize_phone(raw: str | None) -> str:
    text = (raw or "").strip().removeprefix("+")
    if not _ALLOWED.fullmatch(text):
        raise InvalidPhone("Teléfono inválido.")
    digits = re.sub(r"\D", "", text)
    if not 7 <= len(digits) <= 15:
        raise InvalidPhone("Teléfono inválido.")
    return "+" + digits
