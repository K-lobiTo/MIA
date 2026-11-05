"""POST /query con sesión: guarda la vuelta en la conversación del usuario (feature 015, US3)."""

import json
import logging

import pytest

from mia.chat import service
from mia.config import settings
from mia.storage.models import Conversation, ConversationTurn, QueryLog
from tests.unit.chat_de_prueba import (
    PREGUNTA,
    SIN_RESPUESTA,
    iniciar_sesion,
    preguntar_con_sesion,
)
from tests.unit.historial_de_prueba import Pipeline, crear_mundo, preguntar

CAMPOS_DE_QUERY = {"id", "answer", "sources", "mode", "latency_ms", "no_info", "images"}


@pytest.fixture
def mundo(db, modes_config, make_artifact, monkeypatch):
    monkeypatch.setattr(settings, "history_reformulation", "rules")
    return crear_mundo(db, make_artifact, monkeypatch, context_turns=3)


def _conversaciones(db):
    with db() as session:
        return session.query(Conversation).order_by(Conversation.created_at).all()


def _vueltas(db, cid):
    with db() as session:
        return (
            session.query(ConversationTurn)
            .filter_by(conversation_id=cid)
            .order_by(ConversationTurn.position)
            .all()
        )


def test_la_primera_pregunta_crea_la_conversacion_con_su_titulo_y_guarda_la_vuelta(
    client, db, mundo
):
    sesion = iniciar_sesion(db)
    with Pipeline(respuesta="Inician el 5 de octubre."):
        respuesta = preguntar_con_sesion(client, mundo, sesion)

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert set(cuerpo) == CAMPOS_DE_QUERY | {"conversation_id", "saved"}
    assert cuerpo["saved"] is True
    [conversacion] = _conversaciones(db)
    assert cuerpo["conversation_id"] == conversacion.id and conversacion.user_id == sesion["uid"]
    assert conversacion.title == PREGUNTA
    [vuelta] = _vueltas(db, conversacion.id)
    assert (vuelta.position, vuelta.question, vuelta.answer) == (1, PREGUNTA, cuerpo["answer"])
    assert vuelta.mode == "literal" and vuelta.no_info is False
    fuentes = json.loads(vuelta.sources)
    assert fuentes and set(fuentes[0]) == {"domain", "document"}
    assert {f["document"] for f in fuentes} == {s["document"] for s in cuerpo["sources"]}


def test_el_titulo_se_recorta_en_un_limite_de_palabra_y_normaliza_los_espacios():
    largo = "¿Cuándo   empiezan  las lecciones " + "de la maestría en analítica de negocio " * 4
    titulo = service.make_title(largo)

    assert len(titulo) <= 63 and titulo.endswith("...")
    assert "  " not in titulo and not titulo[:-3].endswith(" ")
    assert titulo.startswith("¿Cuándo empiezan las lecciones")
    assert service.make_title("  corta  ") == "corta"


def test_con_conversation_id_la_vuelta_se_agrega_a_la_misma_conversacion(client, db, mundo):
    sesion = iniciar_sesion(db)
    with Pipeline():
        primera = preguntar_con_sesion(client, mundo, sesion).json()
        antes = _conversaciones(db)[0].updated_at
        segunda = preguntar_con_sesion(
            client,
            mundo,
            sesion,
            "¿Y los requisitos de analítica?",
            conversacion=primera["conversation_id"],
        ).json()

    assert segunda["conversation_id"] == primera["conversation_id"] and segunda["saved"] is True
    [conversacion] = _conversaciones(db)
    assert [v.position for v in _vueltas(db, conversacion.id)] == [1, 2]
    assert conversacion.updated_at >= antes
    assert conversacion.title == PREGUNTA  # el título es el de la primera pregunta


def test_una_respuesta_de_sin_informacion_si_se_guarda(client, db, mundo):
    sesion = iniciar_sesion(db)
    with Pipeline() as pipeline:
        respuesta = preguntar_con_sesion(client, mundo, sesion, SIN_RESPUESTA)

    assert respuesta.json()["no_info"] is True
    pipeline.llm.answer.assert_not_called()
    [conversacion] = _conversaciones(db)
    [vuelta] = _vueltas(db, conversacion.id)
    assert vuelta.no_info is True and vuelta.question == SIN_RESPUESTA


