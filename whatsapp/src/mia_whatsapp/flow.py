"""El flujo de cada mensaje: el orden de las decisiones del bot (contracts/servicio-whatsapp.md, "Qué hace con cada mensaje").

Es la única pieza que decide el orden; el resto (formato, cliente de Kapso, cliente de la API, estado) son piezas aparte.
`handle_message` nunca lanza: un error inesperado se registra como `error_interno`. Cada mensaje termina en una línea del
registro con su resultado, sin datos de la persona.
"""

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass

from mia_whatsapp.api_client import ContactState, ImageRef, MiaApiClient
from mia_whatsapp.clarify import match_candidate, names_several, render_clarify, with_program
from mia_whatsapp.config import Settings
from mia_whatsapp.contacts import read_message, render_retry, render_thanks
from mia_whatsapp.format import compose_text, split_message
from mia_whatsapp.kapso import KapsoClient
from mia_whatsapp.logs import log_result
from mia_whatsapp.state import State, Turn
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
    # Feature 017: solo el nombre del evento de contacto de este mensaje (invitada, entregado...), nunca datos de la persona.
    contacto: str | None = None


@dataclass
class _Contact:
    """Lo que el flujo sabe del contacto de la persona en este mensaje (feature 017). Sin `state` (función apagada, sin
    teléfono real o la API no lo informó) los pasos de contacto no se ejecutan y el bot es el de antes."""

    phone: str | None = None
    state: ContactState | None = None
    # El mensaje pasó el límite por persona y el estado del bot: solo entonces la invitación puede cerrarse o enviarse.
    reached: bool = False
    # Una aclaración de programa estaba pendiente: la respuesta es para ella y la invitación sigue como estaba.
    clarifying: bool = False
    # Los pasos de contacto ya respondieron este mensaje.
    consumed: bool = False


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


# Resultados de un envío que dejan la conversación en el contexto: lo que la persona recibió (aunque una imagen fallara).
_SENT = frozenset({"respondido", "aclaracion", "sin_informacion", "imagen_fallida"})


def _remember(deps: Deps, message: IncomingMessage, question: str, outcome: Outcome, bot_turn: Turn) -> None:
    """Guarda en el contexto la pregunta de la persona y la respuesta del bot, solo si el envío salió bien: un envío fallido
    no deja la conversación a medias (la siguiente pregunta se trata como nueva)."""
    if outcome.resultado in _SENT:
        deps.state.conversations.add_person(message.person_key, question)
        deps.state.conversations.add(message.person_key, bot_turn)


async def _process(deps: Deps, message: IncomingMessage) -> Outcome:
    contact = _Contact()
    outcome = await _flow(deps, message, contact)
    if contact.state is not None and contact.reached and not contact.consumed:
        await _after_response(deps, message, contact, outcome)
    return outcome


