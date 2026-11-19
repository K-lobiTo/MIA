"""Habilitar el modo plantilla por artefacto, su costo, el tope y el registro de Uso (feature 020, US4)."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from mia.config import settings
from mia.storage.models import Bot, QueryLog
from tests.unit.historial_de_prueba import Pipeline, crear_mundo
from tests.unit.plantillas_de_prueba import plantilla_del_artefacto, preguntar_con_plantilla
from tests.unit.test_bot_service import CLAVE, NUMERO

PREGUNTA = "Prepárame el informe de la Maestría en Analítica"


def _cuerpo(modes, nombre="Consulta"):
    return {"name": nombre, "access": {"all_domains": True}, "modes": modes}


def test_crear_y_editar_un_artefacto_con_el_modo_plantilla(client, admin, modes_config):
    creado = client.post("/artifacts", json=_cuerpo(["literal", "razonamiento", "plantilla"]), headers=admin)

    assert creado.status_code == 201
    assert creado.json()["modes"] == ["literal", "razonamiento", "plantilla"]
    editado = client.patch(f"/artifacts/{creado.json()['id']}", json={"modes": ["plantilla", "literal"]}, headers=admin)
    assert editado.status_code == 200
    # El orden de los modos es siempre el fijo, sin importar el enviado.
    assert editado.json()["modes"] == ["literal", "plantilla"]
    assert client.post("/artifacts", json=_cuerpo(["inventado"], "Otro"), headers=admin).status_code == 422


def test_el_listado_de_artefactos_ofrece_el_modo_con_su_costo(client, admin, modes_config):
    modos = {m["id"]: m for m in client.get("/artifacts", headers=admin).json()["modes"]}

    assert modos["plantilla"]["name"] == "Plantilla" and modos["plantilla"]["available"] is True


def test_config_lista_la_plantilla_solo_con_el_modo_permitido(client, make_artifact, modes_config):
    con = make_artifact("Con", modes="literal,plantilla")
    sin = make_artifact("Sin", modes="literal,razonamiento")

    assert [m["id"] for m in client.get("/config", headers=con.headers).json()["modes"]] == ["literal", "plantilla"]
    assert "plantilla" not in [m["id"] for m in client.get("/config", headers=sin.headers).json()["modes"]]


def test_sin_el_razonamiento_configurado_la_plantilla_se_ve_no_disponible_con_su_motivo(client, make_artifact, modes_config, monkeypatch):
    monkeypatch.setattr(settings, "llm_provider_razonamiento", "")
    art = make_artifact("Con", modes="literal,razonamiento,plantilla")

    modos = {m["id"]: m for m in client.get("/config", headers=art.headers).json()["modes"]}

    assert modos["plantilla"]["available"] is False and modos["plantilla"]["reason"]
    assert modos["plantilla"]["reason"] == modos["razonamiento"]["reason"]
    assert modos["literal"]["available"] is True


@pytest.fixture
def mundo(db, modes_config, make_artifact, monkeypatch):
    return crear_mundo(db, make_artifact, monkeypatch, modes="literal,razonamiento,plantilla", cap=0.30, reasoning_cap=0.10)


def _gasto(db, artifact_id, modo, costo):
    with db() as session:
        session.add(
            QueryLog(id=str(uuid.uuid4()), artifact_id=artifact_id, created_at=datetime.now(UTC).replace(tzinfo=None),
                     mode=modo, outcome="answered", cost_usd=Decimal(str(costo)), model="m")
        )
        session.commit()


def test_el_tope_total_alcanzado_responde_429_sin_consultar_al_modelo(client, db, mundo):
    plantilla = plantilla_del_artefacto(db, mundo.id)
    _gasto(db, mundo.id, "literal", 0.30)

    with Pipeline() as pipeline:
        respuesta = preguntar_con_plantilla(client, mundo, PREGUNTA, plantilla)

    assert respuesta.status_code == 429 and "tope diario" in respuesta.json()["detail"]
    pipeline.llm.answer.assert_not_called()


def test_el_tope_del_razonamiento_lo_alcanza_el_gasto_de_razonamiento_mas_el_de_plantilla(client, db, mundo):
    plantilla = plantilla_del_artefacto(db, mundo.id)
    _gasto(db, mundo.id, "razonamiento", 0.06)
    _gasto(db, mundo.id, "plantilla", 0.05)

    with Pipeline() as pipeline:
        con_plantilla = preguntar_con_plantilla(client, mundo, PREGUNTA, plantilla)
        con_razonamiento = preguntar_con_plantilla(client, mundo, PREGUNTA, None, modo="razonamiento")
        literal = preguntar_con_plantilla(client, mundo, PREGUNTA, None, modo="literal")

    assert con_plantilla.status_code == 429 and "razonamiento" in con_plantilla.json()["detail"]
    assert con_razonamiento.status_code == 429
    assert literal.status_code == 200
    assert pipeline.llm.answer.call_count == 1


def test_uso_cuenta_la_plantilla_como_su_propio_modo_y_suma_al_tope(client, db, admin, mundo):
    plantilla = plantilla_del_artefacto(db, mundo.id)
    with Pipeline(costo=0.04):
        preguntar_con_plantilla(client, mundo, PREGUNTA, plantilla)
        preguntar_con_plantilla(client, mundo, PREGUNTA, plantilla)
        preguntar_con_plantilla(client, mundo, PREGUNTA, None, modo="razonamiento")

    por_modo = client.get("/usage", params={"period": "today", "group_by": "mode"}, headers=admin).json()
    gasto = {}
    for punto in por_modo["series"]:
        for nombre, grupo in punto["groups"].items():
            gasto[nombre] = gasto.get(nombre, 0) + grupo["spend_usd"]
    assert set(gasto) == {"plantilla", "razonamiento"}
    assert gasto["plantilla"] == pytest.approx(0.08) and gasto["razonamiento"] == pytest.approx(0.04)
    lista = client.get("/usage/queries", params={"period": "today", "mode": "plantilla"}, headers=admin).json()
    assert lista["total"] == 2 and {q["mode"] for q in lista["items"]} == {"plantilla"}
    # El gasto de las tres consultas suma al total del artefacto y al estado del razonamiento y plantilla.
    artefacto = next(a for a in client.get("/artifacts", headers=admin).json()["artifacts"] if a["id"] == mundo.id)
    assert artefacto["today"]["spent_usd"] == pytest.approx(0.12)
    assert artefacto["today"]["reasoning_spent_usd"] == pytest.approx(0.12)
    assert artefacto["today"]["reasoning_cap_reached"] is True


def test_el_bot_sigue_en_literal_aunque_el_artefacto_asignado_tenga_el_modo_plantilla(client, db, modes_config, make_artifact, monkeypatch):
    from tests.unit.test_bot_service import Pipeline as PipelineBot

    monkeypatch.setattr(settings, "bot_service_key", CLAVE)
    art = make_artifact("Bot", units=["u1"], modes="literal,razonamiento,plantilla", cap=1.0)
    from mia.storage.models import Document, Domain, Unit

    with db() as session:
        session.add(Unit(id="u1", name="Computación"))
        session.flush()
        session.add(Domain(id="dom-1", unit_id="u1", name="Admisión"))
        session.flush()
        session.add(Document(id="doc-1", domain_id="dom-1", filename="requisitos.pdf", source_type="pdf", file_hash="h", status="done"))
        session.add(Bot(id=str(uuid.uuid4()), name="Bot", kapso_number_id=NUMERO, artifact_id=art.id, active=True))
        session.commit()

    with PipelineBot():
        respuesta = client.post("/bot/query", json={"number_id": NUMERO, "question": "¿Cuándo es?", "mode": "plantilla", "template_id": "x"}, headers={"X-Bot-Service-Key": CLAVE})

    assert respuesta.status_code == 200 and respuesta.json()["mode"] == "literal"
    with db() as session:
        assert session.query(QueryLog).one().mode == "literal"
