"""Compatibilidad y "exigir inicio de sesión" (feature 015, US7): sin sesión todo sigue como hoy."""

import json
import uuid
from decimal import Decimal

import pytest

from mia.config import settings
from mia.storage.models import Artifact, Bot, Conversation, QueryLog
from tests.unit.chat_de_prueba import PREGUNTA, iniciar_sesion, preguntar_con_sesion
from tests.unit.historial_de_prueba import Pipeline, crear_mundo, preguntar, vuelta

CAMPOS_DE_QUERY = {"id", "answer", "sources", "mode", "latency_ms", "no_info", "images"}
COORD = "coord.comp@itcr.ac.cr"
OPERADOR = "operador@itcr.ac.cr"
ANALITICA = "¿Cuándo empiezan las lecciones de la maestría en analítica de negocio?"


@pytest.fixture
def mundo(db, modes_config, make_artifact, monkeypatch):
    monkeypatch.setattr(settings, "history_reformulation", "rules")
    return crear_mundo(db, make_artifact, monkeypatch, context_turns=3)


def _exigir_sesion(db, artifact_id, valor=True):
    with db() as session:
        session.get(Artifact, artifact_id).require_login = valor
        session.commit()


def _lineas(capsys):
    return [json.loads(x) for x in capsys.readouterr().out.splitlines() if x.startswith("{")]


# --- Sin sesión, como hoy ---------------------------------------------------------------------------------------


def test_sin_sesion_la_respuesta_tiene_exactamente_los_campos_de_hoy_y_no_guarda_nada(client, db, mundo):
    with Pipeline():
        respuesta = preguntar(client, mundo, PREGUNTA)

    assert respuesta.status_code == 200
    assert set(respuesta.json()) == CAMPOS_DE_QUERY
    with db() as session:
        assert session.query(Conversation).count() == 0


def test_sin_sesion_se_sigue_usando_el_historial_del_cliente_de_la_014(client, mundo):
    with Pipeline() as pipeline:
        preguntar(client, mundo, "¿y cuánto cuesta?", historial=[vuelta(ANALITICA, "Inician el 5 de octubre.")])

    assert [t.question for t in pipeline.historial_al_modelo] == [ANALITICA]


def test_un_conversation_id_sin_sesion_se_ignora(client, db, mundo):
    with Pipeline():
        respuesta = client.post(
            "/query",
            json={"domains": ["dom-1"], "question": PREGUNTA, "conversation_id": str(uuid.uuid4())},
            headers=mundo.headers,
        )

    assert respuesta.status_code == 200 and set(respuesta.json()) == CAMPOS_DE_QUERY
    with db() as session:
        assert session.query(Conversation).count() == 0


def test_los_artefactos_nuevos_y_los_existentes_nacen_sin_exigir_sesion(db, make_artifact):
    artefacto = make_artifact("Nuevo")
    with db() as session:
        assert session.get(Artifact, artefacto.id).require_login is False


# --- Exigir inicio de sesión ------------------------------------------------------------------------------------


def test_con_require_login_y_sin_sesion_responde_401_login_required_sin_buscar_ni_llamar_al_modelo(client, db, mundo):
    _exigir_sesion(db, mundo.id)

    with Pipeline() as pipeline:
        respuesta = preguntar(client, mundo, PREGUNTA)

    assert respuesta.status_code == 401
    assert respuesta.json()["code"] == "login_required"
    assert respuesta.json()["detail"] == "Este artefacto exige iniciar sesión para consultar."
    pipeline.embeddings.embed.assert_not_called()
    pipeline.store.search.assert_not_called()
    pipeline.llm.answer.assert_not_called()
    with db() as session:
        [registro] = session.query(QueryLog).all()
        assert registro.outcome == "rejected_permission" and registro.cost_usd == Decimal(0)
        assert registro.question == PREGUNTA


def test_con_require_login_y_sesion_valida_responde_y_guarda(client, db, mundo):
    _exigir_sesion(db, mundo.id)
    ana = iniciar_sesion(db)

    with Pipeline():
        respuesta = preguntar_con_sesion(client, mundo, ana)

    assert respuesta.status_code == 200 and respuesta.json()["saved"] is True


@pytest.mark.parametrize("exigir", [False, True])
def test_una_sesion_invalida_es_401_session_invalid_con_o_sin_require_login(client, db, mundo, exigir):
    _exigir_sesion(db, mundo.id, exigir)

    with Pipeline() as pipeline:
        respuesta = client.post(
            "/query",
            json={"domains": ["dom-1"], "question": PREGUNTA},
            headers={**mundo.headers, "X-Session-Token": "mias_inventado"},
        )

    assert respuesta.status_code == 401 and respuesta.json()["code"] == "session_invalid"
    pipeline.llm.answer.assert_not_called()


def test_el_artefacto_de_un_bot_con_require_login_sigue_respondiendole_al_bot(client, db, mundo, monkeypatch):
    _exigir_sesion(db, mundo.id)
    monkeypatch.setattr(settings, "bot_service_key", "clave-del-servicio-de-prueba")
    with db() as session:
        session.add(Bot(id=str(uuid.uuid4()), name="Bot", kapso_number_id="111", artifact_id=mundo.id))
        session.commit()

    with Pipeline():
        bot = client.post(
            "/bot/query",
            json={"number_id": "111", "question": PREGUNTA},
            headers={"X-Bot-Service-Key": "clave-del-servicio-de-prueba"},
        )
        mensajes = client.post(
            "/bot/messages",
            json={"number_id": "111", "received": 1, "sent": 0},
            headers={"X-Bot-Service-Key": "clave-del-servicio-de-prueba"},
        )

    assert bot.status_code == 200 and bot.json()["no_info"] is False
    assert mensajes.status_code == 200 and mensajes.json()["status"] == "ok"
    assert set(bot.json()) == CAMPOS_DE_QUERY | {"clarify", "programs"}


