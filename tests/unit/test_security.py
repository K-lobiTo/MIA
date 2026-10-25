import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from mia.access.keys import bot_service_key_matches, generate_key, hash_key, key_prefix
from mia.api import security
from mia.config import settings
from mia.storage.db import SessionLocal
from mia.storage.models import Artifact

app = FastAPI()


@app.get("/solo-artefacto")
def solo_artefacto(artifact: Artifact = Depends(security.require_artifact)) -> dict:
    return {"name": artifact.name}




@app.get("/solo-servicio-del-bot", dependencies=[Depends(security.require_bot_service)])
def solo_servicio_del_bot() -> dict:
    return {"ok": True}


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


# --- Credencial de servicio del bot de WhatsApp (feature 011) ---------------------------------------------------


@pytest.fixture
def clave_del_bot(monkeypatch):
    monkeypatch.setattr(settings, "bot_service_key", "clave-del-servicio-de-prueba")
    return "clave-del-servicio-de-prueba"


def test_la_credencial_de_servicio_correcta_pasa(clave_del_bot):
    assert bot_service_key_matches(clave_del_bot) is True
    response = client.get("/solo-servicio-del-bot", headers={"X-Bot-Service-Key": clave_del_bot})
    assert response.status_code == 200


def test_la_credencial_de_servicio_incorrecta_o_ausente_responde_401(clave_del_bot):
    assert bot_service_key_matches("otra") is False
    assert client.get("/solo-servicio-del-bot").status_code == 401
    response = client.get("/solo-servicio-del-bot", headers={"X-Bot-Service-Key": "otra"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Credencial del servicio del bot inválida."


def test_con_la_variable_vacia_las_rutas_del_bot_estan_apagadas(monkeypatch):
    monkeypatch.setattr(settings, "bot_service_key", "")
    assert bot_service_key_matches("") is False
    # Ni siquiera un encabezado vacío (igual a la variable vacía) abre la ruta.
    assert client.get("/solo-servicio-del-bot", headers={"X-Bot-Service-Key": ""}).status_code == 401
    assert client.get("/solo-servicio-del-bot", headers={"X-Bot-Service-Key": "algo"}).status_code == 401


def test_las_claves_de_administracion_y_de_artefacto_no_sustituyen_a_la_del_servicio(clave_del_bot, monkeypatch):
    monkeypatch.setattr(settings, "admin_key", "clave-admin-de-prueba")
    headers = {"X-Admin-Key": "clave-admin-de-prueba", "X-Artifact-Key": "mia_cualquiera"}
    assert client.get("/solo-servicio-del-bot", headers=headers).status_code == 401
