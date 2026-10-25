"""Configuración del servicio del bot de WhatsApp (variables de entorno y textos fijos).

Todas las variables y sus rangos están en specs/011-bot-whatsapp-kapso/contracts/servicio-whatsapp.md. Las cuatro
obligatorias, vacías o ausentes, impiden arrancar con un mensaje que nombra la variable; un valor numérico fuera de
rango también. El tope mensual de mensajes y el tamaño máximo de imagen NO están aquí: son de la API.
"""

import re
from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_TEXT_GREETING = (
    "Hola, soy un asistente automático de los posgrados. Respondo con base en documentos oficiales. "
    "Tus preguntas pasan por WhatsApp (Meta), Kapso y un proveedor de modelos de lenguaje. "
    "Por favor no envíes datos personales."
)
DEFAULT_TEXT_NO_INFO = (
    "No encontré esa información en los documentos. Prueba con otras palabras o pregunta por otro tema, "
    "por ejemplo matrícula, requisitos o plan de estudios."
)
DEFAULT_TEXT_UNAVAILABLE = "Ahora mismo no puedo responder. Intenta de nuevo más tarde."
DEFAULT_TEXT_RATE_LIMIT = "Enviaste muchos mensajes seguidos. Intenta de nuevo en un rato."
DEFAULT_TEXT_NOT_TEXT = "Por ahora solo entiendo mensajes de texto. Escribe tu pregunta, por favor."
DEFAULT_TEXT_TOO_LONG = "Tu mensaje es muy largo. Resúmelo en una o dos frases, por favor."


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Obligatorias: sin valor el servicio no arranca.
    mia_api_url: str = Field(min_length=1)
    bot_service_key: str = Field(min_length=1)
    kapso_api_key: str = Field(min_length=1)
    kapso_webhook_secret: str = Field(min_length=1)

    kapso_api_url: str = "https://api.kapso.ai/meta/whatsapp/v24.0"

    bot_max_messages_per_hour: int = Field(default=10, ge=1, le=1000)
    bot_max_messages_per_day: int = Field(default=30, ge=1, le=10000)
    bot_max_question_chars: int = Field(default=500, ge=10, le=2000)
    bot_max_concurrent_queries: int = Field(default=5, ge=1, le=50)
    bot_queue_size: int = Field(default=20, ge=0, le=1000)
    bot_max_images: int = Field(default=1, ge=0, le=10)
    bot_greeting_hours: int = Field(default=24, ge=1, le=168)
    bot_query_timeout_s: int = Field(default=30, ge=1, le=120)
    bot_kapso_rate_per_min: int = Field(default=90, ge=1, le=100)
    bot_seen_ttl_hours: int = Field(default=24, ge=1, le=168)

    bot_text_greeting: str = DEFAULT_TEXT_GREETING
    bot_text_no_info: str = DEFAULT_TEXT_NO_INFO
    bot_text_unavailable: str = DEFAULT_TEXT_UNAVAILABLE
    bot_text_rate_limit: str = DEFAULT_TEXT_RATE_LIMIT
    bot_text_not_text: str = DEFAULT_TEXT_NOT_TEXT
    bot_text_too_long: str = DEFAULT_TEXT_TOO_LONG

    @field_validator("mia_api_url", "kapso_api_url")
    @classmethod
    def _without_trailing_slash(cls, value: str) -> str:
        return value.strip().rstrip("/")


@lru_cache
def get_settings() -> Settings:
    return Settings()


# Lo que delata un contacto en un texto: un correo, un enlace o un teléfono (7 o más dígitos, con o sin separadores).
_CONTACT = re.compile(r"@|https?:|www\.|\d(?:[\s().+-]*\d){6,}", re.IGNORECASE)

_TEXT_FIELDS = {
    "BOT_TEXT_GREETING": "bot_text_greeting",
    "BOT_TEXT_NO_INFO": "bot_text_no_info",
    "BOT_TEXT_UNAVAILABLE": "bot_text_unavailable",
    "BOT_TEXT_RATE_LIMIT": "bot_text_rate_limit",
    "BOT_TEXT_NOT_TEXT": "bot_text_not_text",
    "BOT_TEXT_TOO_LONG": "bot_text_too_long",
}


def contact_warnings(settings: Settings) -> list[str]:
    """Los textos fijos (por el nombre de su variable) que parecen traer un contacto: el bot no da el contacto del
    programa (FR-017). Se usa al arrancar para avisar si alguien cambió un texto por variable; no impide arrancar."""
    return [name for name, field in _TEXT_FIELDS.items() if _CONTACT.search(getattr(settings, field))]
