"""Conversaciones guardadas de los usuarios de la Consulta (feature 015, research R5 y R9).

Todas las operaciones filtran por el usuario dueño: una conversación ajena y una inexistente son indistinguibles (404). Lo que
se guarda de cada vuelta es la pregunta, la respuesta (cortada a `chat_max_answer_chars`), las fuentes como dominio y
documento (sin extracto), el modo y si fue "sin información". Nunca se guarda la clave del artefacto ni nada del bot."""

import json
import re
import uuid
from dataclasses import dataclass

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from mia.access.errors import conversation_full, conversation_not_found, too_many_conversations
from mia.config import settings
from mia.rag.history import HistoryTurn
from mia.storage.models import ConsultaUser, Conversation, ConversationTurn, _now

TITLE_MAX = 60
# Largo máximo de un título puesto por la persona (el automático se recorta a TITLE_MAX).
RENAME_MAX = 80


def make_title(question: str) -> str:
    """La primera pregunta con espacios normalizados, recortada a 60 caracteres en un límite de palabra ("..." si se cortó)."""
    text = re.sub(r"\s+", " ", question or "").strip()
    if len(text) <= TITLE_MAX:
        return text or "Conversación"
    cut = text[:TITLE_MAX]
    if text[TITLE_MAX] != " " and " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    return cut.rstrip(" ,.;:") + "..."


def get_owned(session: Session, user: ConsultaUser, conversation_id: str) -> Conversation:
    """La conversación del usuario; 404 si es de otro o no existe."""
    conversation = session.scalar(
        select(Conversation).where(
            Conversation.id == conversation_id, Conversation.user_id == user.id
        )
    )
    if conversation is None:
        raise conversation_not_found()
    return conversation


def _turn_count(session: Session, conversation_id: str) -> int:
    return (
        session.scalar(
            select(func.count(ConversationTurn.id)).where(
                ConversationTurn.conversation_id == conversation_id
            )
        )
        or 0
    )


def check_room(session: Session, user: ConsultaUser, conversation_id: str | None) -> None:
    """Antes de consultar (sin gastar el modelo): 404 si la conversación no es del usuario, 409 si ya está llena o si, al
    empezar una nueva, el usuario ya tiene el máximo de conversaciones."""
    if conversation_id is not None:
        get_owned(session, user, conversation_id)
        if _turn_count(session, conversation_id) >= settings.chat_max_turns:
            raise conversation_full()
        return
    total = (
        session.scalar(select(func.count(Conversation.id)).where(Conversation.user_id == user.id))
        or 0
    )
    if total >= settings.chat_max_conversations:
        raise too_many_conversations()


def append_turn(
    session: Session,
    user: ConsultaUser,
    conversation_id: str | None,
    question: str,
    answer: str,
    sources: list[dict],
    mode: str,
    no_info: bool,
) -> str:
    """Guarda una vuelta; crea la conversación si no se dio una. Devuelve el identificador de la conversación."""
    conversation = get_owned(session, user, conversation_id) if conversation_id else None
    if conversation is None:
        now = _now()
        conversation = Conversation(
            id=str(uuid.uuid4()),
            user_id=user.id,
            title=make_title(question),
            created_at=now,
            updated_at=now,
        )
        session.add(conversation)
        session.flush()
    kept = answer[: settings.chat_max_answer_chars]
    for attempt in range(2):
        position = (
            session.scalar(
                select(func.coalesce(func.max(ConversationTurn.position), 0)).where(
                    ConversationTurn.conversation_id == conversation.id
                )
            )
            or 0
        ) + 1
        session.add(
            ConversationTurn(
                id=str(uuid.uuid4()),
                conversation_id=conversation.id,
                position=position,
                question=question,
                answer=kept,
                sources=json.dumps(sources, ensure_ascii=False),
                mode=mode,
                no_info=no_info,
                created_at=_now(),
            )
        )
        conversation.updated_at = _now()
        try:
            session.commit()
            return conversation.id
        except IntegrityError:
            # Otra consulta de la misma conversación tomó esa posición a la vez: se reintenta con la siguiente libre.
            session.rollback()
            if attempt == 1:
                raise
            conversation = get_owned(session, user, conversation.id)
    return conversation.id  # pragma: no cover


