"""POST /query con historial y cambio de modo (feature 014, US3): el historial de cualquier modo ayuda a entender la
pregunta y nunca es fuente de datos; cada modo conserva su estilo y las reglas de modos permitidos se cumplen."""

import pytest

from mia.config import settings
from mia.rag.history import REASONING_WARNING, format_history
from mia.rag.llm import (
    HISTORY_INSTRUCTIONS,
    NO_INFO_MARKER,
    RAG_SYSTEM_PROMPT,
    REASONING_SYSTEM_PROMPT,
)
from mia.storage.models import QueryLog
from tests.unit.historial_de_prueba import (
    NO_INFO_TEXTO,
    Pipeline,
    crear_mundo,
    preguntar,
    vuelta,
)

PREGUNTA_ANA = "¿Cuántos créditos suman los bloques de analítica de negocio?"
CALCULADA = vuelta(
    PREGUNTA_ANA, "Suman 54 créditos (calculado sumando los bloques).", "razonamiento"
)
LITERAL = vuelta(
    "¿Cuándo empiezan las lecciones de analítica?", "Inician el 5 de octubre.", "literal"
)


@pytest.fixture
def mundo(db, modes_config, make_artifact, monkeypatch):
    monkeypatch.setattr(settings, "history_reformulation", "rules")
    return crear_mundo(db, make_artifact, monkeypatch, context_turns=3)


def test_una_vuelta_de_razonamiento_con_pregunta_literal_lleva_la_advertencia_solo_en_esa_vuelta(
    client, mundo
):
    with Pipeline() as pipeline:
        respuesta = preguntar(client, mundo, "¿y cuánto cuesta?", historial=[LITERAL, CALCULADA])

    assert respuesta.status_code == 200
    historial = pipeline.historial_al_modelo
    assert [turno.mode for turno in historial] == ["literal", "razonamiento"]
    bloque = format_history(historial)
    assert bloque.count(REASONING_WARNING) == 1
    assert bloque.index(REASONING_WARNING) > bloque.index(CALCULADA["answer"])
    # El modelo literal conserva su instrucción de sistema (el bloque de historial se agrega dentro del proveedor).
    kwargs = pipeline.llm.answer.call_args.kwargs
    assert kwargs["instructions"].startswith(RAG_SYSTEM_PROMPT[:40])
    assert kwargs["instructions"] != REASONING_SYSTEM_PROMPT
    assert NO_INFO_MARKER in kwargs["instructions"]  # el marcador de sin información de siempre
    assert (
        HISTORY_INSTRUCTIONS
    )  # la regla "no es fuente de datos" existe y los proveedores la agregan con historial


def test_el_caso_inverso_usa_la_instruccion_de_razonamiento(client, mundo):
    with Pipeline() as pipeline:
        preguntar(client, mundo, "¿y cuánto cuesta?", modo="razonamiento", historial=[LITERAL])

    assert pipeline.llm.answer.call_args.kwargs["instructions"] == REASONING_SYSTEM_PROMPT
    assert REASONING_WARNING not in format_history(pipeline.historial_al_modelo)


def test_el_historial_no_cambia_las_fuentes_ni_las_imagenes_de_la_respuesta(client, mundo):
    with Pipeline() as pipeline:
        con = preguntar(client, mundo, "¿y cuánto cuesta?", historial=[LITERAL, CALCULADA]).json()
    with Pipeline():
        sin = preguntar(client, mundo, "¿Cuándo empiezan las lecciones de analítica?").json()

    assert pipeline.historial_al_modelo is not None
    textos = " ".join(s["excerpt"] + s["document"] for s in con["sources"])
    assert CALCULADA["answer"] not in textos and "54 créditos" not in textos
    assert {s["document"] for s in con["sources"]} == {s["document"] for s in sin["sources"]}
    assert con["images"] == []


def test_el_historial_no_abre_un_modo_no_permitido(
    db, modes_config, make_artifact, monkeypatch, client
):
    solo_literal = crear_mundo(db, make_artifact, monkeypatch, context_turns=3, modes="literal")
    with Pipeline() as pipeline:
        respuesta = preguntar(
            client, solo_literal, "¿y cuánto cuesta?", modo="razonamiento", historial=[CALCULADA]
        )

    assert respuesta.status_code == 403
    pipeline.llm.answer.assert_not_called()


def test_las_vueltas_sin_informacion_o_sin_respuesta_no_llegan_al_modelo(client, mundo):
    historial = [
        LITERAL,
        vuelta("¿Cuánto cuesta la luna?", NO_INFO_TEXTO + " en los documentos disponibles."),
        vuelta("¿Y la otra?", "   "),
    ]
    with Pipeline() as pipeline:
        preguntar(client, mundo, "¿y cuánto cuesta?", historial=historial)

    assert [t.question for t in pipeline.historial_al_modelo] == [LITERAL["question"]]


def test_con_el_modo_razonamiento_agotado_la_consulta_literal_funciona_con_su_historial(
    db, modes_config, make_artifact, monkeypatch, client
):
    from decimal import Decimal

    artefacto = crear_mundo(db, make_artifact, monkeypatch, context_turns=3, reasoning_cap=0.01)
    with db() as session:
        session.add(
            QueryLog(
                id="gasto",
                artifact_id=artefacto.id,
                question="q",
                domain_ids="[]",
                mode="razonamiento",
                outcome="answered",
                cost_usd=Decimal("0.5"),
            )
        )
        session.commit()
    with Pipeline() as pipeline:
        rechazada = preguntar(
            client, artefacto, "¿y cuánto cuesta?", modo="razonamiento", historial=[CALCULADA]
        )
        aceptada = preguntar(client, artefacto, "¿y cuánto cuesta?", historial=[LITERAL, CALCULADA])

    assert rechazada.status_code == 429
    assert aceptada.status_code == 200
    assert [t.mode for t in pipeline.historial_al_modelo] == ["literal", "razonamiento"]


def test_la_pregunta_guardada_en_uso_es_solo_la_original(client, mundo, db):
    with Pipeline():
        preguntar(client, mundo, "¿y cuánto cuesta?", historial=[LITERAL, CALCULADA])

    with db() as session:
        registros = session.query(QueryLog).all()
    assert [r.question for r in registros] == ["¿y cuánto cuesta?"]
