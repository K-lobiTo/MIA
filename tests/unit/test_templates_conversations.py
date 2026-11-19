"""La conversación recuerda la plantilla usada (feature 020, US6): cada vuelta guarda el identificador y el nombre, nunca el
contenido; al editar o eliminar la plantilla la conversación no cambia."""

import pytest

from mia.config import settings
from mia.storage.models import ConversationTurn, ResponseTemplate
from tests.unit.chat_de_prueba import iniciar_sesion, preguntar_con_sesion
from tests.unit.historial_de_prueba import Pipeline, crear_mundo
from tests.unit.plantillas_de_prueba import CONTENIDO, plantilla_del_artefacto, plantilla_personal

PREGUNTA = "Prepárame el informe de la Maestría en Analítica"


@pytest.fixture
def mundo(db, modes_config, make_artifact, monkeypatch):
    monkeypatch.setattr(settings, "history_reformulation", "rules")
    return crear_mundo(db, make_artifact, monkeypatch, context_turns=3, modes="literal,razonamiento,plantilla")


def _vueltas(db):
    with db() as session:
        return session.query(ConversationTurn).order_by(ConversationTurn.position).all()


def test_una_vuelta_con_plantilla_guarda_su_id_y_su_nombre_y_nunca_el_contenido(client, db, mundo):
    ana = iniciar_sesion(db)
    plantilla = plantilla_del_artefacto(db, mundo.id, "Informe de programa", contenido="# Muy secreto 987")
    with Pipeline():
        respuesta = preguntar_con_sesion(client, mundo, ana, PREGUNTA, modo="plantilla", template_id=plantilla)

    assert respuesta.status_code == 200 and respuesta.json()["saved"] is True
    (vuelta,) = _vueltas(db)
    assert vuelta.mode == "plantilla" and vuelta.template_id == plantilla and vuelta.template_name == "Informe de programa"
    columnas = {c.name: str(getattr(vuelta, c.name)) for c in ConversationTurn.__table__.columns}
    assert not any("Muy secreto 987" in valor for valor in columnas.values())


def test_una_vuelta_de_otro_modo_deja_la_plantilla_nula(client, db, mundo):
    ana = iniciar_sesion(db)
    with Pipeline():
        preguntar_con_sesion(client, mundo, ana, PREGUNTA, modo="razonamiento")

    (vuelta,) = _vueltas(db)
    assert vuelta.template_id is None and vuelta.template_name is None


def test_abrir_la_conversacion_devuelve_la_plantilla_de_cada_vuelta(client, db, mundo):
    ana = iniciar_sesion(db)
    plantilla = plantilla_del_artefacto(db, mundo.id, "Informe de programa")
    with Pipeline():
        primera = preguntar_con_sesion(client, mundo, ana, PREGUNTA, modo="plantilla", template_id=plantilla).json()
        preguntar_con_sesion(client, mundo, ana, PREGUNTA, conversacion=primera["conversation_id"], modo="literal")

    abierta = client.get(f"/conversations/{primera['conversation_id']}", headers=ana["headers"]).json()

    assert [(t["mode"], t["template_id"], t["template_name"]) for t in abierta["turns"]] == [
        ("plantilla", plantilla, "Informe de programa"),
        ("literal", None, None),
    ]


def test_editar_la_plantilla_y_seguir_la_conversacion_usa_la_version_nueva(client, db, mundo):
    ana = iniciar_sesion(db)
    plantilla = plantilla_del_artefacto(db, mundo.id, "Informe", contenido="# Version vieja")
    with Pipeline():
        primera = preguntar_con_sesion(client, mundo, ana, PREGUNTA, modo="plantilla", template_id=plantilla).json()
    with db() as session:
        session.get(ResponseTemplate, plantilla).content = "# Version nueva"
        session.commit()

    with Pipeline() as pipeline:
        preguntar_con_sesion(client, mundo, ana, "amplía la sección de costos de analítica", conversacion=primera["conversation_id"], modo="plantilla", template_id=plantilla)

    mensaje = pipeline.llm.answer.call_args.args[0]
    assert "# Version nueva" in mensaje and "# Version vieja" not in mensaje


