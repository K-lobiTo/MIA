"""POST /query con historial: el costo y los topes (feature 014, US7). El costo del historial va dentro de lo que informa el
proveedor; el de la reescritura (estrategia `model`) se suma; los topes diarios siguen valiendo."""

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from mia.config import settings
from mia.rag import followup
from mia.rag.llm import LLMAnswer
from mia.storage.models import QueryLog
from tests.unit.historial_de_prueba import Pipeline, crear_mundo, preguntar, vuelta

HISTORIAL = [
    vuelta(
        "¿Cuándo empiezan las lecciones de la maestría en analítica de negocio?",
        "Inician el 5 de octubre.",
    )
]


@pytest.fixture
def mundo(db, modes_config, make_artifact, monkeypatch):
    monkeypatch.setattr(settings, "history_reformulation", "rules")
    return crear_mundo(db, make_artifact, monkeypatch, context_turns=3)


def _reescritor(
    costo=0.00005, tokens=(300, 20), texto="¿Cuánto cuesta la maestría en analítica de negocio?"
):
    proveedor = MagicMock()
    proveedor.rewrite.return_value = LLMAnswer(
        text=texto, model="m", prompt_tokens=tokens[0], completion_tokens=tokens[1], cost_usd=costo
    )
    return proveedor


def _registro(db) -> QueryLog:
    with db() as session:
        return session.query(QueryLog).order_by(QueryLog.created_at.desc()).first()


def test_con_historial_el_registro_guarda_el_costo_y_los_tokens_que_informa_el_proveedor(
    client, mundo, db
):
    with Pipeline(costo=0.0009, tokens=(5200, 80)):
        preguntar(client, mundo, "¿y cuánto cuesta?", historial=HISTORIAL)

    registro = _registro(db)
    assert registro.cost_usd == Decimal("0.000900")
    assert (registro.prompt_tokens, registro.completion_tokens) == (5200, 80)


def test_con_el_modelo_se_suma_el_costo_de_la_reescritura(client, mundo, db, monkeypatch):
    monkeypatch.setattr(settings, "history_reformulation", "model")
    reescritor = _reescritor()
    with (
        Pipeline(costo=0.0004, tokens=(1000, 50)),
        patch.object(followup, "get_llm_provider", return_value=reescritor),
    ):
        preguntar(client, mundo, "¿y cuánto cuesta?", historial=HISTORIAL)

    reescritor.rewrite.assert_called_once()
    registro = _registro(db)
    assert registro.cost_usd == Decimal("0.000450")
    assert (registro.prompt_tokens, registro.completion_tokens) == (1300, 70)


def test_el_costo_de_la_reescritura_cuenta_tambien_si_la_respuesta_es_sin_informacion(
    client, mundo, db, monkeypatch
):
    monkeypatch.setattr(settings, "history_reformulation", "model")
    # La pregunta reescrita no nombra ningún tema con documentos: la búsqueda no encuentra nada.
    reescritor = _reescritor(texto="¿Cuánto cuesta la luna en los documentos?")
    with (
        Pipeline() as pipeline,
        patch.object(followup, "get_llm_provider", return_value=reescritor),
    ):
        cuerpo = preguntar(client, mundo, "¿y cuánto cuesta?", historial=HISTORIAL).json()

    assert cuerpo["no_info"] is True
    pipeline.llm.answer.assert_not_called()
    registro = _registro(db)
    assert registro.outcome == "no_info" and registro.cost_usd == Decimal("0.000050")


def test_con_las_reglas_la_reformulacion_no_cuesta_nada_extra(client, mundo, db):
    with Pipeline(costo=0.0004):
        preguntar(client, mundo, "¿y cuánto cuesta?", historial=HISTORIAL)

    assert _registro(db).cost_usd == Decimal("0.000400")


def _gastar(db, artifact_id, modo, monto):
    with db() as session:
        session.add(
            QueryLog(
                id=f"gasto-{modo}",
                artifact_id=artifact_id,
                question="q",
                domain_ids="[]",
                mode=modo,
                outcome="answered",
                cost_usd=Decimal(str(monto)),
            )
        )
        session.commit()


@pytest.mark.parametrize("modo", ["literal", "razonamiento"])
def test_con_el_tope_alcanzado_responde_429_sin_reescribir_ni_llamar_al_modelo(
    db, modes_config, make_artifact, monkeypatch, client, modo
):
    monkeypatch.setattr(settings, "history_reformulation", "model")
    artefacto = crear_mundo(
        db, make_artifact, monkeypatch, context_turns=3, cap=0.01, reasoning_cap=0.01
    )
    _gastar(db, artefacto.id, modo, 0.5)
    reescritor = _reescritor()

    with (
        Pipeline() as pipeline,
        patch.object(followup, "get_llm_provider", return_value=reescritor),
    ):
        respuesta = preguntar(
            client, artefacto, "¿y cuánto cuesta?", modo=modo, historial=HISTORIAL
        )

    assert respuesta.status_code == 429
    reescritor.rewrite.assert_not_called()
    pipeline.llm.answer.assert_not_called()
    assert pipeline.textos == []


def test_el_reintento_por_respuesta_cortada_sigue_respetando_el_tope(
    db, modes_config, make_artifact, monkeypatch, client
):
    monkeypatch.setattr(settings, "query_retry_cut_answers", "on")
    artefacto = crear_mundo(db, make_artifact, monkeypatch, context_turns=3, cap=0.01)
    with Pipeline() as pipeline:
        pipeline.llm.answer.return_value = LLMAnswer(
            text="Inician el 5 de",
            model="m",
            prompt_tokens=1000,
            completion_tokens=50,
            cost_usd=0.5,
            finish_reason="length",
        )
        respuesta = preguntar(client, artefacto, "¿y cuánto cuesta?", historial=HISTORIAL)

    assert respuesta.status_code == 200
    # El primer intento ya pasó el tope del día: no se reintenta y la respuesta lleva el aviso de posible corte.
    assert pipeline.llm.answer.call_count == 1
