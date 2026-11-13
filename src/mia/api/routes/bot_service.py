"""Rutas para el servicio del bot de WhatsApp (feature 011): POST /bot/messages y POST /bot/query.

Las llama `mia-whatsapp` con la credencial de servicio (`X-Bot-Service-Key`), no el panel ni los artefactos. Cada
llamada trae el `number_id` (el `phone_number_id` de Kapso, el número de la institución, nunca el de una persona) y la
API resuelve el bot y su artefacto asignado. Contrato en specs/011-bot-whatsapp-kapso/contracts/bot-servicio-api.md.
"""

import json
import logging
import time
import uuid
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, StringConstraints, model_serializer
from sqlalchemy.orm import Session

from mia.access.permissions import allowed_modes, configured_domain_ids
from mia.api.routes.query import NO_INFO_ANSWER, QueryRequest, QueryResponse, run_query
from mia.api.security import require_bot_service
from mia.bots.status import bot_state, effective_context_turns, find_bot_by_number
from mia.bots.usage import add_messages, current_month
from mia.config import settings
from mia.contacts import store as contacts_store
from mia.contacts.phone import InvalidPhone, normalize_phone
from mia.rag.completeness import switch_enabled
from mia.rag.modes import mode_available
from mia.rag.programs import ClarifyPolicy, QueryExtras
from mia.storage.db import get_session
from mia.storage.models import Artifact, Bot, QueryLog

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/bot", tags=["bot"], dependencies=[Depends(require_bot_service)])

# El bot siempre pide el modo literal (uso masivo: el más barato), aunque el artefacto asignado permita razonamiento.
BOT_MODE = "literal"
# `QueryRequest` exige al menos un dominio; este valor nunca llega a la búsqueda (ver `bot_query`).
NO_DOMAINS = "sin-dominios"

NumberId = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]


class BotMessages(BaseModel):
    number_id: NumberId
    received: int = Field(default=0, ge=0, le=100)
    sent: int = Field(default=0, ge=0, le=100)
    # El teléfono de la persona, tal como llegó (feature 017); solo con `BOT_CONTACT=on` en el servicio. Se normaliza aquí.
    phone: str | None = Field(default=None, max_length=32)


class ContactState(BaseModel):
    """El estado del contacto de una persona: nunca su nombre ni su correo, solo si existen."""

    status: Literal["pendiente", "invitada", "entrego", "declino"]
    email_retried: bool
    has_name: bool
    has_email: bool


class BotMessagesOut(BaseModel):
    status: Literal["ok", "disabled", "cap_reached", "unknown_bot"]
    month: str
    month_messages: int | None
    month_cap: int | None
    # Las vueltas que recuerda el bot (de 1 a 10); nulo si el número no tiene bot (feature 014).
    context_turns: int | None = None
    # El contacto de quien escribió (feature 017); nulo sin `phone`, con un teléfono inválido o si falló la parte de contactos.
    contact: ContactState | None = None

    @model_serializer(mode="wrap")
    def _without_empty_contact(self, handler):
        """Sin contacto la respuesta es exactamente la de antes de la feature 017 (el campo no aparece): así las pruebas y los
        clientes de la 011 no cambian (SC-007). Quien lee `contact` ausente lo trata igual que nulo."""
        data = handler(self)
        if data.get("contact") is None:
            data.pop("contact", None)
        return data


class ContactEvent(BaseModel):
    """Un evento sobre el contacto de una persona. `phone`, `name` y `email` se validan en el almacén (así ningún mensaje de
    error repite lo recibido); `number_id` no es un dato personal."""

    number_id: NumberId
    phone: str
    event: Literal["claim_invite", "release_invite", "provided", "email_retry", "declined", "erase", "reopen"]
    name: str | None = None
    email: str | None = None


class ContactEventOut(BaseModel):
    claimed: bool
    had_data: bool
    contact: ContactState


class BotQuery(BaseModel):
    number_id: NumberId
    question: str = Field(min_length=1, max_length=2000)


class BotQueryResponse(QueryResponse):
    """La respuesta de `QueryResponse` más lo que el servicio del bot necesita para la aclaración (feature 013):
    `clarify` son los programas candidatos cuando la pregunta es ambigua entre programas (con `no_info` verdadero) y
    `programs` los programas de los documentos citados en una respuesta. `POST /query` no los tiene."""

    clarify: list[str] = Field(default_factory=list)
    programs: list[str] = Field(default_factory=list)


@router.post("/messages", response_model=BotMessagesOut)
def bot_messages(payload: BotMessages, session: Session = Depends(get_session)) -> BotMessagesOut:
    """Cuenta mensajes del mes de un bot y dice en qué estado está. Se suma **antes** de calcular el estado, así el
    mensaje que alcanza el tope ya lo ve alcanzado. Un número sin bot no suma nada."""
    month = current_month()
    bot = find_bot_by_number(session, payload.number_id)
    if bot is None:
        return BotMessagesOut(status="unknown_bot", month=month, month_messages=None, month_cap=None)
    if payload.received or payload.sent:
        add_messages(session, bot.id, month, payload.received, payload.sent)
    state = bot_state(session, bot, month)
    return BotMessagesOut(
        status=state.status,
        month=month,
        month_messages=state.usage.total,
        month_cap=state.cap,
        context_turns=effective_context_turns(bot),
        contact=_contact_of(session, bot, payload.phone) if payload.phone else None,
    )


