"""Conversaciones guardadas de la persona con sesión (feature 015): GET /conversations, GET /conversations/{id}, PATCH /conversations/{id} (renombrar) y DELETE.

Todas exigen la sesión (`X-Session-Token`) y filtran por su dueño: una ajena y una inexistente responden lo mismo (404). El
registro del servidor escribe solo cantidades, nunca títulos ni textos.
Contrato en specs/015-historial-chats/contracts/conversaciones-api.md."""

import json
import logging

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from mia.api.security import require_user
from mia.chat import retention, service
from mia.config import settings
from mia.storage.db import get_session
from mia.storage.models import ConsultaUser

logger = logging.getLogger("mia.chat")

router = APIRouter(tags=["conversations"])


class ConversationSummary(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str
    turn_count: int


class ConversationRename(BaseModel):
    title: str = Field(max_length=200)

    @field_validator("title")
    @classmethod
    def not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("El título no puede estar vacío.")
        return value


class ConversationsOut(BaseModel):
    retention_days: int
    conversations: list[ConversationSummary]


class SourceOut(BaseModel):
    domain: str
    document: str


class TurnOut(BaseModel):
    position: int
    question: str
    answer: str
    sources: list[SourceOut]
    mode: str
    no_info: bool
    created_at: str


class ConversationOut(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str
    turns: list[TurnOut]


def _iso(value) -> str:
    return value.isoformat() + "Z"


def _sources(raw: str) -> list[SourceOut]:
    try:
        return [
            SourceOut(domain=str(s.get("domain", "")), document=str(s.get("document", "")))
            for s in json.loads(raw)
        ]
    except (ValueError, TypeError, AttributeError):
        return []


@router.get("/conversations", response_model=ConversationsOut)
def list_conversations(
    user: ConsultaUser = Depends(require_user), session: Session = Depends(get_session)
) -> ConversationsOut:
    retention.maybe_purge(session)
    days = settings.chat_retention_days
    if days == 0:
        return ConversationsOut(retention_days=0, conversations=[])
    rows = service.list_conversations(session, user)
    logger.info("Conversaciones resultado=listadas cantidad=%d", len(rows))
    return ConversationsOut(
        retention_days=days,
        conversations=[
            ConversationSummary(
                id=c.id,
                title=c.title,
                created_at=_iso(c.created_at),
                updated_at=_iso(c.updated_at),
                turn_count=count,
            )
            for c, count in rows
        ],
    )


@router.get("/conversations/{conversation_id}", response_model=ConversationOut)
def get_conversation(
    conversation_id: str,
    user: ConsultaUser = Depends(require_user),
    session: Session = Depends(get_session),
) -> ConversationOut:
    opened = service.get_conversation(session, user, conversation_id)
    c = opened.conversation
    return ConversationOut(
        id=c.id,
        title=c.title,
        created_at=_iso(c.created_at),
        updated_at=_iso(c.updated_at),
        turns=[
            TurnOut(
                position=t.position,
                question=t.question,
                answer=t.answer,
                sources=_sources(t.sources),
                mode=t.mode,
                no_info=t.no_info,
                created_at=_iso(t.created_at),
            )
            for t in opened.turns
        ],
    )


@router.patch("/conversations/{conversation_id}", response_model=ConversationSummary)
def rename_conversation(
    conversation_id: str,
    payload: ConversationRename,
    user: ConsultaUser = Depends(require_user),
    session: Session = Depends(get_session),
) -> ConversationSummary:
    conversation, count = service.rename_conversation(session, user, conversation_id, payload.title)
    logger.info("Conversaciones resultado=renombrada cantidad=1")
    return ConversationSummary(
        id=conversation.id,
        title=conversation.title,
        created_at=_iso(conversation.created_at),
        updated_at=_iso(conversation.updated_at),
        turn_count=count,
    )


@router.delete("/conversations/{conversation_id}", status_code=204, response_class=Response)
def delete_conversation(
    conversation_id: str,
    user: ConsultaUser = Depends(require_user),
    session: Session = Depends(get_session),
) -> Response:
    service.delete_conversation(session, user, conversation_id)
    logger.info("Conversaciones resultado=borrada cantidad=1")
    return Response(status_code=204)


@router.delete("/conversations", status_code=204, response_class=Response)
def delete_all_conversations(
    user: ConsultaUser = Depends(require_user), session: Session = Depends(get_session)
) -> Response:
    deleted = service.delete_all_conversations(session, user)
    logger.info("Conversaciones resultado=borradas cantidad=%d", deleted)
    return Response(status_code=204)