def test_eliminar_la_plantilla_no_toca_la_conversacion_y_una_consulta_nueva_responde_404(client, db, mundo):
    ana = iniciar_sesion(db)
    plantilla = plantilla_del_artefacto(db, mundo.id, "Informe")
    with Pipeline():
        primera = preguntar_con_sesion(client, mundo, ana, PREGUNTA, modo="plantilla", template_id=plantilla).json()
    with db() as session:
        session.delete(session.get(ResponseTemplate, plantilla))
        session.commit()

    abierta = client.get(f"/conversations/{primera['conversation_id']}", headers=ana["headers"]).json()
    assert abierta["turns"][0]["template_id"] == plantilla and abierta["turns"][0]["template_name"] == "Informe"
    assert abierta["turns"][0]["answer"]
    with Pipeline() as pipeline:
        nueva = preguntar_con_sesion(client, mundo, ana, PREGUNTA, conversacion=primera["conversation_id"], modo="plantilla", template_id=plantilla)
    assert nueva.status_code == 404 and nueva.json()["detail"] == "La plantilla ya no está disponible."
    pipeline.llm.answer.assert_not_called()
    assert len(_vueltas(db)) == 1


def test_con_memoria_el_seguimiento_envia_el_historial_y_el_modelo_recibe_la_plantilla(client, db, mundo):
    ana = iniciar_sesion(db)
    plantilla = plantilla_del_artefacto(db, mundo.id)
    with Pipeline("# Resumen\nLas lecciones de analítica empiezan el 5 de octubre."):
        primera = preguntar_con_sesion(client, mundo, ana, "¿Cuándo empiezan las lecciones de analítica?", modo="plantilla", template_id=plantilla).json()

    with Pipeline() as pipeline:
        preguntar_con_sesion(client, mundo, ana, "¿y los costos de analítica?", conversacion=primera["conversation_id"], modo="plantilla", template_id=plantilla)

    historial = pipeline.historial_al_modelo
    assert [t.mode for t in historial] == ["plantilla"] and "5 de octubre" in historial[0].answer
    assert CONTENIDO in pipeline.llm.answer.call_args.args[0]


def test_una_plantilla_personal_solo_para_un_artefacto_responde_404_desde_otro(client, db, mundo, make_artifact):
    otro = make_artifact("Otro", all_domains=True, modes="literal,razonamiento,plantilla")
    ana = iniciar_sesion(db)
    solo_aqui = plantilla_personal(db, ana["uid"], "Solo aquí", artifact_id=mundo.id)

    with Pipeline():
        desde_otro = preguntar_con_sesion(client, otro, ana, PREGUNTA, modo="plantilla", template_id=solo_aqui)
        desde_aqui = preguntar_con_sesion(client, mundo, ana, PREGUNTA, modo="plantilla", template_id=solo_aqui)

    assert desde_otro.status_code == 404 and desde_aqui.status_code == 200


def test_eliminar_al_usuario_elimina_sus_conversaciones_y_con_ellas_los_id_guardados(client, db, mundo):
    from sqlalchemy import text

    from mia.storage.models import ConsultaUser

    ana = iniciar_sesion(db)
    plantilla = plantilla_del_artefacto(db, mundo.id)
    with Pipeline():
        preguntar_con_sesion(client, mundo, ana, PREGUNTA, modo="plantilla", template_id=plantilla)
    assert len(_vueltas(db)) == 1

    with db() as session:
        session.execute(text("PRAGMA foreign_keys=ON"))
        session.delete(session.get(ConsultaUser, ana["uid"]))
        session.commit()

    assert _vueltas(db) == []
