import os
import tempfile

# Los tests no deben depender del .env de quien los corre (que puede apuntar a bases de
# producción): se fijan valores locales antes de que se importe mia.config.
os.environ["DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/test.db"
os.environ["QDRANT_URL"] = "http://localhost:6333"
os.environ["QDRANT_API_KEY"] = ""
os.environ["INGESTION_ENABLED"] = "true"

from mia.storage.db import init_db

init_db()


import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from mia.api.main import app
from mia.config import settings
from mia.storage.db import get_session

ADMIN_KEY = "clave-admin-de-prueba"


@pytest.fixture
def db(tmp_path):
    """Base SQLite nueva y migrada por prueba; la API la usa en lugar de la global."""
    engine = create_engine(f"sqlite:///{tmp_path}/test.db")
    init_db(engine)
    factory = sessionmaker(bind=engine)

    def _get_session():
        with factory() as session:
            yield session

    app.dependency_overrides[get_session] = _get_session
    yield factory
    app.dependency_overrides.pop(get_session, None)


@pytest.fixture
def client(db):
    return TestClient(app)


@pytest.fixture
def admin(monkeypatch):
    """Encabezados de administración, con ADMIN_KEY configurada en la instancia."""
    monkeypatch.setattr(settings, "admin_key", ADMIN_KEY)
    return {"X-Admin-Key": ADMIN_KEY}


import uuid
from decimal import Decimal
from types import SimpleNamespace

from mia.access.keys import generate_key, hash_key, key_prefix
from mia.storage.models import Artifact, ArtifactDomain, ArtifactUnit


@pytest.fixture
def make_artifact(db):
    """Fábrica de artefactos con su clave; devuelve `.id`, `.key` y `.headers` listos para enviar."""

    def _make(
        name="Artefacto de prueba",
        *,
        modes="literal",
        all_domains=False,
        units=(),
        domains=(),
        active=True,
        cap=0.5,
        reasoning_cap=None,
    ):
        key = generate_key()
        artifact_id = str(uuid.uuid4())
        with db() as session:
            session.add(
                Artifact(
                    id=artifact_id,
                    name=name,
                    key_hash=hash_key(key),
                    key_prefix=key_prefix(key),
                    active=active,
                    all_domains=all_domains,
                    modes=modes,
                    daily_cap_usd=Decimal(str(cap)),
                    reasoning_daily_cap_usd=None if reasoning_cap is None else Decimal(str(reasoning_cap)),
                )
            )
            session.flush()
            session.add_all([ArtifactUnit(artifact_id=artifact_id, unit_id=u) for u in units])
            session.add_all([ArtifactDomain(artifact_id=artifact_id, domain_id=d) for d in domains])
            session.commit()
        return SimpleNamespace(id=artifact_id, key=key, headers={"X-Artifact-Key": key})

    return _make


@pytest.fixture
def modes_config(monkeypatch):
    """Los dos modos configurados en la instancia, sin depender del .env de quien corre las pruebas."""
    valores = {
        "llm_provider": "local",
        "llm_provider_literal": "openrouter",
        "llm_model_literal": "proveedor/modelo-literal",
        "llm_reasoning_effort_literal": "low",
        "llm_price_in_literal": 0.0,
        "llm_price_out_literal": 0.0,
        "llm_provider_razonamiento": "openrouter",
        "llm_model_razonamiento": "proveedor/modelo-razonamiento",
        "llm_reasoning_effort_razonamiento": "high",
        "llm_price_in_razonamiento": 0.0,
        "llm_price_out_razonamiento": 0.0,
        "openrouter_model": "",
        "openrouter_reasoning_effort": "",
        "daily_cap_usd": 3.0,
    }
    for nombre, valor in valores.items():
        monkeypatch.setattr(settings, nombre, valor)
    return valores
