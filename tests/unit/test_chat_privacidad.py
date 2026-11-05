"""Aislamiento y privacidad del historial de chats (feature 015, US6)."""

import json
import logging
import uuid

import pytest
from sqlalchemy import text

from mia.chat import retention
from mia.config import settings
from mia.storage.models import Bot, Conversation, ConversationTurn
from tests.unit.chat_de_prueba import (
    CLAVE_DE_PRUEBA,
    PREGUNTA,
    iniciar_sesion,
    preguntar_con_sesion,
    sembrar_conversacion,
)
from tests.unit.historial_de_prueba import Pipeline, crear_mundo, preguntar

SECRETO = "secreto-conv-77"
COORD = "coord.comp@itcr.ac.cr"
OPERADOR = "operador@itcr.ac.cr"
NO_ENCONTRADA = {"detail": "Conversación no encontrada."}


@pytest.fixture
def mundo(db, modes_config, make_artifact, make_admin, monkeypatch):
    artefacto = crear_mundo(db, make_artifact, monkeypatch, context_turns=3)  # crea el programa "Computación"
    make_admin(COORD, units=["Computación"])
    make_admin(OPERADOR, global_=True)
    return artefacto


def test_cada_ruta_trata_la_conversacion_del_otro_como_inexistente_con_el_mismo_cuerpo(client, db, mundo):
    ana = iniciar_sesion(db, "ana")
    beto = iniciar_sesion(db, "beto")
    de_ana = sembrar_conversacion(db, ana["uid"], 2, SECRETO)
    falsa = str(uuid.uuid4())

    for cid in (de_ana, falsa):
        with Pipeline():
            respuestas = [
                client.get(f"/conversations/{cid}", headers=beto["headers"]),
                client.delete(f"/conversations/{cid}", headers=beto["headers"]),
                preguntar_con_sesion(client, mundo, beto, conversacion=cid),
            ]
        for respuesta in respuestas:
            assert respuesta.status_code == 404 and respuesta.json() == NO_ENCONTRADA, cid
            assert SECRETO not in respuesta.text
    # La de ana sigue intacta y la lista de beto no la incluye.
    assert client.get("/conversations", headers=beto["headers"]).json()["conversations"] == []
    with db() as session:
        assert session.get(Conversation, de_ana) is not None


def test_ninguna_ruta_de_administracion_devuelve_el_texto_de_una_conversacion(client, db, mundo, admin, as_user):
    ana = iniciar_sesion(db)
    sembrar_conversacion(
        db,
        ana["uid"],
        textos=[(f"pregunta con {SECRETO}", f"respuesta con {SECRETO}", "literal", False)],
        titulo=f"titulo con {SECRETO}",
    )
    rutas = ["/consulta-users", "/usage", "/artifacts", "/bots", "/me", "/inventory", "/equivalences", "/query/log"]

    for cabecera in (admin, as_user(OPERADOR), as_user(COORD)):
        for ruta in rutas:
            respuesta = client.get(ruta, headers=cabecera)
            assert SECRETO not in respuesta.text, f"{ruta} devolvió el texto de una conversación"


def test_la_base_no_guarda_la_clave_del_artefacto_ni_contrasenas_ni_tokens_en_claro(client, db, mundo):
    ana = iniciar_sesion(db)
    with Pipeline():
        preguntar_con_sesion(client, mundo, ana)

    with db() as session:
        tablas = [
            "queries",
            "artifacts",
            "bots",
            "bot_message_counts",
            "consulta_users",
            "consulta_sessions",
            "conversations",
            "conversation_turns",
        ]
        volcado = ""
        for tabla in tablas:
            volcado += repr(session.execute(text(f"SELECT * FROM {tabla}")).fetchall())
    assert mundo.key not in volcado
    assert CLAVE_DE_PRUEBA not in volcado and ana["token"] not in volcado
    assert "scrypt$" in volcado  # el hash sí está, la contraseña no


def test_las_conversaciones_no_guardan_la_clave_ni_enlaces_a_uso_ni_costos(db):
    columnas = {c.name for t in (Conversation, ConversationTurn) for c in t.__table__.columns}

    assert not (columnas & {"artifact_id", "artifact_key", "key", "key_hash", "phone", "cost_usd", "query_id"})
    from mia.storage.models import QueryLog

    assert not {c.name for c in QueryLog.__table__.columns} & {"conversation_id", "user_id"}


