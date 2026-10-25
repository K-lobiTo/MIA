"""El flujo de cada mensaje: el orden de las decisiones del bot (contracts/servicio-whatsapp.md, "Qué hace con cada mensaje").

Es la única pieza que decide el orden; el resto (formato, cliente de Kapso, cliente de la API, estado) son piezas aparte.
`handle_message` nunca lanza: un error inesperado se registra como `error_interno`. Cada mensaje termina en una línea del
registro con su resultado, sin datos de la persona.
"""

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass

from mia_whatsapp.api_client import ImageRef, MiaApiClient
from mia_whatsapp.config import Settings
from mia_whatsapp.format import compose_text, split_message
from mia_whatsapp.kapso import KapsoClient
from mia_whatsapp.logs import log_result
from mia_whatsapp.state import State
from mia_whatsapp.webhook import IncomingMessage

logger = logging.getLogger("mia_whatsapp")


@dataclass
class Deps:
    settings: Settings
    state: State
    api: MiaApiClient
    kapso: KapsoClient
    clock: Callable[[], float] = time.monotonic


@dataclass
class Outcome:
    resultado: str
    sent: int = 0
    images: int = 0
    # Solo para `bot_desconocido`: el número de la institución, para descubrir el phone_number_id del sandbox.
    number_id: str | None = None


def _with_greeting(text: str, greeting: str | None) -> str:
    return f"{greeting.strip()}\n\n{text}" if greeting and greeting.strip() else text


async def _count_sent(deps: Deps, message: IncomingMessage, sent: int) -> None:
    """Suma a la cuota del mes lo realmente enviado. Un fallo de la API aquí no deshace lo ya enviado."""
    if sent > 0:
        await deps.api.count_messages(message.number_id, sent=sent)


async def _respond(
    deps: Deps,
    message: IncomingMessage,
    resultado: str,
    text: str,
    *,
    greeted: bool,
    images: list[ImageRef] | None = None,
) -> Outcome:
    """Envía `text` (partido en varios mensajes si hace falta), luego las imágenes y cuenta lo enviado. `greeted` es si el
    texto ya lleva el saludo: solo se marca a la persona como saludada si el primer envío tuvo éxito. Un fallo de una imagen
    no afecta al texto ya enviado ni a las demás imágenes: se registra como `imagen_fallida`."""
    if message.destination is None:
        return Outcome("sin_destino")
    sent = 0
    for part in split_message(text):
        result = await deps.kapso.send_text(message.number_id, message.destination, part)
        if not result.ok:
            await _count_sent(deps, message, sent)
            return Outcome("error_envio", sent=sent)
        sent += 1
        if sent == 1 and greeted:
            deps.state.mark_greeted(message.person_key)
    images_sent = 0
    image_failed = False
    for image in (images or [])[: deps.settings.bot_max_images]:
        result = await deps.kapso.send_image(
            message.number_id, message.destination, deps.settings.mia_api_url + image.url, image.caption
        )
        if result.ok:
            images_sent += 1
            sent += 1
        else:
            image_failed = True
    await _count_sent(deps, message, sent)
    return Outcome("imagen_fallida" if image_failed else resultado, sent=sent, images=images_sent)


async def _process(deps: Deps, message: IncomingMessage) -> Outcome:
    settings = deps.settings

    # 1. Duplicado: Kapso reintenta hasta 3 veces el mismo aviso.
    duplicate = deps.state.seen(message.message_id)
    if message.idempotency_key:
        duplicate = deps.state.seen(f"key:{message.idempotency_key}") or duplicate
    if duplicate:
        return Outcome("duplicado")

    # 2. Se cuenta el mensaje recibido y se pregunta el estado del bot.
    count = await deps.api.count_messages(message.number_id, received=1)
    if count.status == "unknown_bot":
        return Outcome("bot_desconocido", number_id=message.number_id)
    if count.status == "error":
        return Outcome("error_api")
    if count.status == "cap_reached":
        # Con el tope mensual alcanzado no se envía ni un mensaje más, ni siquiera un aviso.
        return Outcome("tope_mensual")

    # 3. Límite por persona: pasado el límite no se procesa nada más suyo hasta que pase la ventana, y solo se le avisa una
    # vez. El aviso no lleva el saludo (no es una respuesta a su pregunta).
    allowance = deps.state.allow(message.person_key)
    if not allowance.allowed:
        if allowance.notify:
            return await _respond(deps, message, "limite", settings.bot_text_rate_limit, greeted=False)
        return Outcome("limite_en_curso")

    greeting = settings.bot_text_greeting if deps.state.needs_greeting(message.person_key) else None

    # 4. Bot desactivado, sin artefacto o con el artefacto desactivado.
    if count.status == "disabled":
        return await _respond(
            deps, message, "no_disponible", _with_greeting(settings.bot_text_unavailable, greeting), greeted=bool(greeting)
        )

    # 5 y 6. Lo que no es una pregunta de texto razonable no llega a la API (sin gasto de modelo).
    question = (message.text or "").strip() if message.type == "text" else ""
    if not question:
        return await _respond(
            deps, message, "no_texto", _with_greeting(settings.bot_text_not_text, greeting), greeted=bool(greeting)
        )
    if len(question) > settings.bot_max_question_chars:
        return await _respond(
            deps, message, "muy_largo", _with_greeting(settings.bot_text_too_long, greeting), greeted=bool(greeting)
        )

    # 7 y 8. Consulta a MIA con el artefacto del bot, con un lugar en la cola de consultas simultáneas: lo que llega con la
    # cola llena se descarta sin responder.
    if not await deps.state.gate.enter():
        return Outcome("descartado")
    try:
        result = await deps.api.query(message.number_id, question)
    finally:
        deps.state.gate.leave()
    if result.kind == "unknown_bot":
        return Outcome("bot_desconocido", number_id=message.number_id)
    if result.kind == "unavailable":
        return await _respond(
            deps, message, "no_disponible", _with_greeting(settings.bot_text_unavailable, greeting), greeted=bool(greeting)
        )
    if result.kind == "no_info":
        return await _respond(
            deps, message, "sin_informacion", _with_greeting(settings.bot_text_no_info, greeting), greeted=bool(greeting)
        )

    # 9. Respuesta: saludo, texto y fuentes en un solo mensaje (cada mensaje cuenta para la cuota).
    text = compose_text(result.answer, result.sources, greeting)
    return await _respond(deps, message, "respondido", text, greeted=bool(greeting), images=result.images)


async def handle_message(message: IncomingMessage, deps: Deps) -> None:
    started = deps.clock()
    outcome = Outcome("error_interno")
    try:
        outcome = await _process(deps, message)
    except Exception:
        logger.exception("Error inesperado al procesar un mensaje")
    finally:
        log_result(
            outcome.resultado,
            int((deps.clock() - started) * 1000),
            mensajes_enviados=outcome.sent,
            imagenes=outcome.images,
            number_id=outcome.number_id,
            message_id=message.message_id,
        )
