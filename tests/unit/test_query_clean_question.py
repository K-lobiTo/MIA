"""La ruta POST /query con la pregunta limpia (feature 008): segundo intento, guardas, apagado y nota de Uso."""

import logging
from unittest.mock import MagicMock, patch

import pytest

from mia.api.routes import query as query_routes
from mia.config import settings
from mia.rag import completeness
from mia.rag.llm import LLMAnswer
from mia.storage.models import Document, Domain, QueryLog, Unit
from mia.storage.vector_store import SearchResult

UMBRAL = 0.82
PREGUNTA = "¿Quién es Natalia Soto Solís?"


@pytest.fixture
def base(db, modes_config):
    with db() as session:
        session.add(Unit(id="u1", name="Computación"))
        session.flush()
        session.add(Domain(id="dom-1", unit_id="u1", name="Tesis", description=""))
        session.flush()
        session.add(
            Document(
                id="doc-1", domain_id="dom-1", filename="NataliaSoto.pdf", source_type="pdf", file_hash="h1",
                status="done",
            )
        )
        session.commit()


class _Almacen:
    """Almacén simulado: devuelve una lista distinta en cada búsqueda y recuerda cómo se le llamó."""

    def __init__(self, busquedas, tamano=3):
        self.busquedas = list(busquedas)
        self.tamano = tamano
        self.llamadas = []

    def search(self, vector, domains, limit):
        self.llamadas.append({"vector": vector, "domains": domains, "limit": limit})
        return self.busquedas[len(self.llamadas) - 1] if len(self.llamadas) <= len(self.busquedas) else []

    def count_chunks(self, document_id):
        return self.tamano

    def get_chunks(self, document_id, indexes):
        return [
            SearchResult(
                chunk_id=f"{document_id}-{i}", document_id=document_id, domain="dom-1",
                text=f"{document_id}:{i}".ljust(100, "."), score=0.0, chunk_index=i,
            )
            for i in indexes
            if 0 <= i < self.tamano
        ]


def _resultado(puntaje, indice=1):
    return SearchResult(
        chunk_id=f"doc-1-{indice}", document_id="doc-1", domain="dom-1",
        text=f"doc-1:{indice}".ljust(100, "."), score=puntaje, chunk_index=indice,
    )


BAJO = [_resultado(0.78)]
ALTO = [_resultado(0.90)]


def _respuesta(texto="Es una persona.", costo=0.01, motivo="stop"):
    return LLMAnswer(text=texto, finish_reason=motivo, cost_usd=costo, prompt_tokens=100, completion_tokens=20)


def _consultar(client, artefacto, busquedas, respuestas=(), pregunta=PREGUNTA, modo="literal", **opciones):
    """Devuelve (respuesta HTTP, almacén, modelo, embeddings)."""
    almacen = _Almacen(busquedas)
    embeddings = MagicMock()
    embeddings.embed.side_effect = lambda textos, is_query=False: [[float(len(textos[0])), 0.2]]
    modelo = MagicMock()
    modelo.answer.side_effect = list(respuestas)
    valores = {"query_clean_question": "on", "query_similarity_threshold": UMBRAL, "query_complete_context": "off",
               "query_retry_cut_answers": "off", "query_cited_sources": "off"}
    valores.update(opciones)
    with (
        patch.multiple(settings, **valores),
        patch.object(query_routes, "get_vector_store", return_value=almacen),
        patch.object(query_routes, "get_embedding_provider", return_value=embeddings),
        patch.object(query_routes, "get_llm_provider", return_value=modelo),
    ):
        respuesta = client.post(
            "/query", json={"domains": ["dom-1"], "question": pregunta, "mode": modo}, headers=artefacto.headers
        )
    return respuesta, almacen, modelo, embeddings


def _registro(db, respuesta):
    with db() as session:
        return session.get(QueryLog, respuesta.json()["id"])


# --- US1: segundo intento ----------------------------------------------------------------------


