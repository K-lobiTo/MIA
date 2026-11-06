"""Rutas de conversaciones guardadas (feature 015): contracts/conversaciones-api.md."""

import uuid

import pytest

from mia.config import settings
from mia.storage.models import Conversation, ConversationTurn
from tests.unit.chat_de_prueba import iniciar_sesion, preguntar_con_sesion, sembrar_conversacion
from tests.unit.historial_de_prueba import Pipeline, crear_mundo

NO_ENCONTRADA = {"detail": "Conversación no encontrada."}


@pytest.fixture
def mundo(db, modes_config, make_artifact, monkeypatch):
    return crear_mundo(db, make_artifact, monkeypatch, context_turns=3)


def test_la_lista_trae_solo_las_del_usuario_de_la_mas_reciente_a_la_mas_antigua(client, db):
    ana = iniciar_sesion(db, "ana")
    beto = iniciar_sesion(db, "beto")
    vieja = sembrar_conversacion(db, ana["uid"], 3, "Vieja", hace_dias=5)
    nueva = sembrar_conversacion(db, ana["uid"], 1, "Nueva", hace_dias=1)
    sembrar_conversacion(db, beto["uid"], 2, "De beto")

    cuerpo = client.get("/conversations", headers=ana["headers"]).json()

    assert cuerpo["retention_days"] == settings.chat_retention_days
    assert [c["id"] for c in cuerpo["conversations"]] == [nueva, vieja]
    primera = cuerpo["conversations"][0]
    assert set(primera) == {"id", "title", "created_at", "updated_at", "turn_count"}
    assert primera["title"] == "Nueva" and primera["turn_count"] == 1
    assert cuerpo["conversations"][1]["turn_count"] == 3


def test_abrir_una_conversacion_devuelve_sus_vueltas_en_orden_con_fuentes_y_modo(client, db):
    ana = iniciar_sesion(db)
    cid = sembrar_conversacion(db, ana["uid"], 3)

    cuerpo = client.get(f"/conversations/{cid}", headers=ana["headers"]).json()

    assert cuerpo["id"] == cid and cuerpo["title"] == "Conversación sembrada"
    assert [t["position"] for t in cuerpo["turns"]] == [1, 2, 3]
    assert set(cuerpo["turns"][0]) == {
        "position",
        "question",
        "answer",
        "sources",
        "mode",
        "no_info",
        "created_at",
    }
    assert (
        cuerpo["turns"][1]["question"] == "pregunta 2" and cuerpo["turns"][1]["mode"] == "literal"
    )


def test_sin_sesion_o_con_una_invalida_es_session_invalid(client, db):
    ana = iniciar_sesion(db)
    cid = sembrar_conversacion(db, ana["uid"])

    for ruta in ("/conversations", f"/conversations/{cid}"):
        sin = client.get(ruta)
        mala = client.get(ruta, headers={"X-Session-Token": "mias_mala"})
        assert sin.status_code == mala.status_code == 401
        assert sin.json()["code"] == mala.json()["code"] == "session_invalid"


def test_una_conversacion_ajena_y_una_inexistente_dan_el_mismo_404(client, db):
    ana = iniciar_sesion(db, "ana")
    beto = iniciar_sesion(db, "beto")
    de_ana = sembrar_conversacion(db, ana["uid"])

    ajena = client.get(f"/conversations/{de_ana}", headers=beto["headers"])
    inexistente = client.get(f"/conversations/{uuid.uuid4()}", headers=beto["headers"])

    assert ajena.status_code == inexistente.status_code == 404
    assert ajena.json() == inexistente.json() == NO_ENCONTRADA


def test_con_el_maximo_de_vueltas_la_siguiente_consulta_es_409_sin_llamar_al_modelo(
    client, db, mundo, monkeypatch
):
    monkeypatch.setattr(settings, "chat_max_turns", 3)
    ana = iniciar_sesion(db)
    cid = sembrar_conversacion(db, ana["uid"], vueltas=3)

    with Pipeline() as pipeline:
        respuesta = preguntar_con_sesion(client, mundo, ana, conversacion=cid)

    assert respuesta.status_code == 409 and respuesta.json()["code"] == "conversation_full"
    pipeline.llm.answer.assert_not_called()
    pipeline.embeddings.embed.assert_not_called()
    with db() as session:
        assert session.query(ConversationTurn).filter_by(conversation_id=cid).count() == 3


def test_con_el_maximo_de_conversaciones_crear_otra_es_409_sin_llamar_al_modelo(
    client, db, mundo, monkeypatch
):
    monkeypatch.setattr(settings, "chat_max_conversations", 2)
    ana = iniciar_sesion(db)
    sembrar_conversacion(db, ana["uid"])
    existente = sembrar_conversacion(db, ana["uid"])

    with Pipeline() as pipeline:
        nueva = preguntar_con_sesion(client, mundo, ana)
    with Pipeline():
        continuar = preguntar_con_sesion(client, mundo, ana, conversacion=existente)

    assert nueva.status_code == 409 and nueva.json()["code"] == "too_many_conversations"
    pipeline.llm.answer.assert_not_called()
    assert continuar.status_code == 200  # seguir en una existente sí se puede


