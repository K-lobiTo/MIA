import pytest

from mia.config import settings
from mia.storage.models import Domain, Unit


@pytest.fixture
def base(db):
    with db() as session:
        session.add(Unit(id="u1", name="Computación"))
        session.flush()
        session.add(Domain(id="d1", unit_id="u1", name="Currículum"))
        session.commit()


def _modos(response):
    return {m["id"]: m for m in response.json()["modes"]}


def test_config_sin_clave_lista_ambos_modos(client, base, modes_config, monkeypatch):
    monkeypatch.setattr(settings, "ingestion_enabled", True)
    monkeypatch.setattr(settings, "max_upload_mb", 25)

    response = client.get("/config")

    assert response.status_code == 200
    body = response.json()
    assert body["ingestion_enabled"] is True and body["max_upload_mb"] == 25
    assert "artifact" not in body
    modos = _modos(response)
    assert set(modos) == {"literal", "razonamiento"}
    assert modos["literal"]["name"] == "Literal" and modos["literal"]["available"] is True
    assert modos["literal"]["reason"] is None
    assert modos["razonamiento"]["description"]


def test_un_modo_sin_proveedor_configurado_figura_no_disponible(client, base, modes_config, monkeypatch):
    monkeypatch.setattr(settings, "llm_provider_razonamiento", "")

    modos = _modos(client.get("/config"))

    assert modos["razonamiento"]["available"] is False
    assert "configurado" in modos["razonamiento"]["reason"]
    assert modos["literal"]["available"] is True


def test_openrouter_sin_modelo_no_esta_disponible(client, base, modes_config, monkeypatch):
    monkeypatch.setattr(settings, "llm_model_literal", "")
    monkeypatch.setattr(settings, "openrouter_model", "")

    modos = _modos(client.get("/config"))

    assert modos["literal"]["available"] is False


def test_el_modo_literal_usa_la_configuracion_anterior_si_no_define_la_suya(client, base, modes_config, monkeypatch):
    monkeypatch.setattr(settings, "llm_provider_literal", "")
    monkeypatch.setattr(settings, "llm_provider", "openrouter")
    monkeypatch.setattr(settings, "llm_model_literal", "")
    monkeypatch.setattr(settings, "openrouter_model", "z-ai/glm-5.3-flash")

    modos = _modos(client.get("/config"))

    assert modos["literal"]["available"] is True


def test_con_clave_de_artefacto_solo_los_modos_permitidos(client, base, modes_config, make_artifact):
    artefacto = make_artifact("Consulta Computación", modes="literal", units=["u1"])

    response = client.get("/config", headers=artefacto.headers)

    assert response.status_code == 200
    assert set(_modos(response)) == {"literal"}
    assert response.json()["artifact"] == {"name": "Consulta Computación", "active": True}


def test_un_artefacto_con_ambos_modos_los_ve_ambos(client, base, modes_config, make_artifact):
    artefacto = make_artifact(modes="literal,razonamiento", all_domains=True)

    assert set(_modos(client.get("/config", headers=artefacto.headers))) == {"literal", "razonamiento"}


def test_clave_de_artefacto_invalida_responde_401(client, base, modes_config):
    assert client.get("/config", headers={"X-Artifact-Key": "mia_falsa"}).status_code == 401


def test_dominios_con_clave_de_artefacto_solo_los_permitidos(client, db, base, make_artifact):
    with db() as session:
        session.add(Domain(id="d2", unit_id="u1", name="Docentes"))
        session.commit()
    artefacto = make_artifact(domains=["d2"])

    todos = client.get("/domains").json()
    permitidos = client.get("/domains", headers=artefacto.headers).json()

    assert {d["name"] for d in todos} == {"Currículum", "Docentes"}
    assert [d["name"] for d in permitidos] == ["Docentes"]
    assert permitidos[0]["unit_name"] == "Computación"
