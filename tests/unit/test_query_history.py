"""POST /query con historial (feature 014): memoria del artefacto, reformulación de la búsqueda y mensaje al modelo."""

import pytest

from mia.config import settings
from mia.rag.history import HistoryTurn
from mia.storage.models import QueryLog
from tests.unit.historial_de_prueba import (
    ANALITICA,
    Pipeline,
    crear_mundo,
    preguntar,
    vuelta,
)

PREGUNTA_ANA = "¿Cuándo empiezan las lecciones de la maestría en analítica de negocio?"
HISTORIAL = [
    vuelta(
        "¿Qué énfasis ofrece la maestría en ciberseguridad?",
        "Ofrece tres énfasis: seguridad del software, defensa y ataque, y gestión.",
    ),
    vuelta(PREGUNTA_ANA, "Inician el 5 de octubre de 2026."),
]


@pytest.fixture
def mundo(db, modes_config, make_artifact, monkeypatch):
    monkeypatch.setattr(settings, "history_reformulation", "rules")
    return crear_mundo(db, make_artifact, monkeypatch, context_turns=3)


def test_un_seguimiento_corto_busca_con_las_preguntas_anteriores_y_encuentra_el_documento(
    client, mundo
):
    with Pipeline() as pipeline:
        respuesta = preguntar(client, mundo, "¿y cuánto cuesta?", historial=HISTORIAL)

    cuerpo = respuesta.json()
    assert respuesta.status_code == 200 and cuerpo["no_info"] is False
    assert {s["document"] for s in cuerpo["sources"]} == {
        "ana-admision.txt",
        "ana-presentacion.txt",
    }
    # El embedding se calculó con las dos preguntas anteriores y la actual (research R4, estrategia rules).
    assert pipeline.textos == [f"{HISTORIAL[0]['question']} {PREGUNTA_ANA} ¿y cuánto cuesta?"]
    assert ANALITICA in pipeline.textos[0].lower()


def test_sin_historial_el_mismo_seguimiento_se_corta_en_sin_informacion(client, mundo):
    with Pipeline() as pipeline:
        cuerpo = preguntar(client, mundo, "¿y cuánto cuesta?").json()

    assert cuerpo["no_info"] is True
    pipeline.llm.answer.assert_not_called()
    assert pipeline.textos == ["¿y cuánto cuesta?"]


def test_el_modelo_recibe_la_pregunta_original_y_el_historial_vigente(client, mundo):
    with Pipeline() as pipeline:
        preguntar(client, mundo, "¿y cuánto cuesta?", historial=HISTORIAL)

    llamada = pipeline.llm.answer.call_args
    assert llamada.args[0] == "¿y cuánto cuesta?"  # la original, no la combinada
    assert pipeline.historial_al_modelo == [
        HistoryTurn(question=h["question"], answer=h["answer"], mode=h.get("mode", "literal"))
        for h in HISTORIAL
    ]


def test_una_pregunta_que_se_entiende_sola_no_se_reformula_aunque_haya_historial(client, mundo):
    pregunta = "¿Cuántos estudiantes se aceptan en la maestría en ciberseguridad?"
    with Pipeline() as pipeline:
        cuerpo = preguntar(client, mundo, pregunta, historial=HISTORIAL).json()

    assert pipeline.textos == [pregunta]  # el embedding es el de la original
    assert {s["document"] for s in cuerpo["sources"]} == {
        "ciber-admision.txt"
    }  # y el tema del historial no se mezcla
    assert (
        pipeline.historial_al_modelo is not None
    )  # el modelo igual recibe el historial para entender


def test_con_mas_vueltas_que_la_memoria_solo_ve_las_ultimas(
    client, db, modes_config, make_artifact, monkeypatch
):
    artefacto = crear_mundo(db, make_artifact, monkeypatch, context_turns=2)
    historial = [vuelta(f"pregunta {n}", f"respuesta {n}") for n in range(1, 6)]

    with Pipeline() as pipeline:
        preguntar(client, artefacto, "¿y el costo de la analítica?", historial=historial)

    assert [h.question for h in pipeline.historial_al_modelo] == ["pregunta 4", "pregunta 5"]


def test_el_registro_de_uso_guarda_la_pregunta_original_no_la_de_busqueda(client, db, mundo):
    with Pipeline():
        preguntar(client, mundo, "¿y cuánto cuesta?", historial=HISTORIAL)

    with db() as session:
        registro = session.query(QueryLog).one()
    assert registro.question == "¿y cuánto cuesta?" and registro.outcome == "answered"


def test_el_historial_pasa_por_la_busqueda_hibrida_con_la_pregunta_de_busqueda(
    client, mundo, monkeypatch
):
    from mia.api.routes import query as query_routes

    vistas = []

    class Hibrida:
        def __init__(self, store, session, question, domains, embedding):
            vistas.append(question)
            self.note, self.failed, self.merged_new = None, False, 0
            self.outcome = type(
                "O",
                (),
                {"groups": [], "elapsed_ms": 0, "wait_ms": 0, "specific": 0, "candidates": []},
            )()

        def merge(self, results, limit):
            return results

    monkeypatch.setattr(settings, "query_hybrid_search", "on")
    monkeypatch.setattr(query_routes, "_HybridRun", Hibrida)
    with Pipeline():
        preguntar(client, mundo, "¿y cuánto cuesta?", historial=HISTORIAL)

    assert len(vistas) == 1 and ANALITICA in vistas[0].lower() and "¿y cuánto cuesta?" in vistas[0]


def test_una_respuesta_con_historial_tiene_las_fuentes_y_el_formato_de_siempre(client, mundo):
    with Pipeline("El costo es ₡61 000 por crédito.") as pipeline:
        cuerpo = preguntar(client, mundo, "¿y cuánto cuesta?", historial=HISTORIAL).json()

    assert set(cuerpo) == {"id", "answer", "sources", "mode", "latency_ms", "no_info", "images"}
    assert cuerpo["answer"] == "El costo es ₡61 000 por crédito." and cuerpo["mode"] == "literal"
    assert all(set(s) == {"domain", "document", "excerpt"} for s in cuerpo["sources"])
    assert pipeline.llm.answer.call_count == 1