def test_continuar_en_una_conversacion_ajena_o_inexistente_es_404_sin_llamar_al_modelo(
    client, db, mundo
):
    ana = iniciar_sesion(db, "ana")
    beto = iniciar_sesion(db, "beto")
    de_ana = sembrar_conversacion(db, ana["uid"])

    with Pipeline() as pipeline:
        ajena = preguntar_con_sesion(client, mundo, beto, conversacion=de_ana)
        falsa = preguntar_con_sesion(client, mundo, beto, conversacion=str(uuid.uuid4()))

    assert ajena.status_code == falsa.status_code == 404
    assert ajena.json() == falsa.json() == NO_ENCONTRADA
    pipeline.llm.answer.assert_not_called()


def test_con_el_guardado_apagado_la_lista_es_vacia_y_no_se_guarda_nada(
    client, db, mundo, monkeypatch
):
    monkeypatch.setattr(settings, "chat_retention_days", 0)
    ana = iniciar_sesion(db)

    with Pipeline():
        respuesta = preguntar_con_sesion(client, mundo, ana)
    lista = client.get("/conversations", headers=ana["headers"]).json()

    assert respuesta.status_code == 200 and "conversation_id" not in respuesta.json()
    assert lista == {"retention_days": 0, "conversations": []}
    with db() as session:
        assert session.query(Conversation).count() == 0


def test_un_usuario_desactivado_pierde_el_acceso_a_su_lista(client, db):
    from mia.storage.models import ConsultaUser

    ana = iniciar_sesion(db)
    sembrar_conversacion(db, ana["uid"])
    with db() as session:
        session.get(ConsultaUser, ana["uid"]).active = False
        session.commit()

    assert client.get("/conversations", headers=ana["headers"]).json()["code"] == "session_invalid"


def test_renombrar_cambia_el_titulo_sin_mover_la_conversacion_en_la_lista(client, db):
    ana = iniciar_sesion(db, "ana")
    vieja = sembrar_conversacion(db, ana["uid"], 3, "Vieja", hace_dias=5)
    sembrar_conversacion(db, ana["uid"], 1, "Nueva", hace_dias=1)
    antes = client.get("/conversations", headers=ana["headers"]).json()["conversations"]

    respuesta = client.patch(
        f"/conversations/{vieja}", json={"title": "  Costos   de la\nmaestría  "}, headers=ana["headers"]
    )

    assert respuesta.status_code == 200
    assert respuesta.json()["title"] == "Costos de la maestría" and respuesta.json()["turn_count"] == 3
    despues = client.get("/conversations", headers=ana["headers"]).json()["conversations"]
    assert [c["id"] for c in despues] == [c["id"] for c in antes]
    assert [c["updated_at"] for c in despues] == [c["updated_at"] for c in antes]
    assert next(c for c in despues if c["id"] == vieja)["title"] == "Costos de la maestría"


def test_renombrar_recorta_el_titulo_largo(client, db):
    ana = iniciar_sesion(db)
    cid = sembrar_conversacion(db, ana["uid"])
    respuesta = client.patch(f"/conversations/{cid}", json={"title": "x" * 150}, headers=ana["headers"])
    assert respuesta.status_code == 200 and len(respuesta.json()["title"]) == 80


@pytest.mark.parametrize("titulo", ["", "   ", "x" * 201])
def test_renombrar_rechaza_un_titulo_vacio_o_demasiado_largo(client, db, titulo):
    ana = iniciar_sesion(db)
    cid = sembrar_conversacion(db, ana["uid"])
    assert client.patch(f"/conversations/{cid}", json={"title": titulo}, headers=ana["headers"]).status_code == 422
    assert client.get(f"/conversations/{cid}", headers=ana["headers"]).json()["title"] == "Conversación sembrada"


def test_renombrar_una_ajena_o_inexistente_es_404_y_sin_sesion_es_401(client, db):
    ana = iniciar_sesion(db, "ana")
    beto = iniciar_sesion(db, "beto")
    de_beto = sembrar_conversacion(db, beto["uid"], 1, "De beto")

    ajena = client.patch(f"/conversations/{de_beto}", json={"title": "mía"}, headers=ana["headers"])
    falsa = client.patch(f"/conversations/{uuid.uuid4()}", json={"title": "x"}, headers=ana["headers"])
    sin_sesion = client.patch(f"/conversations/{de_beto}", json={"title": "x"})

    assert ajena.status_code == 404 and ajena.json() == NO_ENCONTRADA
    assert falsa.status_code == 404
    assert sin_sesion.status_code == 401
    assert client.get(f"/conversations/{de_beto}", headers=beto["headers"]).json()["title"] == "De beto"
