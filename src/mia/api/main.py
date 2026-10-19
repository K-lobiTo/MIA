import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from mia.access.errors import AuthError
from mia.api.routes import (
    artifacts,
    config,
    domains,
    equivalences,
    health,
    inventory,
    me,
    query,
    usage,
)
from mia.config import settings
from mia.rag.embeddings import get_embedding_provider
from mia.rag.lexical import hybrid_enabled
from mia.rag.rerank import warm_up_rerank_provider
from mia.storage.db import init_db
from mia.storage.vector_store import get_vector_store


def ensure_text_index() -> None:
    """Con QUERY_HYBRID_SEARCH=on asegura el índice de texto de Qdrant (feature 010). Un fallo no impide arrancar: la
    búsqueda híbrida cae al significado con un aviso. Con la opción apagada no hace nada (producción no cambia)."""
    if not hybrid_enabled(settings.query_hybrid_search):
        return
    try:
        get_vector_store().ensure_text_index()
    except Exception as exc:  # noqa: BLE001
        logging.getLogger(__name__).warning(
            "No se pudo asegurar el índice de texto (%s: %s): la búsqueda híbrida caerá al significado",
            type(exc).__name__, exc,
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    embedding_provider = get_embedding_provider(settings.embedding_provider)
    get_vector_store().ensure_collection(embedding_provider.dimension)
    ensure_text_index()
    # Con RERANK_PROVIDER=local el modelo se carga al arrancar para que la primera consulta no pague la carga.
    warm_up_rerank_provider()
    yield


# Los mensajes informativos de MIA (por ejemplo el motivo de fin de la generación de cada consulta) salen por la
# salida estándar, donde los recoge Railway. Sin esto Python solo muestra los de nivel WARNING.
_mia_logger = logging.getLogger("mia")
if not _mia_logger.handlers:
    _mia_handler = logging.StreamHandler(sys.stdout)
    _mia_handler.setFormatter(logging.Formatter("%(levelname)s:     %(name)s: %(message)s"))
    _mia_logger.addHandler(_mia_handler)
    _mia_logger.setLevel(logging.INFO)

app = FastAPI(title="MIA", description="Memoria Institucional Académica", lifespan=lifespan)

# Los sitios estáticos (panel, Consulta administrativa) llaman directo a la API desde el navegador.
# Sin orígenes configurados no se agrega CORS: en desarrollo el proxy de Vite lo hace innecesario.
_cors_origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
if _cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["content-type", "Authorization", "X-Admin-Key", "X-Artifact-Key"],
        expose_headers=["Retry-After"],
    )



@app.exception_handler(AuthError)
async def auth_error_handler(request: Request, error: AuthError) -> JSONResponse:
    # Además del mensaje, un código estable para que el panel distinga el caso.
    headers = {"WWW-Authenticate": "Bearer"} if error.status_code == 401 else None
    return JSONResponse(
        status_code=error.status_code, content={"detail": error.detail, "code": error.code}, headers=headers
    )


app.include_router(health.router)
app.include_router(me.router)
app.include_router(inventory.router)
app.include_router(artifacts.router)
app.include_router(config.router)
app.include_router(equivalences.router)
app.include_router(usage.router)
app.include_router(domains.router)
app.include_router(query.router)
