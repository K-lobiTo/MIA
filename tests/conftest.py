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
