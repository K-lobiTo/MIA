import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from mia.config import settings
from mia.rag.context import build_passages
from mia.rag.embeddings import get_embedding_provider
from mia.rag.llm import RagContext, get_llm_provider, is_no_info_answer
from mia.storage.db import get_session
from mia.storage.models import Document, Domain
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
    question: str = Field(min_length=1)


class QueryResponse(BaseModel):
    answer: str
    sources: list[Source]


@router.post("/query", response_model=QueryResponse)
def query(payload: QueryRequest, session: Session = Depends(get_session)) -> QueryResponse:
    embedding_provider = get_embedding_provider(settings.embedding_provider)
    question_embedding = embedding_provider.embed([payload.question], is_query=True)[0]

    vector_store = get_vector_store()
    results = vector_store.search(
        question_embedding, domains=payload.domains, limit=settings.query_search_limit
    )
    relevant = [r for r in results if r.score >= settings.query_similarity_threshold]

    if not relevant:
        return QueryResponse(answer=NO_INFO_ANSWER, sources=[])

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

    llm_provider = get_llm_provider(settings.llm_provider)
    try:
        answer = llm_provider.answer(payload.question, context)
    except Exception as exc:
        # Sin esto el motivo real (clave inválida, modelo inexistente, timeout...) no queda en el log.
        logger.exception("Falló el proveedor de LLM (%s)", settings.llm_provider)
        raise HTTPException(
            status_code=502, detail="El proveedor de LLM no está disponible en este momento."
        ) from exc

    if is_no_info_answer(answer):
        return QueryResponse(answer=NO_INFO_ANSWER, sources=[])

    return QueryResponse(answer=answer, sources=sources)
