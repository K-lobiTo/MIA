from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from mia.access.keys import generate_key, hash_key, key_prefix
from mia.api import security
from mia.storage.db import SessionLocal
from mia.storage.models import Artifact

app = FastAPI()


@app.get("/solo-artefacto")
def solo_artefacto(artifact: Artifact = Depends(security.require_artifact)) -> dict:
    return {"name": artifact.name}


client = TestClient(app)


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
