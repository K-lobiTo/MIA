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
DEFAULT_TEXT_CLARIFY = (
    "¿A qué programa te refieres? Tengo información de:\n{programs}\n"
    "Responde con el nombre del programa o su número."
)
DEFAULT_TEXT_UNAVAILABLE = "Ahora mismo no puedo responder. Intenta de nuevo más tarde."
DEFAULT_TEXT_RATE_LIMIT = "Enviaste muchos mensajes seguidos. Intenta de nuevo en un rato."
DEFAULT_TEXT_NOT_TEXT = "Por ahora solo entiendo mensajes de texto. Escribe tu pregunta, por favor."
DEFAULT_TEXT_TOO_LONG = "Tu mensaje es muy largo. Resúmelo en una o dos frases, por favor."

# Datos de contacto (feature 017). Piden un correo y llevan un ejemplo con "@": por eso NO están en `_TEXT_FIELDS` (la
# advertencia de contactos de programas). `{saved}` y `{example}` los reemplaza el servicio.
DEFAULT_TEXT_CONTACT_INVITE = (
    "Si quieres que la Coordinación del programa te contacte, puedes dejarme tu nombre y tu correo. "
    "Es totalmente opcional: puedes seguir preguntando sin dejarlos. "
    "Guardo tu número de WhatsApp y, si los das, tu nombre y correo, solo para que te contacten sobre los programas; "
    "no los uses dentro de tus preguntas. "
    "Para dejarlos escribe, por ejemplo: Ana Pérez ana@correo.com. "
    "Si no quieres dejarlos, escribe «no». Para borrar tus datos, escribe «borrar mis datos»."
)
DEFAULT_TEXT_CONTACT_THANKS = (
    "Listo, guardé {saved}. Para corregirlo escribe «quiero dejar mis datos»; para borrarlo, «borrar mis datos». "
    "Sigue con tus preguntas cuando quieras."
)
DEFAULT_TEXT_CONTACT_DECLINED = (
    "De acuerdo, no guardé tus datos. Puedes seguir preguntando; si cambias de opinión, escribe «quiero dejar mis datos»."
)
DEFAULT_TEXT_CONTACT_EMAIL_RETRY = (
    "No pude leer tu correo. ¿Puedes escribirlo de nuevo? Por ejemplo: {example}. Si no quieres dejarlo, escribe «no»."
)
DEFAULT_TEXT_CONTACT_WHY = (
    "Pido el nombre y el correo solo para que la Coordinación del programa pueda contactarte si te interesa. "
    "Es opcional, y el bot funciona igual sin ellos. Puedes borrarlos cuando quieras escribiendo «borrar mis datos»."
)
DEFAULT_TEXT_CONTACT_ERASED = "Listo, borré tu nombre y tu correo. No te los volveré a pedir."
DEFAULT_TEXT_CONTACT_NO_DATA = "No tenía tu nombre ni tu correo guardados."


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
    # Contexto de conversación (feature 013): los últimos turnos de cada persona, en memoria, y cuánto se recuerdan.
    bot_context_messages: int = Field(default=4, ge=2, le=10)
    bot_context_minutes: int = Field(default=30, ge=1, le=1440)
    bot_context_max_people: int = Field(default=5000, ge=100, le=100000)
    # Datos de contacto (feature 017): `off` (por defecto) deja el bot exactamente como antes; `on` guarda el teléfono de quien
    # escribe e invita, tras la primera respuesta, a dejar nombre y correo (opcional).
    bot_contact: str = "off"

    bot_text_greeting: str = DEFAULT_TEXT_GREETING
    bot_text_no_info: str = DEFAULT_TEXT_NO_INFO
    bot_text_unavailable: str = DEFAULT_TEXT_UNAVAILABLE
    bot_text_rate_limit: str = DEFAULT_TEXT_RATE_LIMIT
    bot_text_not_text: str = DEFAULT_TEXT_NOT_TEXT
    bot_text_too_long: str = DEFAULT_TEXT_TOO_LONG
    # `{programs}` se reemplaza por la lista numerada de programas candidatos.
    bot_text_clarify: str = DEFAULT_TEXT_CLARIFY
    bot_text_contact_invite: str = DEFAULT_TEXT_CONTACT_INVITE
    # `{saved}` = "tu nombre", "tu correo" o "tu nombre y tu correo" (con el correo enmascarado).
    bot_text_contact_thanks: str = DEFAULT_TEXT_CONTACT_THANKS
    bot_text_contact_declined: str = DEFAULT_TEXT_CONTACT_DECLINED
    # `{example}` = un correo de ejemplo.
    bot_text_contact_email_retry: str = DEFAULT_TEXT_CONTACT_EMAIL_RETRY
    bot_text_contact_why: str = DEFAULT_TEXT_CONTACT_WHY
    bot_text_contact_erased: str = DEFAULT_TEXT_CONTACT_ERASED
    bot_text_contact_no_data: str = DEFAULT_TEXT_CONTACT_NO_DATA

    @field_validator("bot_contact")
    @classmethod
    def _contact_mode(cls, value: str) -> str:
        value = value.strip().lower()
        if value not in ("off", "on"):
            raise ValueError("BOT_CONTACT debe ser 'off' o 'on'")
        return value

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
    "BOT_TEXT_CLARIFY": "bot_text_clarify",
}


def contact_warnings(settings: Settings) -> list[str]:
    """Los textos fijos (por el nombre de su variable) que parecen traer un contacto: el bot no da el contacto del
    programa (FR-017). Se usa al arrancar para avisar si alguien cambió un texto por variable; no impide arrancar."""
    return [name for name, field in _TEXT_FIELDS.items() if _CONTACT.search(getattr(settings, field))]