@pytest.mark.parametrize(("modo", "limite"), [("literal", 8), ("razonamiento", 16)])
def test_el_segundo_intento_encuentra_y_el_modelo_responde_con_la_pregunta_original(
    client, base, make_artifact, modo, limite
):
    artefacto = make_artifact(units=["u1"], modes="literal,razonamiento")
    with patch.multiple(settings, query_search_limit=8, query_search_limit_razonamiento=16):
        respuesta, almacen, modelo, embeddings = _consultar(
            client, artefacto, [BAJO, ALTO], [_respuesta()], modo=modo
        )
    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["no_info"] is False and cuerpo["answer"] == "Es una persona."
    assert [s["document"] for s in cuerpo["sources"]] == ["NataliaSoto.pdf"]
    # Dos búsquedas con los mismos dominios y el mismo límite del modo.
    assert len(almacen.llamadas) == 2
    assert almacen.llamadas[0]["domains"] == almacen.llamadas[1]["domains"] == ["dom-1"]
    assert almacen.llamadas[0]["limit"] == almacen.llamadas[1]["limit"] == limite
    # El embedding del segundo intento es el del texto reducido y de pregunta.
    textos = [c.args[0][0] for c in embeddings.embed.call_args_list]
    assert textos == [PREGUNTA, "Natalia Soto Solís"]
    assert all(c.kwargs.get("is_query") is True for c in embeddings.embed.call_args_list)
    # Una sola llamada al modelo y con la pregunta original.
    assert modelo.answer.call_count == 1
    assert modelo.answer.call_args.args[0] == PREGUNTA
    # El contexto es el de los fragmentos del segundo intento.
    assert modelo.answer.call_args.args[1][0].document == "NataliaSoto.pdf"
    # `images` (feature 011) es un campo nuevo, siempre presente y vacío sin imágenes: el resto de la estructura no cambia.
    assert set(cuerpo) == {"id", "answer", "sources", "mode", "latency_ms", "no_info", "images"}
    assert cuerpo["images"] == []


def test_el_segundo_intento_usa_el_contexto_completo_de_la_007(client, base, make_artifact):
    artefacto = make_artifact(units=["u1"])
    _, _, modelo, _ = _consultar(client, artefacto, [BAJO, ALTO], [_respuesta()], query_complete_context="on")
    contexto = modelo.answer.call_args.args[1]
    assert contexto and all(c.document == "NataliaSoto.pdf" for c in contexto)
    assert completeness.COMPLETENESS_INSTRUCTIONS in modelo.answer.call_args.kwargs["instructions"]


def test_si_la_primera_busqueda_ya_pasa_el_umbral_no_hay_segundo_intento(client, base, make_artifact):
    artefacto = make_artifact(units=["u1"])
    respuesta, almacen, modelo, embeddings = _consultar(client, artefacto, [ALTO, ALTO], [_respuesta()])
    assert respuesta.status_code == 200
    assert len(almacen.llamadas) == 1 and embeddings.embed.call_count == 1
    assert modelo.answer.call_count == 1


def test_si_el_segundo_intento_tampoco_pasa_el_umbral_es_sin_informacion_sin_llamar_al_modelo(
    client, base, make_artifact
):
    artefacto = make_artifact(units=["u1"])
    respuesta, almacen, modelo, _ = _consultar(client, artefacto, [BAJO, BAJO, ALTO], [_respuesta()])
    assert respuesta.json()["no_info"] is True
    assert modelo.answer.call_count == 0
    assert len(almacen.llamadas) == 2  # no hay tercera búsqueda


# --- US2: lo que no se reformula ---------------------------------------------------------------


@pytest.mark.parametrize(
    "pregunta", ["¿Cuántos créditos tiene el curso de IPA en Big Data?", "¿Cuál es el costo del curso X?"]
)
def test_una_pregunta_que_no_se_reduce_no_hace_segunda_busqueda(client, base, make_artifact, pregunta):
    artefacto = make_artifact(units=["u1"])
    respuesta, almacen, modelo, embeddings = _consultar(
        client, artefacto, [BAJO, ALTO], [_respuesta()], pregunta=pregunta
    )
    assert respuesta.json()["no_info"] is True
    assert len(almacen.llamadas) == 1 and embeddings.embed.call_count == 1
    assert modelo.answer.call_count == 0


def test_identificacion_de_algo_ausente_sigue_siendo_sin_informacion(client, base, make_artifact):
    artefacto = make_artifact(units=["u1"])
    respuesta, almacen, modelo, _ = _consultar(
        client, artefacto, [BAJO, []], [_respuesta()], pregunta="¿Quién es Zacarías Fernández Pizarro?"
    )
    assert respuesta.json()["no_info"] is True
    assert modelo.answer.call_count == 0 and len(almacen.llamadas) == 2


def test_una_consulta_rechazada_por_tope_no_busca(client, db, base, make_artifact):
    artefacto = make_artifact(units=["u1"], cap=0.0001)
    _consultar(client, artefacto, [ALTO], [_respuesta(costo=0.01)])  # gasta el tope
    respuesta, almacen, modelo, embeddings = _consultar(client, artefacto, [BAJO, ALTO], [_respuesta()])
    assert respuesta.status_code == 429
    assert almacen.llamadas == [] and embeddings.embed.call_count == 0 and modelo.answer.call_count == 0


# --- US3: apagado y nota de Uso ----------------------------------------------------------------


