import hashlib
import hmac
import secrets

from mia.config import settings

KEY_PREFIX = "mia_"


def generate_key() -> str:
    return KEY_PREFIX + secrets.token_urlsafe(32)


def hash_key(key: str) -> str:
    """SHA-256 de la clave. Alcanza porque la clave es aleatoria de 256 bits: los hashes lentos
    (bcrypt, argon2) son para contraseñas que elige una persona y solo sumarían latencia."""
    return hashlib.sha256(key.encode()).hexdigest()


def key_prefix(key: str) -> str:
    """Comienzo de la clave, lo único que se muestra después de crearla."""
    return key[:8]


def admin_key_matches(given: str) -> bool:
    if not settings.admin_key:
        return False
    return hmac.compare_digest(given.encode(), settings.admin_key.encode())
