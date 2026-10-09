import json
import logging
import time
import uuid
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from mia.access.caps import CapStatus, check_caps, seconds_until
from mia.access.permissions import allowed_domain_ids, allowed_modes
from mia.api.security import require_artifact
from mia.config import settings
from mia.rag.context import build_passages
from mia.rag.embeddings import get_embedding_provider
from mia.rag.llm import RagContext, get_llm_provider, is_no_info_answer
from mia.rag.modes import estimate_cost, mode_available, mode_config
from mia.storage.db import get_session
from mia.storage.models import Artifact, Document, Domain, QueryLog
from mia.storage.vector_store import get_vector_store

router = APIRouter(tags=["query"])
logger = logging.getLogger(__name__)

NO_INFO_ANSWER = (
    "No encontré información suficiente en los dominios consultados para responder esta pregunta."
)


class Source(BaseModel):
    domain: str
    document: str
    excerpt: str


class QueryRequest(BaseModel):
    domains: list[str] = Field(min_length=1)
    question: str = Field(min_length=1, max_length=2000)
    mode: Literal["literal", "razonamiento"] = "literal"


class QueryResponse(BaseModel):
    id: str
    answer: str
    sources: list[Source]
    mode: str
    latency_ms: int
    # La respuesta es "sin información suficiente": el cliente la distingue sin comparar el texto.
    no_info: bool = False


class Feedback(BaseModel):
    rating: Literal["util", "no_util"]
    comment: str | None = None


def _elapsed_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)


def _reject(
    session: Session,
    log: QueryLog,
    started: float,
    status_code: int,
    outcome: str,
    reason: str,
    headers: dict[str, str] | None = None,
) -> HTTPException:
    """Registra la consulta rechazada (con costo cero) y devuelve el error HTTP para lanzarlo."""
    log.outcome = outcome
    log.reject_reason = reason
    log.latency_ms = _elapsed_ms(started)
    session.add(log)
    session.commit()
    return HTTPException(status_code=status_code, detail=reason, headers=headers)


def cap_message(status: CapStatus) -> str:
    """Mensaje de un tope alcanzado, para el error 429, el registro y la configuración."""
    reset = f"Se reinicia a la medianoche ({settings.cap_timezone})."
    if status.scope == "api":
        return f"Se alcanzó el tope diario de gasto de toda la API ({status.cap:.2f} USD). {reset}"
    if status.scope == "artifact":
        return f"Este artefacto alcanzó su tope diario de gasto ({status.cap:.2f} USD). {reset}"
    return (
        f"Este artefacto alcanzó su tope diario del modo con razonamiento ({status.cap:.2f} USD); "
        f"puede seguir usando los otros modos. {reset}"
    )


