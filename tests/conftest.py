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


import time
import uuid
from decimal import Decimal
from types import SimpleNamespace

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa

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


# --- Identidad de prueba: tokens de Microsoft firmados con una clave local (specs/004-acceso-panel-tec) ---

TEST_TENANT = "1119bb90-88ba-4894-b7f1-de26e129d977"
TEST_CLIENT_ID = "cliente-de-prueba"
TEST_KID = "clave-de-prueba"


@pytest.fixture(scope="session")
def rsa_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


class FakeKeySource:
    """Conjunto de claves falso: solo conoce las que se le dan, sin tocar la red."""

    def __init__(self, keys: dict):
        self.keys = keys

    def get_key(self, kid):
        return self.keys.get(kid)


@pytest.fixture
def entra_config(monkeypatch):
    """La API con inicio de sesión configurado (client ID de prueba, tenant del TEC, MFA exigido)."""
    monkeypatch.setattr(settings, "entra_client_id", TEST_CLIENT_ID)
    monkeypatch.setattr(settings, "entra_tenant_id", TEST_TENANT)
    monkeypatch.setattr(settings, "entra_require_mfa", True)


@pytest.fixture
def key_source(rsa_key):
    return FakeKeySource({TEST_KID: rsa_key.public_key()})


@pytest.fixture
def key_source_override(key_source, db):
    """Sustituye el origen de claves de Microsoft por el falso en toda la API."""
    from mia.api.security import get_key_source

    app.dependency_overrides[get_key_source] = lambda: key_source
    yield key_source
    app.dependency_overrides.pop(get_key_source, None)


@pytest.fixture
def token_factory(rsa_key, entra_config):
    """Fábrica de ID tokens de prueba. Cada claim se puede cambiar; con valor None se quita. Con
    `signing_key` se firma con otra clave, y con `alg` se prueban algoritmos no admitidos."""

    def _make(email="persona@itcr.ac.cr", *, signing_key=None, alg="RS256", kid=TEST_KID, **overrides) -> str:
        now = int(time.time())
        claims = {
            "iss": f"https://login.microsoftonline.com/{TEST_TENANT}/v2.0",
            "aud": TEST_CLIENT_ID,
            "tid": TEST_TENANT,
            "email": email,
            "amr": ["pwd", "mfa"],
            "iat": now - 10,
            "exp": now + 3600,
        }
        claims.update(overrides)
        claims = {k: v for k, v in claims.items() if v is not None}
        headers = {"kid": kid} if kid else {}
        if alg == "none":
            return jwt.encode(claims, None, algorithm="none", headers=headers)
        if alg == "HS256":
            return jwt.encode(claims, "secreto-compartido-de-prueba-0123456789", algorithm="HS256", headers=headers)
        return jwt.encode(claims, signing_key or rsa_key, algorithm="RS256", headers=headers)

    return _make


@pytest.fixture
def as_user(token_factory, key_source_override):
    """Encabezados de una persona que inició sesión con Microsoft: `as_user("correo@itcr.ac.cr")`.
    La persona debe estar en la lista (ver `make_admin`) para que la API la acepte."""

    def _headers(email="persona@itcr.ac.cr", **overrides) -> dict:
        return {"Authorization": f"Bearer {token_factory(email, **overrides)}"}

    return _headers


@pytest.fixture
def units(db):
    """Las dos unidades reales: `units.comp` y `units.adm` (ids)."""
    from mia.storage.models import Unit

    ids = SimpleNamespace(comp=str(uuid.uuid4()), adm=str(uuid.uuid4()))
    with db() as session:
        session.add_all(
            [
                Unit(id=ids.comp, name="Computación"),
                Unit(id=ids.adm, name="Administración de Empresas"),
            ]
        )
        session.commit()
    return ids


@pytest.fixture
def make_admin(db):
    """Agrega un administrador a la lista: `make_admin("a@itcr.ac.cr", global_=True)` o con `units=[nombres]`."""
    from mia.access.admins import add_admin

    def _make(email, *, global_=False, units=()):
        with db() as session:
            return add_admin(session, email, is_global=global_, unit_names=list(units))

    return _make
