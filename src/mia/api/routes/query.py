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
from mia.rag.citations import (
    CITATION_INSTRUCTIONS,
    SAFETY_RULE_NOTE,
    cited_sources_enabled,
    parse_citations,
    select_sources,
)
from mia.rag.completeness import (
    COMPLETENESS_INSTRUCTIONS,
    NOTE_NOTICE,
    NOTE_RETRIED,
    combine_notes,
    complete_context_enabled,
    mark_continuation,
    merge_attempts,
    needs_retry,
    retry_cut_enabled,
    with_notice,
)
from mia.rag.context import ContextPolicy, build_passages
from mia.rag.embeddings import get_embedding_provider
from mia.rag.llm import RagContext, get_llm_provider, is_no_info_answer
from mia.rag.modes import estimate_cost, mode_available, mode_config
from mia.rag.query_rewrite import clean_note, clean_question, clean_question_enabled
from mia.rag.rerank import (
    RerankOutcome,
    deadline_for,
    format_memory,
    get_rerank_provider,
    read_memory_mb,
    rerank_candidates,
    rerank_note,
    warn_rerank_failure,
)
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

    # Con RERANK_PROVIDER=local (feature 009) se recuperan más candidatos, un cross-encoder los puntúa contra la
    # pregunta original y el corte es el puntaje del reranker. Sin reranker (o si falla) es la similitud de siempre.
    rerank_provider = get_rerank_provider(settings.rerank_provider)
    rerank_logits: dict[str, float] = {}  # chunk_id -> logit, para no puntuar dos veces el mismo fragmento
    rerank_failed = False
    rerank_outcome: RerankOutcome | None = None

    def by_similarity(results):
        return [r for r in results[: config.search_limit] if r.score >= settings.query_similarity_threshold]

    def retrieve(vector):
        nonlocal rerank_failed, rerank_outcome
        if rerank_provider is None or rerank_failed:
            return by_similarity(
                vector_store.search(vector, domains=payload.domains, limit=config.search_limit)
            )
        # Nunca menos candidatos que el límite del modo: así la caída a la similitud no entrega menos que hoy.
        results = vector_store.search(
            vector, domains=payload.domains, limit=max(settings.rerank_candidates, config.search_limit)
        )
        if not results:
            return []
        try:
            started = time.perf_counter()
            pending = [r for r in results if r.chunk_id not in rerank_logits]
            if pending:
                logits = rerank_provider.score(
                    payload.question, [r.text for r in pending], deadline=deadline_for(started)
                )
                rerank_logits.update(zip((r.chunk_id for r in pending), logits, strict=True))
                _, peak = read_memory_mb()
                logger.info(
                    "Reranker: %d candidatos en %d ms, pico de memoria %s MB (modo %s)",
                    len(pending), _elapsed_ms(started), format_memory(peak), payload.mode,
                )
            rerank_outcome = rerank_candidates(
                results,
                [rerank_logits[r.chunk_id] for r in results],
                settings.rerank_min_score,
                config.search_limit,
            )
            return rerank_outcome.results
        except Exception as exc:  # noqa: BLE001
            # Un fallo del reranker nunca rompe la consulta: sigue con el orden y el umbral por similitud.
            warn_rerank_failure(exc)
            rerank_failed = True
            rerank_outcome = RerankOutcome(
                results=[], best=None, scored=0, passed=0, fell_back=True, min_score=settings.rerank_min_score
            )
            return by_similarity(results)

    relevant = retrieve(question_embedding)

    # Con QUERY_CLEAN_QUESTION encendida, si nada pasó el umbral se repite la búsqueda una vez con la pregunta
    # reducida a lo que se busca (feature 008). Solo reglas de texto: el segundo intento no llama a ningún modelo
    # de lenguaje, y el modelo recibe siempre la pregunta original.
    clean_question_note: str | None = None
    if not relevant and clean_question_enabled(settings.query_clean_question):
        cleaned = clean_question(payload.question)
        if cleaned:
            cleaned_embedding = embedding_provider.embed([cleaned], is_query=True)[0]
            relevant = retrieve(cleaned_embedding)
            clean_question_note = clean_note(cleaned, found=bool(relevant))

    # Nota del reranker: la de la última búsqueda de la consulta (o la caída a la similitud).
    rerank_note_text = (
        rerank_note(rerank_outcome)
        if rerank_outcome is not None and (rerank_outcome.fell_back or rerank_outcome.scored > 0)
        else None
    )

    def no_info(model: str | None = None) -> QueryResponse:
        log.outcome = "no_info"
        log.model = model
        log.reject_reason = combine_notes(rerank_note_text, clean_question_note)
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

    # Con QUERY_COMPLETE_CONTEXT encendida el documento principal se entrega completo o prolongado hacia
    # adelante (feature 007). Se lee en cada consulta, como las demás opciones.
    complete_context = complete_context_enabled(settings.query_complete_context)
    policy = (
        ContextPolicy(
            documents=settings.query_complete_documents,
            document_max_chunks=settings.query_complete_document_max_chunks,
            forward_neighbors=settings.query_complete_forward_neighbors,
            max_chars=settings.query_context_max_chars,
        )
        if complete_context
        else None
    )
    passages = build_passages(
        relevant,
        vector_store,
        settings.query_context_neighbors,
        settings.query_full_document_max_chunks,
        policy,
    )

    # Con QUERY_CITED_SOURCES encendida los pasajes se numeran y se le pide al modelo que cite los que usó.
    # Se lee en cada consulta, así que cambiar la variable y reiniciar el servicio basta.
    cite_sources = cited_sources_enabled(settings.query_cited_sources)

    sources: list[Source] = []
    context: list[RagContext] = []
    for position, passage in enumerate(passages, start=1):
        document = session.get(Document, passage.document_id)
        domain = session.get(Domain, passage.domain)
        document_label = document.filename if document else passage.document_id
        domain_label = domain.name if domain else passage.domain
        sources.append(Source(domain=domain_label, document=document_label, excerpt=passage.text))
        context.append(
            RagContext(
                domain=domain_label,
                document=document_label,
                # La marca de continuación la ve el modelo; la persona ve el texto original en las fuentes.
                excerpt=mark_continuation(passage.text, passage.continues) if complete_context else passage.text,
                reference=position if cite_sources else None,
            )
        )

    try:
        llm_provider = get_llm_provider(config.provider, config.model, config.reasoning_effort)
        instructions = config.instructions
        if complete_context:
            instructions = f"{instructions}\n\n{COMPLETENESS_INSTRUCTIONS}"
        if cite_sources:
            instructions = f"{instructions}\n\n{CITATION_INSTRUCTIONS}"
        answer = llm_provider.answer(payload.question, context, instructions=instructions)
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

    # Motivo de fin de la generación: se deja siempre en el registro del servidor, con cualquier combinación
    # de opciones, para poder contar cuántas respuestas terminan de forma anormal.
    logger.info("Fin de la generación: %s (modo %s)", answer.finish_reason or "desconocido", payload.mode)

    def interpret(model_answer):
        """El texto sin la línea FUENTES: (si las citas están encendidas) y su interpretación."""
        if not cite_sources:
            return model_answer.text, None
        parsed_citations = parse_citations(model_answer.text, len(passages))
        return parsed_citations.text, parsed_citations

    answer_text, parsed = interpret(answer)

    # Una generación que no terminó con normalidad se reintenta una vez, si los topes de gasto lo permiten; si
    # sigue cortada, el texto se entrega con un aviso (feature 007).
    cut_note: str | None = None
    notice = False
    if retry_cut_enabled(settings.query_retry_cut_answers) and needs_retry(
        answer.finish_reason, is_no_info_answer(answer_text)
    ):
        first_cost = (
            Decimal(str(answer.cost_usd))
            if answer.cost_usd is not None
            else estimate_cost(payload.mode, answer.prompt_tokens, answer.completion_tokens)
        )
        second = None
        if check_caps(session, artifact, payload.mode, extra=first_cost) is None:
            try:
                second = llm_provider.answer(payload.question, context, instructions=instructions)
                logger.info(
                    "Fin de la generación (reintento): %s (modo %s)", second.finish_reason or "desconocido", payload.mode
                )
            except Exception:
                logger.exception("Falló el reintento de una respuesta cortada (modo %s)", payload.mode)
        if second is None:
            notice, cut_note = True, NOTE_NOTICE
        else:
            second_text, second_parsed = interpret(second)
            if needs_retry(second.finish_reason, is_no_info_answer(second_text)):
                notice, cut_note = True, NOTE_NOTICE
                if len(second_text) >= len(answer_text):
                    answer_text, parsed = second_text, second_parsed
            else:
                cut_note = NOTE_RETRIED
                answer_text, parsed = second_text, second_parsed
            answer = merge_attempts(answer, second)

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

    safety_note: str | None = None
    if parsed is not None:
        # Con la línea FUENTES: ya quitada del texto, se eligen las fuentes que el modelo dice haber usado.
        selection = select_sources(parsed, len(passages))
        sources = [sources[i - 1] for i in selection.indexes]
        if parsed.invalid:
            logger.info("El modelo citó fragmentos inexistentes: %s (entregados: %d)", parsed.invalid, len(passages))
        if selection.safety_rule and not is_no_info_answer(answer_text):
            # Sin citas utilizables se listan todas las fuentes; la nota permite medir con qué frecuencia pasa.
            safety_note = SAFETY_RULE_NOTE

    if is_no_info_answer(answer_text):
        return no_info(model=log.model)

    if notice:
        answer_text = with_notice(answer_text)
    log.reject_reason = combine_notes(rerank_note_text, clean_question_note, cut_note, safety_note)
    log.outcome = "answered"
    log.sources = json.dumps(
        [{"domain": d, "document": n} for d, n in dict.fromkeys((s.domain, s.document) for s in sources)],
        ensure_ascii=False,
    )
    log.latency_ms = _elapsed_ms(started)
    session.add(log)
    session.commit()
    return QueryResponse(
        id=log.id, answer=answer_text, sources=sources, mode=payload.mode, latency_ms=log.latency_ms
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