async def _flow(deps: Deps, message: IncomingMessage, contact: _Contact) -> Outcome:
    settings = deps.settings

    # 1. Duplicado: Kapso reintenta hasta 3 veces el mismo aviso.
    duplicate = deps.state.seen(message.message_id)
    if message.idempotency_key:
        duplicate = deps.state.seen(f"key:{message.idempotency_key}") or duplicate
    if duplicate:
        return Outcome("duplicado")

    # 2. Se cuenta el mensaje recibido y se pregunta el estado del bot.
    # Con la función de contacto encendida (feature 017) el teléfono real viaja en esta misma llamada; sin ella, la llamada es
    # exactamente la de antes.
    contact.phone = message.phone if settings.bot_contact == "on" else None
    count = await deps.api.count_messages(message.number_id, received=1, phone=contact.phone)
    contact.state = count.contact if contact.phone else None
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

    # 4b. Contacto (feature 017): la respuesta a la invitación, el borrado y la reapertura los atiende el servicio sin consultar a
    # MIA. Antes de la consulta, con los datos de contexto de la 013 (una aclaración pendiente tiene prioridad).
    conversations = deps.state.conversations
    person = message.person_key
    # La memoria del bot cuenta VUELTAS (pregunta y respuesta); un turno es un mensaje, así que una vuelta son 2 turnos
    # (feature 014). Sin el dato (la API no lo informó) rige `BOT_CONTEXT_MESSAGES`. Se lee en cada mensaje: un cambio del
    # panel rige desde el mensaje siguiente, también en conversaciones en curso.
    limit = 2 * count.context_turns if count.context_turns else settings.bot_context_messages
    pending = conversations.pending(person, limit)
    contact.reached = True
    contact.clarifying = pending is not None
    if contact.state is not None and not contact.clarifying and message.type == "text":
        consumed = await _answer_contact(deps, message, contact)
        if consumed is not None:
            return consumed

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

    # 6b. Contexto (feature 013): si el bot acaba de preguntar a qué programa se refiere y la persona nombra exactamente uno,
    # su pregunta original sigue con ese programa. Si no lo nombra (o nombra varios), la aclaración se descarta y el mensaje
    # es una pregunta nueva: máximo una aclaración por pregunta. (`conversations`, `person`, `limit` y `pending` se calculan
    # antes del paso 4b.)
    to_send = question
    chosen: str | None = None
    if pending is not None:
        chosen = match_candidate(question, list(pending.candidates))
        if chosen is not None:
            to_send = with_program(pending.question, chosen)
        elif names_several(question, list(pending.candidates)):
            # Nombra a varios ("las dos"): no se puede decidir. "Sin información", sin consultar y sin volver a preguntar.
            outcome = await _respond(
                deps, message, "sin_informacion", _with_greeting(settings.bot_text_no_info, greeting), greeted=bool(greeting)
            )
            _remember(deps, message, question, outcome, Turn(role="bot", kind="no_info"))
            return outcome

    # 7 y 8. Consulta a MIA con el artefacto del bot, con un lugar en la cola de consultas simultáneas: lo que llega con la
    # cola llena se descarta sin responder. El reintento con el programa recordado usa el mismo lugar.
    if not await deps.state.gate.enter():
        return Outcome("descartado")
    used_program = chosen
    try:
        result = await deps.api.query(message.number_id, to_send)
        # Sin respuesta ni aclaración resuelta, y con un programa de la conversación: se reintenta una vez con él.
        remembered = conversations.remembered_program(person, limit)
        if result.kind in ("no_info", "clarify") and chosen is None and remembered is not None:
            retry = await deps.api.query(message.number_id, with_program(question, remembered))
            if retry.kind == "answer":
                result, used_program = retry, remembered
    finally:
        deps.state.gate.leave()
    if result.kind == "unknown_bot":
        return Outcome("bot_desconocido", number_id=message.number_id)
    if result.kind == "unavailable":
        return await _respond(
            deps, message, "no_disponible", _with_greeting(settings.bot_text_unavailable, greeting), greeted=bool(greeting)
        )
    if result.kind == "clarify" and chosen is None:
        # La pregunta es ambigua entre programas: se pregunta a cuál se refiere (un solo mensaje, cuenta en la cuota).
        text = render_clarify(settings.bot_text_clarify, result.candidates)
        outcome = await _respond(deps, message, "aclaracion", _with_greeting(text, greeting), greeted=bool(greeting))
        _remember(deps, message, question, outcome, Turn(role="bot", kind="clarify", candidates=tuple(result.candidates)))
        return outcome
    if result.kind in ("no_info", "clarify"):
        # Con la pregunta ya aclarada, otra ambigüedad se trata como "sin información": nunca dos aclaraciones.
        outcome = await _respond(
            deps, message, "sin_informacion", _with_greeting(settings.bot_text_no_info, greeting), greeted=bool(greeting)
        )
        _remember(deps, message, question, outcome, Turn(role="bot", kind="no_info"))
        return outcome

    # 9. Respuesta: saludo, texto y fuentes en un solo mensaje (cada mensaje cuenta para la cuota).
    text = compose_text(result.answer, result.sources, greeting)
    outcome = await _respond(deps, message, "respondido", text, greeted=bool(greeting), images=result.images)
    programs = tuple(result.programs) or ((used_program,) if used_program else ())
    _remember(deps, message, question, outcome, Turn(role="bot", kind="answer", programs=programs))
    return outcome