def list_conversations(session: Session, user: ConsultaUser) -> list[tuple[Conversation, int]]:
    """Las conversaciones del usuario de la más reciente a la más antigua, con su cantidad de vueltas."""
    counts = (
        select(ConversationTurn.conversation_id, func.count(ConversationTurn.id).label("n"))
        .group_by(ConversationTurn.conversation_id)
        .subquery()
    )
    rows = session.execute(
        select(Conversation, func.coalesce(counts.c.n, 0))
        .outerjoin(counts, counts.c.conversation_id == Conversation.id)
        .where(Conversation.user_id == user.id)
        .order_by(Conversation.updated_at.desc(), Conversation.created_at.desc())
    ).all()
    return [(conversation, count) for conversation, count in rows]


@dataclass
class OpenedConversation:
    conversation: Conversation
    turns: list[ConversationTurn]


def get_conversation(
    session: Session, user: ConsultaUser, conversation_id: str
) -> OpenedConversation:
    conversation = get_owned(session, user, conversation_id)
    turns = list(
        session.scalars(
            select(ConversationTurn)
            .where(ConversationTurn.conversation_id == conversation.id)
            .order_by(ConversationTurn.position)
        )
    )
    return OpenedConversation(conversation=conversation, turns=turns)


HISTORY_FETCH = 50  # tantas vueltas guardadas se traen como máximo: el recorte fino por la memoria del artefacto es de la 014


def history_turns(session: Session, user: ConsultaUser, conversation_id: str) -> list[HistoryTurn]:
    """Las últimas vueltas guardadas de la conversación, de la más vieja a la más nueva, como historial de la feature 014. Es
    lo que se retoma: sale de lo guardado y nunca de lo que mande el cliente. `sanitize_history` aplica después la memoria del
    artefacto y excluye las vueltas vacías y las de "sin información"."""
    get_owned(session, user, conversation_id)
    rows = session.scalars(
        select(ConversationTurn)
        .where(ConversationTurn.conversation_id == conversation_id)
        .order_by(ConversationTurn.position.desc())
        .limit(HISTORY_FETCH)
    ).all()
    return [HistoryTurn(turn.question, turn.answer, turn.mode) for turn in reversed(rows)]


def rename_conversation(session: Session, user: ConsultaUser, conversation_id: str, title: str) -> tuple[Conversation, int]:
    """Cambia el título de la conversación (espacios normalizados, hasta `RENAME_MAX` caracteres) sin tocar su fecha de
    actividad: la retención y el orden de la lista no cambian. 404 si no es del usuario o no existe."""
    conversation = get_owned(session, user, conversation_id)
    conversation.title = re.sub(r"\s+", " ", title or "").strip()[:RENAME_MAX] or conversation.title
    session.commit()
    return conversation, _turn_count(session, conversation.id)


def delete_conversation(session: Session, user: ConsultaUser, conversation_id: str) -> None:
    """Borra la conversación y todas sus vueltas por completo; 404 si no es del usuario o no existe."""
    conversation = get_owned(session, user, conversation_id)
    session.execute(
        delete(ConversationTurn).where(ConversationTurn.conversation_id == conversation.id)
    )
    session.execute(delete(Conversation).where(Conversation.id == conversation.id))
    session.commit()


def delete_all_conversations(session: Session, user: ConsultaUser) -> int:
    """Borra todas las conversaciones del usuario (y solo las suyas) con sus vueltas. Devuelve cuántas."""
    ids = list(session.scalars(select(Conversation.id).where(Conversation.user_id == user.id)))
    for start in range(0, len(ids), 500):
        chunk = ids[start : start + 500]
        session.execute(delete(ConversationTurn).where(ConversationTurn.conversation_id.in_(chunk)))
        session.execute(delete(Conversation).where(Conversation.id.in_(chunk)))
    session.commit()
    return len(ids)
