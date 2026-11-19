"""POST /query en modo plantilla (feature 020, US1): la respuesta sigue la plantilla elegida con el mismo modelo del
razonamiento; el contenido de la plantilla va solo al modelo y nunca al registro de Uso."""

import pytest

from mia.config import settings
from mia.rag.llm import NO_INFO_MARKER, TEMPLATE_CLOSE, TEMPLATE_OPEN, TEMPLATE_SYSTEM_PROMPT
from mia.storage.models import QueryLog
from tests.unit.historial_de_prueba import NO_INFO_TEXTO, Pipeline, crear_mundo, preguntar, vuelta
from tests.unit.plantillas_de_prueba import (
    CONTENIDO,
    plantilla_del_artefacto,
    plantilla_personal,
    preguntar_con_plantilla,
)

PREGUNTA = "Prepárame el informe de la Maestría en Analítica"


@pytest.fixture
def mundo(db, modes_config, make_artifact, monkeypatch):
    monkeypatch.setattr(settings, "history_reformulation", "rules")
    return crear_mundo(db, make_artifact, monkeypatch, context_turns=3, modes="literal,razonamiento,plantilla")


def _registros(db):
    with db() as session:
        return session.query(QueryLog).order_by(QueryLog.created_at).all()


def test_responde_con_la_plantilla_en_el_mensaje_y_la_instruccion_propia(client, db, mundo):
    plantilla = plantilla_del_artefacto(db, mundo.id)
    with Pipeline("# Resumen\nTexto") as pipeline:
        respuesta = preguntar_con_plantilla(client, mundo, PREGUNTA, plantilla)

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["mode"] == "plantilla" and cuerpo["answer"] == "# Resumen\nTexto"
    assert cuerpo["sources"] and cuerpo["no_info"] is False
    llamada = pipeline.llm.answer.call_args
    mensaje = llamada.args[0]
    assert mensaje.startswith(PREGUNTA) and TEMPLATE_OPEN in mensaje and TEMPLATE_CLOSE in mensaje and CONTENIDO in mensaje
    assert llamada.kwargs["instructions"].startswith(TEMPLATE_SYSTEM_PROMPT)
    assert CONTENIDO not in llamada.kwargs["instructions"]


def test_la_busqueda_usa_solo_la_pregunta_y_el_registro_no_guarda_la_plantilla(client, db, mundo):
    plantilla = plantilla_del_artefacto(db, mundo.id, contenido="# Resumen\nciberseguridad secreta")
    with Pipeline() as pipeline:
        respuesta = preguntar_con_plantilla(client, mundo, PREGUNTA, plantilla)

    assert respuesta.status_code == 200
    # El embedding se calculó solo con la pregunta: el tema de la plantilla ("ciberseguridad") no cambió la búsqueda.
    assert pipeline.textos == [PREGUNTA]
    (registro,) = _registros(db)
    assert registro.mode == "plantilla" and registro.outcome == "answered"
    assert registro.question == PREGUNTA
    columnas = {c.name: getattr(registro, c.name) for c in QueryLog.__table__.columns}
    assert not any("ciberseguridad secreta" in str(valor) for valor in columnas.values())
    assert not any("plantilla" in nombre and nombre != "mode" for nombre in columnas)


def test_sin_plantilla_no_se_envia_y_con_otro_modo_se_ignora(client, db, mundo):
    plantilla = plantilla_del_artefacto(db, mundo.id)
    with Pipeline() as pipeline:
        sin = preguntar_con_plantilla(client, mundo, PREGUNTA, None)
        otro_modo = preguntar_con_plantilla(client, mundo, PREGUNTA, plantilla, modo="razonamiento")

    assert sin.status_code == 422 and sin.json()["detail"] == "Elige una plantilla."
    assert otro_modo.status_code == 200 and otro_modo.json()["mode"] == "razonamiento"
    assert pipeline.llm.answer.call_count == 1  # solo la de razonamiento llamó al modelo
    assert TEMPLATE_OPEN not in pipeline.llm.answer.call_args.args[0]
    assert [r.outcome for r in _registros(db)] == ["rejected_permission", "answered"]


