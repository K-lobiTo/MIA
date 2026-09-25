from contextlib import asynccontextmanager

from fastapi import FastAPI

from mia.api.routes import domains, health, query
from mia.storage.db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="MIA", description="Memoria Institucional Académica", lifespan=lifespan)

app.include_router(health.router)
app.include_router(domains.router)
app.include_router(query.router)
