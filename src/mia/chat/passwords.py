"""Contraseñas y nombres de usuario de la Consulta (feature 015, research R1).

La contraseña se guarda como `scrypt$n$r$p$sal$hash` (`hashlib.scrypt`, biblioteca estándar): lento y con uso de memoria a
propósito, con una sal propia por contraseña. Los parámetros van en el propio texto, así se pueden endurecer después sin
invalidar las contraseñas existentes (`needs_rehash`). Nunca se devuelve ni se escribe en ningún registro."""

import base64
import binascii
import hashlib
import hmac
import re
import secrets

from mia.config import settings

SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1
KEY_BYTES = 32
SALT_BYTES = 16
GENERATED_CHARS = 16

USERNAME_PATTERN = re.compile(r"^[a-z0-9._-]{3,40}$")
USERNAME_RULE = "El usuario tiene de 3 a 40 caracteres: letras minúsculas sin tilde, números, punto, guion y guion bajo."


def _derive(password: str, salt: bytes, n: int, r: int, p: int) -> bytes:
    # maxmem = 128 * n * r * 2 deja margen sobre lo que pide scrypt (128 * n * r) para cualquier n guardado.
    return hashlib.scrypt(
        password.encode(), salt=salt, n=n, r=r, p=p, dklen=KEY_BYTES, maxmem=256 * n * r + 1_048_576
    )


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(SALT_BYTES)
    key = _derive(password, salt, SCRYPT_N, SCRYPT_R, SCRYPT_P)
    return "$".join(
        [
            "scrypt",
            str(SCRYPT_N),
            str(SCRYPT_R),
            str(SCRYPT_P),
            base64.b64encode(salt).decode(),
            base64.b64encode(key).decode(),
        ]
    )


def _parse(stored: str) -> tuple[int, int, int, bytes, bytes] | None:
    parts = (stored or "").split("$")
    if len(parts) != 6 or parts[0] != "scrypt":
        return None
    try:
        n, r, p = int(parts[1]), int(parts[2]), int(parts[3])
        salt = base64.b64decode(parts[4], validate=True)
        key = base64.b64decode(parts[5], validate=True)
    except (ValueError, binascii.Error):
        return None
    if n < 2 or n & (n - 1) or r < 1 or p < 1 or not salt or not key:
        return None
    return n, r, p, salt, key


def verify_password(password: str, stored: str) -> bool:
    """Si la contraseña corresponde al hash guardado, con los parámetros del propio hash. Un hash mal formado es falso."""
    parsed = _parse(stored)
    if parsed is None:
        return False
    n, r, p, salt, key = parsed
    try:
        candidate = _derive(password, salt, n, r, p)
    except (ValueError, MemoryError):
        return False
    return hmac.compare_digest(candidate, key)


def needs_rehash(stored: str) -> bool:
    """Si el hash guardado usa parámetros distintos a los vigentes (o no se entiende) y conviene volver a guardarlo."""
    parsed = _parse(stored)
    return parsed is None or parsed[:3] != (SCRYPT_N, SCRYPT_R, SCRYPT_P)


def generate_password() -> str:
    """Una contraseña aleatoria de 16 caracteres que cumple el mínimo."""
    return secrets.token_urlsafe(GENERATED_CHARS)[:GENERATED_CHARS]


def validate_password(text: str) -> str | None:
    """El motivo por el que la contraseña no sirve, o None si cumple (largo mínimo y no solo espacios)."""
    minimum = settings.password_min_chars
    if not text or not text.strip():
        return "La contraseña no puede estar vacía."
    if len(text) < minimum:
        return f"La contraseña tiene al menos {minimum} caracteres."
    return None


def normalize_username(text: str) -> str:
    return (text or "").strip().lower()


def validate_username(text: str) -> str | None:
    """El motivo por el que el nombre (ya normalizado) no sirve, o None si cumple."""
    return None if USERNAME_PATTERN.fullmatch(text or "") else USERNAME_RULE


# Hash de relleno: verificar contra él cuando el usuario no existe iguala el trabajo (y el tiempo) con el de un usuario real.
DUMMY_HASH = hash_password(secrets.token_urlsafe(24))