@router.post("/query", response_model=QueryResponse)
def query(
    payload: QueryRequest,
    artifact: Artifact = Depends(require_artifact),
    session: Session = Depends(get_session),
) -> QueryResponse:
    started = time.perf_counter()
    log = QueryLog(
        id=str(uuid.uuid4()),
        artifact_id=artifact.id,
        question=payload.question,
        domain_ids=json.dumps(payload.domains),
        mode=payload.mode,
        cost_usd=Decimal(0),
    )

    # Los permisos los aplica la API en cada consulta, no el artefacto: el código de un sitio
    # estático se puede modificar.
    if not artifact.active:
        raise _reject(session, log, started, 403, "rejected_permission", "Este artefacto está desactivado.")
    if payload.mode not in allowed_modes(artifact):
        raise _reject(
            session, log, started, 403, "rejected_permission",
            f"Este artefacto no tiene permitido el modo '{payload.mode}'.",
        )
    available, why = mode_available(payload.mode)
    if not available:
        raise _reject(
            session, log, started, 403, "rejected_permission",
            f"El modo '{payload.mode}' no está disponible en esta instancia: {why}",
        )
    allowed = allowed_domain_ids(session, artifact)
    forbidden = [d for d in payload.domains if d not in allowed]
    if forbidden:
        raise _reject(
            session, log, started, 403, "rejected_permission",
            "Este artefacto no tiene acceso a los dominios: " + ", ".join(forbidden) + ".",
        )

    # Topes de gasto del día. El costo de una consulta se conoce al terminar, así que un tope puede
    # excederse por el costo de las consultas que estaban en curso (acotado por OPENROUTER_MAX_TOKENS).
    cap = check_caps(session, artifact, payload.mode)
    if cap is not None:
        raise _reject(
            session, log, started, 429, "rejected_cap", cap_message(cap),
            headers={"Retry-After": str(seconds_until(cap.resets_at))},
        )

    # Ya se validó que el modo está disponible, así que su configuración existe.
    config = mode_config(payload.mode)
    embedding_provider = get_embedding_provider(settings.embedding_provider)
    question_embedding = embedding_provider.embed([payload.question], is_query=True)[0]

    vector_store = get_vector_store()
    results = vector_store.search(
        question_embedding, domains=payload.domains, limit=config.search_limit
    )
    relevant = [r for r in results if r.score >= settings.query_similarity_threshold]

    def no_info(model: str | None = None) -> QueryResponse:
        log.outcome = "no_info"
        log.model = model
        log.latency_ms = _elapsed_ms(started)
        session.add(log)
        session.commit()
        return QueryResponse(
            id=log.id,
            answer=NO_INFO_ANSWER,
            sources=[],
            mode=payload.mode,
            latency_ms=log.latency_ms,
            no_info=True,
        )

    if not relevant:
        return no_info()

    passages = build_passages(
        relevant,
        vector_store,
        settings.query_context_neighbors,
        settings.query_full_document_max_chunks,
    )

    sources: list[Source] = []
    context: list[RagContext] = []
    for passage in passages:
        document = session.get(Document, passage.document_id)
        domain = session.get(Domain, passage.domain)
        document_label = document.filename if document else passage.document_id
        domain_label = domain.name if domain else passage.domain
        sources.append(Source(domain=domain_label, document=document_label, excerpt=passage.text))
        context.append(
            RagContext(domain=domain_label, document=document_label, excerpt=passage.text)
        )

    try:
        llm_provider = get_llm_provider(config.provider, config.model, config.reasoning_effort)
        answer = llm_provider.answer(payload.question, context, instructions=config.instructions)
    except Exception as exc:
        # Sin esto el motivo real (clave inválida, modelo inexistente, timeout...) no queda en el log.
        logger.exception("Falló el proveedor de LLM (%s, modo %s)", config.provider, payload.mode)
        log.outcome = "error"
        log.reject_reason = str(exc)[:500]
        log.latency_ms = _elapsed_ms(started)
        session.add(log)
        session.commit()
        raise HTTPException(
            status_code=502, detail="El proveedor de LLM no está disponible en este momento."
        ) from exc

    # El costo real lo informa el proveedor; si no, se estima con los precios de respaldo del modo.
    log.model = answer.model or config.model
    log.prompt_tokens = answer.prompt_tokens
    log.completion_tokens = answer.completion_tokens
    log.reasoning_tokens = answer.reasoning_tokens
    if answer.cost_usd is not None:
        log.cost_usd = Decimal(str(answer.cost_usd)).quantize(Decimal("0.000001"))
        log.cost_estimated = False
    else:
        log.cost_usd = estimate_cost(payload.mode, answer.prompt_tokens, answer.completion_tokens)
        log.cost_estimated = True

    if is_no_info_answer(answer.text):
        return no_info(model=log.model)

    log.outcome = "answered"
    log.sources = json.dumps(
        [{"domain": d, "document": n} for d, n in dict.fromkeys((s.domain, s.document) for s in sources)],
        ensure_ascii=False,
    )
    log.latency_ms = _elapsed_ms(started)
    session.add(log)
    session.commit()
    return QueryResponse(
        id=log.id, answer=answer.text, sources=sources, mode=payload.mode, latency_ms=log.latency_ms
    )


@router.post("/query/{query_id}/feedback", status_code=204)
def feedback(
    query_id: str,
    payload: Feedback,
    artifact: Artifact = Depends(require_artifact),
    session: Session = Depends(get_session),
) -> Response:
    """Calificación de una consulta propia (útil o no útil). Una segunda calificación reemplaza la anterior."""
    log = session.scalar(select(QueryLog).where(QueryLog.id == query_id, QueryLog.artifact_id == artifact.id))
    if log is None:
        raise HTTPException(status_code=404, detail="Consulta no encontrada.")
    log.rating = payload.rating
    log.rating_comment = payload.comment
    session.commit()
    return Response(status_code=204)
