from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from mia.config import settings
from mia.rag.embeddings import get_embedding_provider
from mia.rag.llm import RagContext, get_llm_provider, is_no_info_answer
from mia.storage.db import get_session
from mia.storage.models import Document, Domain
from mia.storage.vector_store import get_vector_store

router = APIRouter(tags=["query"])

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

    results = get_vector_store().search(
        question_embedding, domains=payload.domains, limit=settings.query_search_limit
    )
    relevant = [r for r in results if r.score >= settings.query_similarity_threshold]

    if not relevant:
        return QueryResponse(answer=NO_INFO_ANSWER, sources=[])

    sources: list[Source] = []
    context: list[RagContext] = []
    for result in relevant:
        document = session.get(Document, result.document_id)
        domain = session.get(Domain, result.domain)
        document_label = document.filename if document else result.document_id
        domain_label = domain.name if domain else result.domain
        sources.append(Source(domain=domain_label, document=document_label, excerpt=result.text))
        context.append(RagContext(domain=domain_label, document=document_label, excerpt=result.text))

    llm_provider = get_llm_provider(settings.llm_provider)
    try:
        answer = llm_provider.answer(payload.question, context)
    except Exception as exc:
        raise HTTPException(
            status_code=502, detail="El proveedor de LLM no está disponible en este momento."
        ) from exc

    if is_no_info_answer(answer):
        return QueryResponse(answer=NO_INFO_ANSWER, sources=[])

    return QueryResponse(answer=answer, sources=sources)
