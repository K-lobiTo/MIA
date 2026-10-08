from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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

# Los sitios estáticos (panel, Consulta administrativa) llaman directo a la API desde el navegador.
# Sin orígenes configurados no se agrega CORS: en desarrollo el proxy de Vite lo hace innecesario.
_cors_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
if _cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["content-type", "X-Admin-Key", "X-Artifact-Key"],
        expose_headers=["Retry-After"],
    )

app.include_router(health.router)
app.include_router(domains.router)
app.include_router(query.router)
