"""Retomar una conversación guardada con la memoria de la feature 014 (feature 015, US4)."""

import pytest

from mia.config import settings
from mia.rag.history import REASONING_WARNING, HistoryTurn, format_history
from mia.storage.models import ConversationTurn
from tests.unit.chat_de_prueba import iniciar_sesion, preguntar_con_sesion, sembrar_conversacion
from tests.unit.historial_de_prueba import Pipeline, crear_mundo, fijar_memoria, vuelta

ANALITICA = "¿Cuándo empiezan las lecciones de la maestría en analítica de negocio?"


@pytest.fixture
def mundo(db, modes_config, make_artifact, monkeypatch):
    monkeypatch.setattr(settings, "history_reformulation", "rules")
    return crear_mundo(db, make_artifact, monkeypatch, context_turns=3)


def _turnos_guardados(db, cid):
    with db() as session:
        return session.query(ConversationTurn).filter_by(conversation_id=cid).count()


def test_con_memoria_n_la_consulta_lleva_las_ultimas_n_vueltas_guardadas(client, db, mundo):
    ana = iniciar_sesion(db)
    cid = sembrar_conversacion(db, ana["uid"], vueltas=5)

    with Pipeline() as pipeline:
        respuesta = preguntar_con_sesion(
            client, mundo, ana, "¿y el costo de analítica?", conversacion=cid
        )

    assert respuesta.status_code == 200
    assert pipeline.historial_al_modelo == [
        HistoryTurn("pregunta 3", "respuesta 3", "literal"),
        HistoryTurn("pregunta 4", "respuesta 4", "literal"),
        HistoryTurn("pregunta 5", "respuesta 5", "literal"),
    ]
    assert _turnos_guardados(db, cid) == 6  # la vuelta nueva también se guarda


def test_con_memoria_cero_no_hay_historial_pero_la_conversacion_sigue_creciendo(client, db, mundo):
    fijar_memoria(db, mundo.id, 0)
    ana = iniciar_sesion(db)
    cid = sembrar_conversacion(db, ana["uid"], vueltas=3)

    with Pipeline() as pipeline:
        preguntar_con_sesion(client, mundo, ana, "¿y el costo de analítica?", conversacion=cid)

    assert pipeline.historial_al_modelo is None
    assert _turnos_guardados(db, cid) == 4


def test_el_historial_que_manda_el_cliente_se_ignora_con_sesion(client, db, mundo):
    ana = iniciar_sesion(db)
    cid = sembrar_conversacion(db, ana["uid"], vueltas=2)
    falso = [vuelta("pregunta inventada", "respuesta inventada")]

    with Pipeline() as con_conversacion:
        preguntar_con_sesion(
            client, mundo, ana, "¿y el costo de analítica?", conversacion=cid, historial=falso
        )
    with Pipeline() as conversacion_nueva:
        preguntar_con_sesion(
            client, mundo, ana, "¿Cuándo empiezan las lecciones de analítica?", historial=falso
        )

    assert [t.question for t in con_conversacion.historial_al_modelo] == [
        "pregunta 1",
        "pregunta 2",
    ]
    assert (
        conversacion_nueva.historial_al_modelo is None
    )  # una conversación nueva no tiene vueltas anteriores


def test_un_seguimiento_corto_sobre_una_conversacion_guardada_encuentra_el_documento(
    client, db, mundo
):
    ana = iniciar_sesion(db)
    cid = sembrar_conversacion(
        db, ana["uid"], textos=[(ANALITICA, "Inician el 5 de octubre de 2026.", "literal", False)]
    )

    with Pipeline() as pipeline:
        cuerpo = preguntar_con_sesion(
            client, mundo, ana, "¿y cuánto cuesta?", conversacion=cid
        ).json()

    assert cuerpo["no_info"] is False and cuerpo["saved"] is True
    assert {s["document"] for s in cuerpo["sources"]} == {
        "ana-admision.txt",
        "ana-presentacion.txt",
    }
    assert pipeline.textos == [
        f"{ANALITICA} ¿y cuánto cuesta?"
    ]  # la búsqueda se reformula con la pregunta guardada
    llamada = pipeline.llm.answer.call_args
    assert llamada.args[0] == "¿y cuánto cuesta?"  # el modelo recibe la pregunta original


def test_una_conversacion_con_ambos_modos_conserva_las_reglas_de_la_014(client, db, mundo):
    ana = iniciar_sesion(db)
    cid = sembrar_conversacion(
        db,
        ana["uid"],
        textos=[
            (
                "¿Cuántos créditos suman los bloques?",
                "Suman 35 créditos (calculado).",
                "razonamiento",
                False,
            ),
            ("¿Cuándo empieza?", "Inicia en octubre.", "literal", False),
        ],
    )

    with Pipeline() as literal:
        preguntar_con_sesion(client, mundo, ana, "¿y el costo de analítica?", conversacion=cid)
    with Pipeline() as razonamiento:
        preguntar_con_sesion(
            client, mundo, ana, "¿y el costo de analítica?", conversacion=cid, modo="razonamiento"
        )

    for pipeline in (literal, razonamiento):
        bloque = format_history(pipeline.historial_al_modelo)
        assert (
            bloque.count(REASONING_WARNING) == 1
        )  # solo la vuelta de razonamiento lleva la advertencia
        assert "Suman 35 créditos" in bloque


def test_las_vueltas_de_sin_informacion_no_entran_al_historial(client, db, mundo):
    ana = iniciar_sesion(db)
    cid = sembrar_conversacion(
        db,
        ana["uid"],
        textos=[
            ("¿Cuándo empieza?", "Inicia en octubre.", "literal", False),
            (
                "¿Cuánto cuesta la luna?",
                "No encontré información suficiente en los documentos.",
                "literal",
                True,
            ),
        ],
    )

    with Pipeline() as pipeline:
        preguntar_con_sesion(client, mundo, ana, "¿y el costo de analítica?", conversacion=cid)

    assert [t.question for t in pipeline.historial_al_modelo] == ["¿Cuándo empieza?"]


def test_retomar_con_otro_artefacto_usa_la_memoria_del_artefacto_actual(
    client, db, mundo, make_artifact
):
    otro = make_artifact("Otro artefacto", units=["u1"], modes="literal", cap=1.0)
    fijar_memoria(db, otro.id, 1)
    ana = iniciar_sesion(db)
    cid = sembrar_conversacion(db, ana["uid"], vueltas=4)

    with Pipeline() as pipeline:
        preguntar_con_sesion(client, otro, ana, "¿y el costo de analítica?", conversacion=cid)

    assert [t.question for t in pipeline.historial_al_modelo] == ["pregunta 4"]
    assert _turnos_guardados(db, cid) == 5  # todas las vueltas guardadas siguen ahí


def test_con_el_guardado_apagado_se_usa_el_historial_del_cliente_como_en_la_014_y_no_se_guarda(
    client, db, mundo, monkeypatch
):
    monkeypatch.setattr(settings, "chat_retention_days", 0)
    ana = iniciar_sesion(db)

    with Pipeline() as pipeline:
        respuesta = preguntar_con_sesion(
            client,
            mundo,
            ana,
            "¿y cuánto cuesta?",
            historial=[vuelta(ANALITICA, "Inician el 5 de octubre.")],
        )

    assert respuesta.status_code == 200 and "conversation_id" not in respuesta.json()
    assert [t.question for t in pipeline.historial_al_modelo] == [ANALITICA]
    with db() as session:
        assert session.query(ConversationTurn).count() == 0