def test_una_plantilla_ajena_inexistente_o_de_otro_artefacto_responde_el_mismo_404(client, db, mundo, make_artifact):
    otro = make_artifact("Otro", modes="literal,razonamiento,plantilla")
    de_otro_artefacto = plantilla_del_artefacto(db, otro.id)
    from tests.unit.chat_de_prueba import crear_usuario

    ajena = plantilla_personal(db, crear_usuario(db, "beto"))
    with Pipeline() as pipeline:
        respuestas = [
            preguntar_con_plantilla(client, mundo, PREGUNTA, identificador)
            for identificador in (de_otro_artefacto, ajena, "no-existe")
        ]

    for respuesta in respuestas:
        assert respuesta.status_code == 404 and respuesta.json()["detail"] == "La plantilla ya no está disponible."
    pipeline.llm.answer.assert_not_called()


def test_si_el_modelo_responde_sin_informacion_no_hay_fuentes(client, db, mundo):
    plantilla = plantilla_del_artefacto(db, mundo.id)
    with Pipeline(NO_INFO_MARKER) as pipeline:
        respuesta = preguntar_con_plantilla(client, mundo, PREGUNTA, plantilla)

    cuerpo = respuesta.json()
    assert respuesta.status_code == 200 and cuerpo["no_info"] is True and cuerpo["sources"] == []
    assert NO_INFO_TEXTO in cuerpo["answer"]
    pipeline.llm.answer.assert_called_once()


def test_sin_resultados_de_busqueda_responde_sin_informacion_sin_consultar_al_modelo(client, db, mundo):
    plantilla = plantilla_del_artefacto(db, mundo.id)
    with Pipeline() as pipeline:
        respuesta = preguntar_con_plantilla(client, mundo, "¿Cuánto cuesta la luna?", plantilla)

    assert respuesta.json()["no_info"] is True
    pipeline.llm.answer.assert_not_called()


def test_un_artefacto_sin_el_modo_permitido_rechaza_con_403(client, db, make_artifact, modes_config, monkeypatch):
    sin = crear_mundo(db, make_artifact, monkeypatch, modes="literal,razonamiento")
    plantilla = plantilla_del_artefacto(db, sin.id)
    with Pipeline() as pipeline:
        respuesta = preguntar_con_plantilla(client, sin, PREGUNTA, plantilla)

    assert respuesta.status_code == 403
    pipeline.llm.answer.assert_not_called()
    assert _registros(db)[0].outcome == "rejected_permission"


def test_usa_el_proveedor_el_modelo_el_esfuerzo_y_los_resultados_del_razonamiento(client, db, mundo):
    plantilla = plantilla_del_artefacto(db, mundo.id)
    with Pipeline() as pipeline:
        preguntar(client, mundo, PREGUNTA, modo="razonamiento")
        preguntar_con_plantilla(client, mundo, PREGUNTA, plantilla)

    razonamiento, con_plantilla = pipeline.get_llm.call_args_list
    assert razonamiento == con_plantilla  # (proveedor, modelo, esfuerzo)
    limites = [llamada.kwargs["limit"] for llamada in pipeline.store.search.call_args_list]
    assert limites[0] == limites[1] == settings.query_search_limit_razonamiento


def test_el_costo_suma_al_tope_diario_del_artefacto(client, db, mundo):
    plantilla = plantilla_del_artefacto(db, mundo.id)
    with Pipeline(costo=0.20):
        preguntar_con_plantilla(client, mundo, PREGUNTA, plantilla)
    (registro,) = _registros(db)

    assert float(registro.cost_usd) == pytest.approx(0.20)
    assert registro.cost_usd > 0
    from mia.access.caps import spent_today

    with db() as session:
        assert float(spent_today(session, artifact_id=mundo.id, mode="plantilla")) == pytest.approx(0.20)


def test_con_memoria_el_historial_se_usa_como_en_el_razonamiento(client, db, mundo):
    plantilla = plantilla_del_artefacto(db, mundo.id)
    anterior = vuelta("¿Cuándo empiezan las lecciones de analítica?", "Inician el 5 de octubre.", "plantilla")
    with Pipeline() as pipeline:
        respuesta = preguntar_con_plantilla(client, mundo, "¿y de analítica los costos?", plantilla, historial=[anterior])

    assert respuesta.status_code == 200
    assert [t.mode for t in pipeline.historial_al_modelo] == ["plantilla"]
    assert TEMPLATE_OPEN in pipeline.llm.answer.call_args.args[0]
