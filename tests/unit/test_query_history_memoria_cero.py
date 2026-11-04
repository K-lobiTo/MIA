"""POST /query con memoria 0 (feature 014, US4): el valor por defecto deja todo exactamente como antes, aunque el cliente
envíe historial."""

import pytest

from mia.config import settings
from mia.storage.models import Artifact, QueryLog
from tests.unit.historial_de_prueba import Pipeline, crear_mundo, preguntar, vuelta

PREGUNTA = "¿Cuándo empiezan las lecciones de analítica?"
HISTORIAL = [
    vuelta(
        "¿Cuándo empiezan las lecciones de la maestría en analítica de negocio?",
        "Inician el 5 de octubre.",
    ),
    vuelta(
        "¿Qué énfasis ofrece la maestría en ciberseguridad?", "Ofrece tres énfasis.", "razonamiento"
    ),
]


@pytest.fixture
def mundo(db, modes_config, make_artifact, monkeypatch):
    monkeypatch.setattr(settings, "history_reformulation", "rules")
    return crear_mundo(db, make_artifact, monkeypatch, context_turns=0)


def _sin_ids(cuerpo):
    return {k: v for k, v in cuerpo.items() if k not in {"id", "latency_ms"}}


def test_con_memoria_cero_el_historial_enviado_no_cambia_nada(client, mundo, db):
    with Pipeline() as sin:
        base = preguntar(client, mundo, PREGUNTA)
    with Pipeline() as con:
        otra = preguntar(client, mundo, PREGUNTA, historial=HISTORIAL)

    assert base.status_code == otra.status_code == 200
    assert _sin_ids(base.json()) == _sin_ids(otra.json())
    # La búsqueda es la de la pregunta original, sin reformular.
    assert con.textos == sin.textos == [PREGUNTA]
    assert con.store.search.call_count == sin.store.search.call_count
    # El modelo recibe exactamente la misma llamada: sin el parámetro del historial y con la misma instrucción.
    assert con.historial_al_modelo is None and sin.historial_al_modelo is None
    assert con.llm.answer.call_args.args == sin.llm.answer.call_args.args
    assert con.llm.answer.call_args.kwargs == sin.llm.answer.call_args.kwargs
    # El registro de Uso (costo, tokens, resultado) es el mismo.
    with db() as session:
        registros = session.query(QueryLog).order_by(QueryLog.created_at).all()
    assert len(registros) == 2
    uno, dos = registros
    assert (uno.outcome, uno.cost_usd, uno.prompt_tokens, uno.completion_tokens, uno.question) == (
        dos.outcome,
        dos.cost_usd,
        dos.prompt_tokens,
        dos.completion_tokens,
        dos.question,
    )


def test_con_memoria_cero_un_seguimiento_se_corta_en_sin_informacion_como_hoy(client, mundo):
    with Pipeline() as pipeline:
        cuerpo = preguntar(client, mundo, "¿y cuánto cuesta?", historial=HISTORIAL).json()

    assert cuerpo["no_info"] is True
    pipeline.llm.answer.assert_not_called()


def test_los_artefactos_nuevos_nacen_con_memoria_cero(db, make_artifact):
    artefacto = make_artifact("Nuevo")
    with db() as session:
        assert session.get(Artifact, artefacto.id).context_turns == 0


def test_un_cliente_sin_history_funciona_sin_cambios(client, mundo):
    with Pipeline() as pipeline:
        respuesta = preguntar(client, mundo, "¿Cuándo empiezan las lecciones de analítica?")

    assert respuesta.status_code == 200 and respuesta.json()["no_info"] is False
    assert pipeline.historial_al_modelo is None
