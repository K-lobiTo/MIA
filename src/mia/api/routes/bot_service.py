"""Rutas para el servicio del bot de WhatsApp (feature 011): POST /bot/messages y POST /bot/query.

Las llama `mia-whatsapp` con la credencial de servicio (`X-Bot-Service-Key`), no el panel ni los artefactos. Cada
llamada trae el `number_id` (el `phone_number_id` de Kapso, el número de la institución, nunca el de una persona) y la
API resuelve el bot y su artefacto asignado. Contrato en specs/011-bot-whatsapp-kapso/contracts/bot-servicio-api.md.
"""

import json
import time
import uuid
from decimal import Decimal
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy.orm import Session

from mia.access.permissions import allowed_modes, configured_domain_ids
from mia.api.routes.query import NO_INFO_ANSWER, QueryRequest, QueryResponse, run_query
from mia.api.security import require_bot_service
from mia.bots.status import bot_state, find_bot_by_number
from mia.bots.usage import add_messages, current_month
from mia.rag.modes import mode_available
from mia.storage.db import get_session
from mia.storage.models import Artifact, QueryLog

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


class BotMessagesOut(BaseModel):
    status: Literal["ok", "disabled", "cap_reached", "unknown_bot"]
    month: str
    month_messages: int | None
    month_cap: int | None


class BotQuery(BaseModel):
    number_id: NumberId
    question: str = Field(min_length=1, max_length=2000)


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
    return BotMessagesOut(status=state.status, month=month, month_messages=state.usage.total, month_cap=state.cap)


@router.post("/query", response_model=QueryResponse)
def bot_query(payload: BotQuery, session: Session = Depends(get_session)) -> QueryResponse:
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
    return run_query(request, artifact, session)


def _no_domains_response(session: Session, artifact_id: str, question: str) -> QueryResponse:
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
    return QueryResponse(
        id=log.id, answer=NO_INFO_ANSWER, sources=[], mode=BOT_MODE, latency_ms=log.latency_ms or 0, no_info=True
    )
