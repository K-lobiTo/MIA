"""Los demás modos y artefactos no cambian (feature 020, US7): sin el modo plantilla habilitado, MIA responde como antes."""

import uuid

import pytest

from mia.config import settings
from mia.storage.models import Bot, Document, Domain, QueryLog, ResponseTemplate, Unit
from tests.unit.historial_de_prueba import Pipeline, crear_mundo, preguntar
from tests.unit.plantillas_de_prueba import plantilla_del_artefacto, preguntar_con_plantilla
from tests.unit.test_bot_service import CLAVE, NUMERO
from tests.unit.test_bot_service import Pipeline as PipelineBot

PREGUNTA = "¿Cuándo empiezan las lecciones de analítica?"


@pytest.fixture
def sin_el_modo(db, modes_config, make_artifact, monkeypatch):
    return crear_mundo(db, make_artifact, monkeypatch, modes="literal,razonamiento")


def test_un_artefacto_sin_el_modo_no_lo_ofrece_ni_lo_acepta(client, db, sin_el_modo):
    ana_headers = sin_el_modo.headers

    config = client.get("/config", headers=ana_headers).json()
    assert [m["id"] for m in config["modes"]] == ["literal", "razonamiento"]
    templates = client.get("/templates", headers=ana_headers).json()
    assert templates["enabled"] is False and templates["artifact"] == [] and templates["mine"] == []
    with Pipeline() as pipeline:
        consulta = preguntar_con_plantilla(client, sin_el_modo, PREGUNTA, "x")
    assert consulta.status_code == 403
    pipeline.llm.answer.assert_not_called()


def test_sin_el_modo_no_se_pueden_crear_plantillas_personales(client, db, sin_el_modo):
    from tests.unit.chat_de_prueba import iniciar_sesion

    ana = iniciar_sesion(db)

    respuesta = client.post("/templates", json={"name": "x", "content": "y", "scope": "all"}, headers={**sin_el_modo.headers, **ana["headers"]})

    assert respuesta.status_code == 403


def test_habilitar_el_modo_en_otro_artefacto_no_cambia_al_que_no_lo_tiene(client, db, sin_el_modo, make_artifact):
    con_modo = make_artifact("Con", all_domains=True, modes="literal,razonamiento,plantilla")
    plantilla_del_artefacto(db, con_modo.id)

    config = client.get("/config", headers=sin_el_modo.headers).json()
    templates = client.get("/templates", headers=sin_el_modo.headers).json()

    assert "plantilla" not in [m["id"] for m in config["modes"]]
    assert templates["enabled"] is False and templates["artifact"] == []
    with Pipeline() as pipeline:
        respuesta = preguntar(client, sin_el_modo, PREGUNTA)
    assert respuesta.status_code == 200 and respuesta.json()["mode"] == "literal"
    assert pipeline.llm.answer.call_count == 1


def test_literal_y_razonamiento_responden_igual_antes_y_despues_de_crear_plantillas(client, db, modes_config, make_artifact, monkeypatch):
    mundo = crear_mundo(db, make_artifact, monkeypatch, modes="literal,razonamiento,plantilla")

    def cuerpo_de(modo):
        with Pipeline("Respuesta fija.") as pipeline:
            respuesta = preguntar(client, mundo, PREGUNTA, modo=modo)
        llamada = pipeline.llm.answer.call_args
        with db() as session:
            registro = session.query(QueryLog).order_by(QueryLog.created_at.desc()).first()
        quitar = {"id", "latency_ms"}
        return (
            {k: v for k, v in respuesta.json().items() if k not in quitar},
            llamada.args[0], llamada.kwargs["instructions"],
            (registro.mode, registro.outcome, registro.question, float(registro.cost_usd), registro.model),
        )

    antes = {modo: cuerpo_de(modo) for modo in ("literal", "razonamiento")}
    plantilla_del_artefacto(db, mundo.id)
    despues = {modo: cuerpo_de(modo) for modo in ("literal", "razonamiento")}

    assert antes == despues
    assert antes["literal"][1] == PREGUNTA and "<<<PLANTILLA" not in antes["razonamiento"][1]


def test_el_bot_de_whatsapp_sigue_en_literal_y_su_pedido_no_acepta_modo_ni_plantilla(client, db, modes_config, make_artifact, monkeypatch):
    from mia.api.routes.bot_service import BotQuery

    monkeypatch.setattr(settings, "bot_service_key", CLAVE)
    art = make_artifact("Bot", units=["u1"], modes="literal,razonamiento,plantilla", cap=1.0)
    with db() as session:
        session.add(Unit(id="u1", name="Computación"))
        session.flush()
        session.add(Domain(id="dom-1", unit_id="u1", name="Admisión"))
        session.flush()
        session.add(Document(id="doc-1", domain_id="dom-1", filename="requisitos.pdf", source_type="pdf", file_hash="h", status="done"))
        session.add(Bot(id=str(uuid.uuid4()), name="Bot", kapso_number_id=NUMERO, artifact_id=art.id, active=True))
        session.commit()
    plantilla_del_artefacto(db, art.id)

    with PipelineBot():
        respuesta = client.post(
            "/bot/query",
            json={"number_id": NUMERO, "question": "¿Cuándo es la matrícula?"},
            headers={"X-Bot-Service-Key": CLAVE},
        )

    assert respuesta.status_code == 200 and respuesta.json()["mode"] == "literal"
    with db() as session:
        assert session.query(QueryLog).one().mode == "literal"
    assert set(BotQuery.model_fields) == {"number_id", "question"}


def test_quitar_el_modo_conserva_las_plantillas_y_reaparecen_al_habilitarlo(client, db, admin, modes_config, make_artifact, monkeypatch):
    mundo = crear_mundo(db, make_artifact, monkeypatch, modes="literal,razonamiento,plantilla")
    plantilla = plantilla_del_artefacto(db, mundo.id, "Informe")

    client.patch(f"/artifacts/{mundo.id}", json={"modes": ["literal", "razonamiento"]}, headers=admin)
    quitado = client.get("/templates", headers=mundo.headers).json()
    with db() as session:
        assert session.get(ResponseTemplate, plantilla) is not None
    assert quitado["enabled"] is False and quitado["artifact"] == []

    client.patch(f"/artifacts/{mundo.id}", json={"modes": ["literal", "razonamiento", "plantilla"]}, headers=admin)
    vuelto = client.get("/templates", headers=mundo.headers).json()
    assert vuelto["enabled"] is True and [t["id"] for t in vuelto["artifact"]] == [plantilla]