def _contact_of(session: Session, bot: Bot, raw_phone: str) -> ContactState | None:
    """El contacto de la persona (se crea `pendiente` si es nuevo). Una falla de contactos NUNCA cambia el estado ni hace
    fallar la ruta (FR-025): se registra solo el tipo de la excepción, sin datos personales, y devuelve None."""
    try:
        phone = normalize_phone(raw_phone)
    except InvalidPhone:
        return None
    try:
        contact = contacts_store.get_or_create(session, bot.id, phone)
        contacts_store.touch(session, contact)
        return ContactState(**contacts_store.state_of(contact))
    except Exception as error:  # noqa: BLE001 - la función de contactos falla en silencio hacia el comportamiento anterior
        session.rollback()
        logger.warning("Falló la lectura del contacto: %s", type(error).__name__)
        return None


@router.put("/contacts", response_model=ContactEventOut)
def bot_contacts(payload: ContactEvent, session: Session = Depends(get_session)):
    """Aplica un evento al contacto de una persona (contracts/bot-contactos-api.md). Nunca repite en un error el teléfono, el
    nombre ni el correo recibidos."""
    bot = find_bot_by_number(session, payload.number_id)
    if bot is None:
        raise HTTPException(status_code=404, detail="Bot no encontrado.")
    try:
        phone = normalize_phone(payload.phone)
        result = contacts_store.apply_event(
            session, bot.id, phone, payload.event, name=payload.name, email=payload.email
        )
    except (InvalidPhone, contacts_store.InvalidData) as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    except contacts_store.ContactNotFound:
        raise HTTPException(status_code=404, detail="Contacto no encontrado.") from None
    except contacts_store.InvalidTransition as error:
        return JSONResponse(
            status_code=409, content={"detail": "El evento no aplica al estado actual.", "status": error.status}
        )
    return ContactEventOut(
        claimed=result.claimed, had_data=result.had_data, contact=ContactState(**contacts_store.state_of(result.contact))
    )


@router.post("/query", response_model=BotQueryResponse)
def bot_query(payload: BotQuery, session: Session = Depends(get_session)) -> BotQueryResponse:
    """Consulta con el artefacto asignado al bot, siempre en modo literal. Es la misma consulta que `POST /query`
    (`run_query`): mismos rechazos, topes diarios, citas y registro en Uso, con el artefacto asignado."""
    bot = find_bot_by_number(session, payload.number_id)
    if bot is None:
        raise HTTPException(status_code=404, detail="Bot no encontrado.")
    if not bot.active:
        raise HTTPException(status_code=403, detail="El bot está desactivado.")
    artifact = session.get(Artifact, bot.artifact_id) if bot.artifact_id else None
    if artifact is None:
        raise HTTPException(status_code=403, detail="El bot no tiene artefacto asignado.")

    # Los dominios los decide la API, en cada consulta: un cambio de artefacto o de accesos rige desde la siguiente.
    domains = sorted(configured_domain_ids(session, artifact))
    if not domains and artifact.active and BOT_MODE in allowed_modes(artifact) and mode_available(BOT_MODE)[0]:
        return _no_domains_response(session, artifact.id, payload.question)
    request = QueryRequest(domains=domains or [NO_DOMAINS], question=payload.question, mode=BOT_MODE)
    # Con BOT_CLARIFY encendida (feature 013) una pregunta sin resultados puede volver con los programas candidatos.
    policy = (
        ClarifyPolicy(
            settings.bot_clarify_min_similarity, settings.bot_clarify_max_programs, settings.bot_clarify_candidates
        )
        if switch_enabled(settings.bot_clarify, "BOT_CLARIFY")
        else None
    )
    # Con la opción apagada no se pide nada extra: la respuesta es exactamente la de antes (`clarify` y `programs` vacíos).
    extras = QueryExtras() if policy is not None else None
    result = run_query(request, artifact, session, clarify=policy, extras=extras)
    if extras is None:
        return BotQueryResponse(**result.model_dump())
    return BotQueryResponse(**result.model_dump(), clarify=extras.clarify, programs=extras.programs)


def _no_domains_response(session: Session, artifact_id: str, question: str) -> BotQueryResponse:
    """El artefacto no cubre ningún dominio (por ejemplo, un programa sin dominios): no hay dónde buscar. Responde
    "sin información" sin gastar nada y deja la consulta en Uso."""
    started = time.perf_counter()
    log = QueryLog(
        id=str(uuid.uuid4()),
        artifact_id=artifact_id,
        question=question,
        domain_ids=json.dumps([]),
        mode=BOT_MODE,
        cost_usd=Decimal(0),
        outcome="no_info",
        reject_reason="El artefacto no cubre ningún dominio",
        latency_ms=int((time.perf_counter() - started) * 1000),
    )
    session.add(log)
    session.commit()
    return BotQueryResponse(
        id=log.id, answer=NO_INFO_ANSWER, sources=[], mode=BOT_MODE, latency_ms=log.latency_ms or 0, no_info=True
    )
