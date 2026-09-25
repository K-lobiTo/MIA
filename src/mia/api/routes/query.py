from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["query"])


class Source(BaseModel):
    domain: str
    document: str
    excerpt: str


class QueryRequest(BaseModel):
    domains: list[str]
    question: str


class QueryResponse(BaseModel):
    answer: str
    sources: list[Source]


@router.post("/query", response_model=QueryResponse)
def query(payload: QueryRequest) -> QueryResponse:
    raise NotImplementedError("Motor RAG pendiente de implementación (ver docs/Definicion_Requerimientos_MVP.md secciones 6-7)")