async def _answer_contact(deps: Deps, message: IncomingMessage, contact: _Contact) -> Outcome | None:
    """Paso 4b: si el mensaje es una frase de control o la respuesta a la invitación, lo atiende y devuelve su resultado (no se
    consulta a MIA, no entra al contexto de la 013 y no gasta modelo). None: el mensaje sigue su camino normal. Si guardar en
    la API falla, el mensaje NO se consume (FR-025)."""
    settings = deps.settings
    state = contact.state
    text = (message.text or "").strip()
    if not text or len(text) > settings.bot_max_question_chars:
        return None
    reading = read_message(text, state.status)
    kind = reading.kind
    phone = contact.phone
    api = deps.api

    if kind == "question":
        return None
    if kind == "erase":
        result = await api.put_contact(message.number_id, phone, "erase")
        if not result.ok:
            return None
        reply = settings.bot_text_contact_erased if result.had_data else settings.bot_text_contact_no_data
        return await _contact_reply(deps, message, contact, "contacto_borrado", "borrado", reply)
    if kind == "reopen":
        result = await api.put_contact(message.number_id, phone, "reopen")
        if not result.ok:
            return None
        return await _contact_reply(deps, message, contact, "contacto_reabierto", "reabierto", settings.bot_text_contact_invite)
    if kind == "decline":
        result = await api.put_contact(message.number_id, phone, "declined")
        if not result.ok:
            return None
        return await _contact_reply(
            deps, message, contact, "contacto_declinado", "declinado", settings.bot_text_contact_declined
        )
    if kind == "why":
        return await _contact_reply(deps, message, contact, "contacto_explicado", "explicado", settings.bot_text_contact_why)
    if kind == "provided":
        result = await api.put_contact(message.number_id, phone, "provided", name=reading.name, email=reading.email)
        if not result.ok:
            return None
        reply = render_thanks(settings.bot_text_contact_thanks, reading.name, reading.email)
        return await _contact_reply(deps, message, contact, "contacto_entregado", "entregado", reply)
    if kind == "bad_email":
        if not state.email_retried:
            result = await api.put_contact(message.number_id, phone, "email_retry", name=reading.name)
            if not result.ok:
                return None
            reply = render_retry(settings.bot_text_contact_email_retry)
            return await _contact_reply(deps, message, contact, "contacto_reintento", "reintento", reply)
        # Segundo intento inválido: no se insiste. Si ahora llegó un nombre se guarda; si no, se cierra la invitación.
        if reading.name:
            result = await api.put_contact(message.number_id, phone, "provided", name=reading.name)
            reply = render_thanks(settings.bot_text_contact_thanks, reading.name, None)
            resultado, evento = "contacto_entregado", "entregado"
        else:
            result = await api.put_contact(message.number_id, phone, "declined")
            reply, resultado, evento = settings.bot_text_contact_declined, "contacto_declinado", "declinado"
        if not result.ok:
            return None
        return await _contact_reply(deps, message, contact, resultado, evento, reply)
    return None


async def _contact_reply(
    deps: Deps, message: IncomingMessage, contact: _Contact, resultado: str, evento: str, text: str
) -> Outcome:
    """Responde un mensaje que atendió el flujo de contacto: sin saludo (no es una respuesta a una pregunta) y contando lo
    enviado en la cuota."""
    contact.consumed = True
    outcome = await _respond(deps, message, resultado, text, greeted=False)
    outcome.contacto = evento
    return outcome


# Resultados tras los que se invita: la persona recibió una respuesta a su pregunta (con información o sin ella).
_INVITE_AFTER = frozenset({"respondido", "sin_informacion", "imagen_fallida"})


async def _after_response(deps: Deps, message: IncomingMessage, contact: _Contact, outcome: Outcome) -> None:
    """Paso 10: tras responder, invita a dejar los datos (una sola vez) o cierra la invitación abierta si la persona siguió
    con otra cosa. Nunca lanza ni cambia el resultado del mensaje: una falla de contactos se ignora (FR-025)."""
    try:
        sent_ok = outcome.sent > 0 and outcome.resultado != "error_envio"
        status = contact.state.status
        if status == "invitada" and not contact.clarifying and sent_ok:
            # No contestó la invitación (una pregunta, o un mensaje que no es texto): se da por no aceptada.
            await deps.api.put_contact(message.number_id, contact.phone, "declined")
            return
        if status == "pendiente" and outcome.resultado in _INVITE_AFTER and sent_ok and message.destination is not None:
            claim = await deps.api.put_contact(message.number_id, contact.phone, "claim_invite")
            if not (claim.ok and claim.claimed):
                return
            invite = await _respond(deps, message, "contacto_invitada", deps.settings.bot_text_contact_invite, greeted=False)
            if invite.resultado == "error_envio":
                await deps.api.put_contact(message.number_id, contact.phone, "release_invite")
                return
            outcome.sent += invite.sent
            outcome.contacto = "invitada"
    except Exception:  # noqa: BLE001 - sin traza: nada de contactos puede tumbar ni ensuciar el registro de un mensaje
        logger.warning("Falló el paso de contacto tras responder")


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
            contacto=outcome.contacto,
        )
