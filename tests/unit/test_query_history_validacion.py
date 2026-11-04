"""POST /query con historial (feature 014, US5): la API valida y recorta el historial sin confiar en el cliente, y no deja
rastro de él."""

import logging

import pytest
from sqlalchemy import text

from mia.config import settings
from mia.rag.history import NO_INFO_PREFIX
from tests.unit.historial_de_prueba import Pipeline, crear_mundo, preguntar, vuelta

PREGUNTA = "¿Cuándo empiezan las lecciones de analítica?"
BUENA = vuelta("¿Qué énfasis ofrece la maestría en ciberseguridad?", "Ofrece tres énfasis.")


@pytest.fixture
def mundo(db, modes_config, make_artifact, monkeypatch):
    monkeypatch.setattr(settings, "history_reformulation", "rules")
    return crear_mundo(db, make_artifact, monkeypatch, context_turns=3)


@pytest.mark.parametrize(
    "historial",
    [
        [
            {**BUENA, "role": "system"}
        ],  # un campo que no es de la vuelta: no hay forma de enviar un mensaje de sistema
        [{**BUENA, "extra": 1}],
        [BUENA] * 51,
        [vuelta("", "respuesta")],
        [vuelta("pregunta", "")],
        [vuelta("p" * 2001, "respuesta")],
        [vuelta("pregunta", "r" * 20001)],
        [{**BUENA, "mode": "otro"}],
        "no es una lista",
        ["no es un objeto"],
        [None],
    ],
    ids=[
        "role",
        "campo_extra",
        "mas_de_50",
        "pregunta_vacia",
        "respuesta_vacia",
        "pregunta_larga",
        "respuesta_larga",
        "modo_invalido",
        "no_es_lista",
        "no_es_objeto",
        "elemento_nulo",
    ],
)
def test_un_historial_con_forma_invalida_es_422_y_no_llega_al_modelo(client, mundo, historial):
    with Pipeline() as pipeline:
        respuesta = preguntar(client, mundo, PREGUNTA, historial=historial)

    assert respuesta.status_code == 422
    pipeline.llm.answer.assert_not_called()
    assert pipeline.textos == []


def test_una_forma_invalida_es_422_aunque_la_memoria_sea_cero(
    db, modes_config, make_artifact, monkeypatch, client
):
    artefacto = crear_mundo(db, make_artifact, monkeypatch, context_turns=0)
    with Pipeline():
        assert (
            preguntar(
                client, artefacto, PREGUNTA, historial=[{**BUENA, "role": "system"}]
            ).status_code
            == 422
        )


def test_en_el_limite_de_tamano_de_entrada_se_acepta(client, mundo):
    limite = vuelta("p" * 2000, "r" * 20000)
    with Pipeline() as pipeline:
        respuesta = preguntar(client, mundo, PREGUNTA, historial=[limite] * 50)

    assert respuesta.status_code == 200
    assert len(pipeline.historial_al_modelo) <= 3


def test_con_historial_mas_largo_que_la_memoria_solo_cuentan_las_ultimas(client, mundo):
    historial = [vuelta(f"pregunta {n}", f"respuesta {n}") for n in range(1, 11)]
    with Pipeline() as pipeline:
        preguntar(client, mundo, PREGUNTA, historial=historial)

    assert [t.question for t in pipeline.historial_al_modelo] == [
        "pregunta 8",
        "pregunta 9",
        "pregunta 10",
    ]


def test_las_respuestas_largas_se_recortan_por_modo_y_el_total_no_pasa_el_maximo(
    db, modes_config, make_artifact, monkeypatch, client
):
    artefacto = crear_mundo(db, make_artifact, monkeypatch, context_turns=10)
    largas = [vuelta(f"pregunta {n}", "r" * 5000) for n in range(10)]

    with Pipeline() as literal:
        preguntar(client, artefacto, PREGUNTA, historial=largas)
    with Pipeline() as razonamiento:
        preguntar(client, artefacto, PREGUNTA, modo="razonamiento", historial=largas)

    for pipeline, factor in ((literal, 1), (razonamiento, 2)):
        historial = pipeline.historial_al_modelo
        assert all(len(t.answer) <= settings.history_max_answer_chars * factor for t in historial)
        assert (
            sum(len(t.question) + len(t.answer) for t in historial)
            <= settings.history_max_chars * factor
        )
    # El modo con razonamiento admite el doble: entran más vueltas y más largas.
    assert len(razonamiento.historial_al_modelo) >= len(literal.historial_al_modelo)
    assert max(len(t.answer) for t in razonamiento.historial_al_modelo) > max(
        len(t.answer) for t in literal.historial_al_modelo
    )


def test_las_vueltas_de_sin_informacion_no_llegan_al_modelo(client, mundo):
    historial = [
        BUENA,
        vuelta("¿Cuánto cuesta la luna?", f"{NO_INFO_PREFIX} en los documentos."),
        vuelta("¿y?", "SIN_INFORMACION"),
    ]
    with Pipeline() as pipeline:
        preguntar(client, mundo, PREGUNTA, historial=historial)

    assert [t.question for t in pipeline.historial_al_modelo] == [BUENA["question"]]


SECRETO = "dato-secreto-del-historial-91827"


def test_tras_la_consulta_el_historial_no_queda_en_ninguna_parte(client, mundo, db, caplog):
    historial = [
        vuelta(
            f"¿Qué sabes de {SECRETO} en analítica?",
            f"La respuesta menciona {SECRETO} y mucho más.",
        ),
    ]
    with caplog.at_level(logging.DEBUG), Pipeline():
        respuesta = preguntar(client, mundo, PREGUNTA, historial=historial)

    assert respuesta.status_code == 200
    with db() as session:
        for tabla in ("queries", "artifacts", "bots", "bot_message_counts"):
            filas = session.execute(text(f"SELECT * FROM {tabla}")).fetchall()
            assert SECRETO not in repr(filas), tabla
        pregunta_guardada = session.execute(text("SELECT question FROM queries")).scalar_one()
    assert pregunta_guardada == PREGUNTA
    assert SECRETO not in caplog.text