def test_una_consulta_que_falla_no_guarda_nada_ni_crea_conversacion(client, db, mundo):
    sesion = iniciar_sesion(db)
    with Pipeline() as pipeline:
        pipeline.llm.answer.side_effect = RuntimeError("proveedor caído")
        proveedor = preguntar_con_sesion(client, mundo, sesion)

    assert proveedor.status_code == 502
    assert _conversaciones(db) == []


def test_un_modo_no_permitido_o_un_tope_alcanzado_no_guardan_nada(
    db, modes_config, make_artifact, monkeypatch, client
):
    solo_literal = crear_mundo(db, make_artifact, monkeypatch, context_turns=3, modes="literal")
    sesion = iniciar_sesion(db)
    with Pipeline() as pipeline:
        respuesta = preguntar_con_sesion(client, solo_literal, sesion, modo="razonamiento")

    assert respuesta.status_code == 403
    pipeline.llm.answer.assert_not_called()
    assert _conversaciones(db) == []


def test_si_guardar_falla_la_respuesta_se_entrega_con_saved_falso_y_sin_el_texto_en_el_registro(
    client, db, mundo, monkeypatch, caplog
):
    sesion = iniciar_sesion(db)

    def roto(*args, **kwargs):
        raise RuntimeError("disco lleno con texto secreto-guardado-55")

    monkeypatch.setattr(service, "append_turn", roto)
    with Pipeline(), caplog.at_level(logging.DEBUG):
        respuesta = preguntar_con_sesion(client, mundo, sesion)

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["saved"] is False and cuerpo["answer"]
    assert _conversaciones(db) == []
    assert "secreto-guardado-55" not in caplog.text and PREGUNTA not in caplog.text


def test_dos_consultas_seguidas_no_pierden_ni_duplican_vueltas(client, db, mundo):
    sesion = iniciar_sesion(db)
    with Pipeline():
        cid = preguntar_con_sesion(client, mundo, sesion).json()["conversation_id"]
        for _ in range(3):
            preguntar_con_sesion(client, mundo, sesion, conversacion=cid)

    assert [v.position for v in _vueltas(db, cid)] == [1, 2, 3, 4]


def test_una_respuesta_muy_larga_se_guarda_cortada_al_maximo(client, db, mundo, monkeypatch):
    monkeypatch.setattr(settings, "chat_max_answer_chars", 1000)
    sesion = iniciar_sesion(db)
    with Pipeline(respuesta="r" * 5000):
        cuerpo = preguntar_con_sesion(client, mundo, sesion).json()

    assert len(cuerpo["answer"]) == 5000  # al usuario le llega completa
    [vuelta] = _vueltas(db, cuerpo["conversation_id"])
    assert len(vuelta.answer) == 1000


def test_guardar_no_llama_al_modelo_ni_al_almacen_de_mas(client, db, mundo):
    sesion = iniciar_sesion(db)
    with Pipeline() as con:
        preguntar_con_sesion(client, mundo, sesion)
    with Pipeline() as sin:
        preguntar(client, mundo, PREGUNTA)

    assert con.llm.answer.call_count == sin.llm.answer.call_count == 1
    assert con.store.search.call_count == sin.store.search.call_count
    assert con.embeddings.embed.call_count == sin.embeddings.embed.call_count


def test_el_registro_de_uso_sigue_guardando_solo_la_pregunta_actual(client, db, mundo):
    sesion = iniciar_sesion(db)
    with Pipeline():
        cid = preguntar_con_sesion(client, mundo, sesion).json()["conversation_id"]
        preguntar_con_sesion(client, mundo, sesion, "¿y cuánto cuesta?", conversacion=cid)

    with db() as session:
        preguntas = sorted(r.question for r in session.query(QueryLog).all())
    assert preguntas == sorted([PREGUNTA, "¿y cuánto cuesta?"])