# --- La sesión no cambia lo que el artefacto permite -------------------------------------------------------------


def test_la_sesion_no_amplia_los_modos_los_dominios_ni_los_topes(db, modes_config, make_artifact, monkeypatch, client):
    solo_literal = crear_mundo(db, make_artifact, monkeypatch, context_turns=3, modes="literal", cap=0.01)
    ana = iniciar_sesion(db)
    with db() as session:
        session.add(
            QueryLog(
                id="gasto", artifact_id=solo_literal.id, question="q", domain_ids="[]", mode="literal",
                outcome="answered", cost_usd=Decimal("0.5"),
            )
        )
        session.commit()

    with Pipeline() as pipeline:
        modo = preguntar_con_sesion(client, solo_literal, ana, modo="razonamiento")
        tope = preguntar_con_sesion(client, solo_literal, ana)

    assert modo.status_code == 403
    assert tope.status_code == 429
    pipeline.llm.answer.assert_not_called()
    with db() as session:
        assert session.query(Conversation).count() == 0


# --- /config y administración del ajuste -------------------------------------------------------------------------


def test_config_con_la_clave_del_artefacto_trae_require_login_y_el_bloque_chat(client, db, mundo, monkeypatch):
    cuerpo = client.get("/config", headers=mundo.headers).json()
    assert cuerpo["artifact"]["require_login"] is False
    assert cuerpo["chat"] == {"enabled": True, "retention_days": settings.chat_retention_days}

    _exigir_sesion(db, mundo.id)
    monkeypatch.setattr(settings, "chat_retention_days", 0)
    cuerpo = client.get("/config", headers=mundo.headers).json()
    assert cuerpo["artifact"]["require_login"] is True
    assert cuerpo["chat"] == {"enabled": False, "retention_days": 0}


def test_config_sin_clave_no_cambia(client, mundo):
    cuerpo = client.get("/config").json()

    assert "artifact" not in cuerpo and "chat" not in cuerpo
    assert set(cuerpo) == {"ingestion_enabled", "max_upload_mb", "modes"}


@pytest.fixture
def con_admins(db, units, make_admin):
    from mia.storage.models import Domain

    with db() as session:
        session.add(Domain(id="dc", unit_id=units.comp, name="Currículum"))
        session.commit()
    make_admin(COORD, units=["Computación"])
    make_admin(OPERADOR, global_=True)
    return units


def _crear_artefacto(client, headers, units, **extra):
    cuerpo = {
        "name": "Nueva",
        "access": {"all_domains": False, "unit_ids": [units.comp], "domain_ids": []},
        "modes": ["literal"],
        **extra,
    }
    return client.post("/artifacts", json=cuerpo, headers=headers)


def test_crear_y_editar_un_artefacto_acepta_y_devuelve_require_login(client, con_admins, admin, capsys):
    creado = _crear_artefacto(client, admin, con_admins)
    assert creado.status_code == 201 and creado.json()["require_login"] is False
    con = _crear_artefacto(client, admin, con_admins, name="Con sesión", require_login=True)
    assert con.json()["require_login"] is True
    capsys.readouterr()

    cambiado = client.patch(f"/artifacts/{creado.json()['id']}", json={"require_login": True}, headers=admin)
    sin_cambio = client.patch(f"/artifacts/{creado.json()['id']}", json={"require_login": True}, headers=admin)

    assert cambiado.json()["require_login"] is True and sin_cambio.status_code == 200
    lineas = [x for x in _lineas(capsys) if x["action"] == "artifact.require_login"]
    assert [x["detail"] for x in lineas] == ["Nueva: false -> true"]
    listado = client.get("/artifacts", headers=admin).json()["artifacts"]
    assert {a["name"]: a["require_login"] for a in listado} == {"Nueva": True, "Con sesión": True}


def test_el_ajuste_respeta_el_alcance_del_artefacto(client, con_admins, admin, as_user):
    creado = _crear_artefacto(client, admin, con_admins).json()
    ajeno = _crear_artefacto(
        client,
        admin,
        con_admins,
        name="De administración",
        access={"all_domains": False, "unit_ids": [con_admins.adm], "domain_ids": []},
    ).json()

    propio = client.patch(f"/artifacts/{creado['id']}", json={"require_login": True}, headers=as_user(COORD))
    fuera = client.patch(f"/artifacts/{ajeno['id']}", json={"require_login": True}, headers=as_user(COORD))

    assert propio.status_code == 200 and propio.json()["require_login"] is True
    assert fuera.status_code == 404


def test_rige_desde_la_consulta_siguiente_sin_reiniciar(client, db, mundo, admin):
    with Pipeline():
        assert preguntar(client, mundo, PREGUNTA).status_code == 200
    client.patch(f"/artifacts/{mundo.id}", json={"require_login": True}, headers=admin)
    with Pipeline():
        assert preguntar(client, mundo, PREGUNTA).status_code == 401
    client.patch(f"/artifacts/{mundo.id}", json={"require_login": False}, headers=admin)
    with Pipeline():
        assert preguntar(client, mundo, PREGUNTA).status_code == 200