def test_con_la_opcion_apagada_todo_es_como_antes(client, db, base, make_artifact):
    artefacto = make_artifact(units=["u1"])
    respuesta, almacen, modelo, embeddings = _consultar(
        client, artefacto, [BAJO, ALTO], [_respuesta()], query_clean_question="off"
    )
    assert respuesta.json()["no_info"] is True
    assert len(almacen.llamadas) == 1 and embeddings.embed.call_count == 1 and modelo.answer.call_count == 0
    registro = _registro(db, respuesta)
    assert registro.outcome == "no_info" and registro.reject_reason is None


def test_el_valor_por_defecto_es_apagado():
    assert type(settings)(_env_file=None).query_clean_question == "off"


def test_un_valor_invalido_se_comporta_como_apagado_y_avisa_una_sola_vez(client, base, make_artifact, caplog):
    completeness._INVALID_VALUES_WARNED.clear()
    artefacto = make_artifact(units=["u1"])
    with caplog.at_level(logging.WARNING, logger=completeness.__name__):
        for _ in range(2):
            respuesta, almacen, _, _ = _consultar(client, artefacto, [BAJO, ALTO], query_clean_question="quizás")
            assert respuesta.status_code == 200 and len(almacen.llamadas) == 1
    avisos = [r.getMessage() for r in caplog.records if "QUERY_CLEAN_QUESTION" in r.getMessage()]
    assert len(avisos) == 1
    completeness._INVALID_VALUES_WARNED.clear()


def test_la_opcion_se_lee_en_cada_consulta(client, base, make_artifact):
    artefacto = make_artifact(units=["u1"])
    _, primera, _, _ = _consultar(client, artefacto, [BAJO, ALTO], [_respuesta()], query_clean_question="on")
    _, segunda, _, _ = _consultar(client, artefacto, [BAJO, ALTO], [_respuesta()], query_clean_question="off")
    assert len(primera.llamadas) == 2 and len(segunda.llamadas) == 1


def test_la_nota_con_resultados_queda_en_uso(client, db, base, make_artifact):
    artefacto = make_artifact(units=["u1"])
    respuesta, _, _, _ = _consultar(client, artefacto, [BAJO, ALTO], [_respuesta()])
    registro = _registro(db, respuesta)
    assert registro.outcome == "answered"
    assert registro.reject_reason == "Pregunta limpia: «Natalia Soto Solís» (con resultados)"


def test_la_nota_sin_resultados_queda_en_uso(client, db, base, make_artifact):
    artefacto = make_artifact(units=["u1"])
    respuesta, _, _, _ = _consultar(client, artefacto, [BAJO, BAJO])
    registro = _registro(db, respuesta)
    assert registro.outcome == "no_info"
    assert registro.reject_reason == "Pregunta limpia: «Natalia Soto Solís» (sin resultados)"


def test_el_modelo_responde_sin_informacion_tras_un_segundo_intento_con_resultados(client, db, base, make_artifact):
    artefacto = make_artifact(units=["u1"])
    respuesta, _, modelo, _ = _consultar(
        client, artefacto, [BAJO, ALTO], [_respuesta("SIN_INFORMACION")]
    )
    registro = _registro(db, respuesta)
    assert respuesta.json()["no_info"] is True and modelo.answer.call_count == 1
    assert registro.outcome == "no_info"
    assert registro.reject_reason == "Pregunta limpia: «Natalia Soto Solís» (con resultados)"


def test_sin_segundo_intento_no_hay_nota(client, db, base, make_artifact):
    artefacto = make_artifact(units=["u1"])
    respuesta, _, _, _ = _consultar(client, artefacto, [ALTO], [_respuesta()])
    assert _registro(db, respuesta).reject_reason is None


def test_las_notas_se_unen_en_el_orden_pregunta_limpia_corte_citas(client, db, base, make_artifact):
    artefacto = make_artifact(units=["u1"])
    # Primer intento cortado, el reintento termina bien y no cita nada (regla de seguridad de la 006).
    respuesta, _, modelo, _ = _consultar(
        client, artefacto, [BAJO, ALTO],
        [_respuesta("Cortada", motivo="length"), _respuesta("Es una persona.")],
        query_retry_cut_answers="on", query_cited_sources="on",
    )
    registro = _registro(db, respuesta)
    assert registro.reject_reason == (
        "Pregunta limpia: «Natalia Soto Solís» (con resultados); "
        "Respuesta cortada: se reintentó; Fuentes: sin citas utilizables, se mostraron todas"
    )
    # El segundo intento no agrega llamadas: solo el reintento por corte de la feature 007.
    assert modelo.answer.call_count == 2