def test_uso_guarda_solo_la_pregunta_actual_y_no_las_respuestas(client, db, mundo):
    ana = iniciar_sesion(db)
    with Pipeline(respuesta="respuesta-que-no-va-a-uso-31"):
        cid = preguntar_con_sesion(client, mundo, ana).json()["conversation_id"]
        preguntar_con_sesion(client, mundo, ana, "¿y los requisitos de analítica?", conversacion=cid)

    with db() as session:
        registros = session.execute(text("SELECT question, sources, reject_reason FROM queries")).fetchall()
    assert sorted(r[0] for r in registros) == sorted([PREGUNTA, "¿y los requisitos de analítica?"])
    assert "respuesta-que-no-va-a-uso-31" not in repr(registros)


def test_la_salida_de_registro_no_contiene_preguntas_respuestas_titulos_contrasenas_ni_tokens(
    client, db, mundo, caplog, capsys
):
    ana = iniciar_sesion(db)
    with caplog.at_level(logging.DEBUG), Pipeline(respuesta="respuesta-sensible-9"):
        cuerpo = preguntar_con_sesion(client, mundo, ana, f"¿Qué dice {SECRETO} de analítica?").json()
        client.get("/conversations", headers=ana["headers"])
        client.get(f"/conversations/{cuerpo['conversation_id']}", headers=ana["headers"])
        client.delete(f"/conversations/{cuerpo['conversation_id']}", headers=ana["headers"])
        client.post("/auth/login", json={"username": "ana", "password": CLAVE_DE_PRUEBA})
        retention.reset_purge_clock()
        with db() as session:
            retention.purge_expired(session)

    salida = caplog.text + capsys.readouterr().out
    for secreto in (SECRETO, "respuesta-sensible-9", CLAVE_DE_PRUEBA, ana["token"]):
        assert secreto not in salida, secreto


def test_la_consulta_anonima_y_la_del_bot_no_dejan_conversaciones(client, db, mundo, monkeypatch):
    from mia.config import settings as ajustes

    with Pipeline():
        anonima = preguntar(client, mundo, PREGUNTA)
    assert anonima.status_code == 200 and "conversation_id" not in anonima.json()

    monkeypatch.setattr(ajustes, "bot_service_key", "clave-del-servicio-de-prueba")
    with db() as session:
        session.add(Bot(id=str(uuid.uuid4()), name="Bot", kapso_number_id="111", artifact_id=mundo.id))
        session.commit()
    with Pipeline():
        bot = client.post(
            "/bot/query",
            json={"number_id": "111", "question": PREGUNTA},
            headers={"X-Bot-Service-Key": "clave-del-servicio-de-prueba"},
        )
    assert bot.status_code == 200 and "conversation_id" not in bot.json()
    with db() as session:
        assert session.query(Conversation).count() == 0
        assert session.query(ConversationTurn).count() == 0


def test_una_sesion_no_amplia_lo_que_el_artefacto_permite(client, db, mundo):
    ana = iniciar_sesion(db)
    cuerpo = {"domains": ["otro-dominio"], "question": PREGUNTA, "mode": "literal"}

    with Pipeline() as pipeline:
        respuesta = client.post("/query", json=cuerpo, headers={**mundo.headers, **ana["headers"]})

    assert respuesta.status_code == 403
    pipeline.llm.answer.assert_not_called()
    with db() as session:
        assert session.query(Conversation).count() == 0


def test_la_respuesta_de_la_lista_no_trae_campos_de_otros_usuarios(client, db):
    ana = iniciar_sesion(db, "ana")
    beto = iniciar_sesion(db, "beto")
    sembrar_conversacion(db, ana["uid"], 1, "de ana")
    sembrar_conversacion(db, beto["uid"], 1, "de beto")

    cuerpo = json.dumps(client.get("/conversations", headers=ana["headers"]).json())

    assert "de ana" in cuerpo and "de beto" not in cuerpo and beto["uid"] not in cuerpo
    assert settings.chat_retention_days > 0
