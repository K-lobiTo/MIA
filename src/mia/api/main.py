from contextlib import asynccontextmanager

from fastapi import FastAPI

from mia.api.routes import domains, health, query
from mia.config import settings
from mia.rag.embeddings import get_embedding_provider
from mia.storage.db import init_db
from mia.storage.vector_store import get_vector_store


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    embedding_provider = get_embedding_provider(settings.embedding_provider)
    get_vector_store().ensure_collection(embedding_provider.dimension)
    yield


app = FastAPI(title="MIA", description="Memoria Institucional Académica", lifespan=lifespan)

app.include_router(health.router)
app.include_router(domains.router)
app.include_router(query.router)
