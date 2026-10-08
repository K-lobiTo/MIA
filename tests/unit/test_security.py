import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from mia.access.keys import generate_key, hash_key, key_prefix
from mia.api import security
from mia.config import settings
from mia.storage.db import SessionLocal
from mia.storage.models import Artifact

app = FastAPI()


@app.get("/solo-admin", dependencies=[Depends(security.require_admin)])
def solo_admin() -> dict:
    return {"ok": True}


@app.get("/solo-artefacto")
def solo_artefacto(artifact: Artifact = Depends(security.require_artifact)) -> dict:
    return {"name": artifact.name}


client = TestClient(app)


@pytest.fixture
def admin_key(monkeypatch):
    monkeypatch.setattr(settings, "admin_key", "clave-de-prueba")
    return "clave-de-prueba"


def test_sin_admin_key_configurada_responde_503(monkeypatch):
    monkeypatch.setattr(settings, "admin_key", "")
    response = client.get("/solo-admin", headers={"X-Admin-Key": "lo-que-sea"})
    assert response.status_code == 503


def test_clave_de_administracion_incorrecta_o_ausente_responde_401(admin_key):
    assert client.get("/solo-admin").status_code == 401
    assert client.get("/solo-admin", headers={"X-Admin-Key": "otra"}).status_code == 401


def test_clave_de_administracion_correcta_da_acceso(admin_key):
    assert client.get("/solo-admin", headers={"X-Admin-Key": admin_key}).status_code == 200


def test_clave_de_artefacto_inexistente_o_ausente_responde_401():
    assert client.get("/solo-artefacto").status_code == 401
    assert client.get("/solo-artefacto", headers={"X-Artifact-Key": "mia_falsa"}).status_code == 401


def test_clave_de_artefacto_valida_encuentra_al_artefacto():
    key = generate_key()
    with SessionLocal() as session:
        session.add(
            Artifact(id="a-sec", name="Prueba seguridad", key_hash=hash_key(key), key_prefix=key_prefix(key))
        )
        session.commit()
    response = client.get("/solo-artefacto", headers={"X-Artifact-Key": key})
    assert response.status_code == 200
    assert response.json() == {"name": "Prueba seguridad"}


def test_claves_generadas():
    key = generate_key()
    assert key.startswith("mia_")
    assert len(key) > 40
    assert hash_key(key) == hash_key(key)
    assert hash_key(key) != hash_key(generate_key())
    assert key_prefix(key) == key[:8]
