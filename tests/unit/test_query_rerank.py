"""La ruta POST /query con el reranker local (feature 009): candidatos, corte por puntaje, notas de Uso, caída a la
similitud y convivencia con las features 006 a 008. El reranker, el almacén, los embeddings y el modelo son simulados."""

import logging
from unittest.mock import MagicMock, patch

import pytest

from mia.api.routes import query as query_routes
from mia.config import settings
from mia.rag import rerank
from mia.rag.llm import LLMAnswer
from mia.rag.rerank import RerankProvider, RerankTimeout
from mia.storage.models import Document, Domain, QueryLog, Unit
from mia.storage.vector_store import SearchResult

UMBRAL = 0.82
PREGUNTA = "¿Quién es Natalia Soto Solís?"
DOCUMENTOS = 30


@pytest.fixture(autouse=True)
def estado_limpio():
    rerank.reset_rerank_state()
    yield
    rerank.reset_rerank_state()


@pytest.fixture
def base(db, modes_config):
    with db() as session:
        session.add(Unit(id="u1", name="Computación"))
        session.flush()
        session.add(Domain(id="dom-1", unit_id="u1", name="Tesis", description=""))
        session.flush()
        for i in range(1, DOCUMENTOS + 1):
            session.add(
                Document(
                    id=f"doc-{i}", domain_id="dom-1", filename=f"Doc{i}.pdf", source_type="pdf", file_hash=f"h{i}",
                    status="done",
                )
            )
        session.commit()


def _candidato(i):
    """El candidato i por coseno: 1 es el más parecido (0,95) y cada puesto baja 0,01."""
    return SearchResult(
        chunk_id=f"c{i}", document_id=f"doc-{i}", domain="dom-1", text=f"texto del documento {i}",
        score=round(0.95 - 0.01 * (i - 1), 4), chunk_index=0,
    )


CANDIDATOS = [_candidato(i) for i in range(1, DOCUMENTOS + 1)]


class _Almacen:
    """Devuelve la lista de la búsqueda número N recortada al `limit` pedido, como un almacén real."""

    def __init__(self, busquedas):
        self.busquedas = list(busquedas)
        self.llamadas = []

    def search(self, vector, domains, limit):
        self.llamadas.append({"vector": vector, "domains": domains, "limit": limit})
        n = len(self.llamadas) - 1
        return self.busquedas[n][:limit] if n < len(self.busquedas) else []

    def count_chunks(self, document_id):
        return 1

    def get_chunks(self, document_id, indexes):
        return [
            SearchResult(
                chunk_id=f"{document_id}-{i}", document_id=document_id, domain="dom-1",
                text=f"texto del {document_id}", score=0.0, chunk_index=i,
            )
            for i in indexes
            if i == 0
        ]


class _Reranker(RerankProvider):
    """Da el logit que le diga `logit(texto)` y recuerda cada llamada."""

    def __init__(self, logit, error=None):
        self.logit = logit
        self.error = error
        self.llamadas = []

    def score(self, query, passages, deadline=None):
        self.llamadas.append({"query": query, "passages": list(passages), "deadline": deadline})
        if self.error is not None:
            raise self.error
        return [self.logit(p) for p in passages]


def _logit_solo(numero, alto=8.0, bajo=-8.0):
    return lambda texto: alto if texto == f"texto del documento {numero}" else bajo


def _respuesta(texto="Es una persona.", costo=0.01):
    return LLMAnswer(text=texto, finish_reason="stop", cost_usd=costo, prompt_tokens=100, completion_tokens=20)


def _consultar(client, artefacto, busquedas, reranker, respuestas=(), pregunta=PREGUNTA, modo="literal", **opciones):
    """Devuelve (respuesta HTTP, almacén, modelo, embeddings, reranker)."""
    almacen = _Almacen(busquedas)
    embeddings = MagicMock()
    embeddings.embed.side_effect = lambda textos, is_query=False: [[float(len(textos[0])), 0.2]]
    modelo = MagicMock()
    modelo.answer.side_effect = list(respuestas)
    valores = {
        "query_similarity_threshold": UMBRAL, "query_search_limit": 8, "query_search_limit_razonamiento": 16,
        "query_clean_question": "off", "query_complete_context": "off", "query_retry_cut_answers": "off",
        "query_cited_sources": "off", "rerank_provider": "local", "rerank_candidates": 30, "rerank_min_score": 0.5,
        "rerank_budget_ms": 2500,
    }
    valores.update(opciones)
    with (
        patch.multiple(settings, **valores),
        patch.object(query_routes, "get_vector_store", return_value=almacen),
        patch.object(query_routes, "get_embedding_provider", return_value=embeddings),
        patch.object(query_routes, "get_llm_provider", return_value=modelo),
        patch.object(query_routes, "get_rerank_provider", return_value=reranker),
    ):
        respuesta = client.post(
            "/query", json={"domains": ["dom-1"], "question": pregunta, "mode": modo}, headers=artefacto.headers
        )
    return respuesta, almacen, modelo, embeddings, reranker


def _documentos(modelo):
    return [c.document for c in modelo.answer.call_args.args[1]]


def _registro(db, respuesta):
    with db() as session:
        return session.get(QueryLog, respuesta.json()["id"])


# --- US1: recuperar y reordenar ----------------------------------------------------------------


def test_el_documento_del_puesto_12_llega_al_modelo_aunque_el_modo_trae_8(client, base, make_artifact):
    artefacto = make_artifact(units=["u1"])
    reranker = _Reranker(_logit_solo(12))
    respuesta, almacen, modelo, _, _ = _consultar(client, artefacto, [CANDIDATOS], reranker, [_respuesta()])
    assert respuesta.status_code == 200 and respuesta.json()["no_info"] is False
    assert almacen.llamadas[0]["limit"] == 30  # RERANK_CANDIDATES y no los 8 del modo
    assert _documentos(modelo) == ["Doc12.pdf"]
    assert [s["document"] for s in respuesta.json()["sources"]] == ["Doc12.pdf"]
    # El reranker puntúa los 30 textos contra la pregunta original; el modelo recibe la pregunta original.
    assert reranker.llamadas[0]["query"] == PREGUNTA
    assert reranker.llamadas[0]["passages"] == [c.text for c in CANDIDATOS]
    assert modelo.answer.call_args.args[0] == PREGUNTA


@pytest.mark.parametrize(("modo", "limite"), [("literal", 8), ("razonamiento", 16)])
def test_nunca_llegan_mas_fragmentos_que_el_limite_del_modo_y_en_el_orden_del_reranker(
    client, base, make_artifact, modo, limite
):
    artefacto = make_artifact(units=["u1"], modes="literal,razonamiento")
    # Todos pasan el mínimo; los de número mayor puntúan más alto, al revés que el coseno.
    reranker = _Reranker(lambda texto: float(texto.rsplit(" ", 1)[1]))
    _, _, modelo, _, _ = _consultar(client, artefacto, [CANDIDATOS], reranker, [_respuesta()], modo=modo)
    documentos = _documentos(modelo)
    assert len(documentos) == limite
    assert documentos[0] == "Doc30.pdf"  # el mayor puntaje primero
    assert documentos == [f"Doc{n}.pdf" for n in range(30, 30 - limite, -1)]


def test_un_documento_bajo_el_umbral_de_coseno_llega_si_el_reranker_lo_aprueba(client, base, make_artifact):
    artefacto = make_artifact(units=["u1"])
    cubillo = SearchResult(
        chunk_id="cubillo", document_id="doc-3", domain="dom-1", text="Luis Diego Cubillo Guevara", score=0.819,
        chunk_index=0,
    )
    ajenos = [_candidato(i) for i in (1, 2)]
    reranker = _Reranker(lambda texto: 6.0 if "Cubillo" in texto else -7.0)
    respuesta, _, modelo, _, _ = _consultar(
        client, artefacto, [[*ajenos, cubillo]], reranker, [_respuesta()]
    )
    assert respuesta.json()["no_info"] is False
    assert _documentos(modelo) == ["Doc3.pdf"]


def test_nunca_se_piden_menos_candidatos_que_el_limite_del_modo(client, base, make_artifact):
    artefacto = make_artifact(units=["u1"], modes="literal,razonamiento")
    reranker = _Reranker(_logit_solo(1))
    _, almacen, _, _, _ = _consultar(
        client, artefacto, [CANDIDATOS], reranker, [_respuesta()], modo="razonamiento", rerank_candidates=5
    )
    assert almacen.llamadas[0]["limit"] == 16


def test_sin_candidatos_no_se_invoca_al_reranker(client, base, make_artifact):
    artefacto = make_artifact(units=["u1"])
    reranker = _Reranker(_logit_solo(1))
    respuesta, _, modelo, _, _ = _consultar(client, artefacto, [[]], reranker, [_respuesta()])
    assert respuesta.json()["no_info"] is True and modelo.answer.call_count == 0
    assert reranker.llamadas == []


# --- US2: sin información ----------------------------------------------------------------------


def test_si_ninguno_supera_el_minimo_es_sin_informacion_sin_llamar_al_modelo(client, db, base, make_artifact):
    artefacto = make_artifact(units=["u1"])
    reranker = _Reranker(lambda texto: -6.0)
    respuesta, _, modelo, _, _ = _consultar(client, artefacto, [CANDIDATOS], reranker, [_respuesta()])
    assert respuesta.json()["no_info"] is True
    assert modelo.answer.call_count == 0
    registro = _registro(db, respuesta)
    assert registro.outcome == "no_info" and float(registro.cost_usd) == 0
    assert registro.reject_reason == "Reranker: ninguno sobre el mínimo 0.50, mejor 0.002 de 30"


def test_la_nota_de_una_respuesta_lleva_el_mejor_puntaje(client, db, base, make_artifact):
    artefacto = make_artifact(units=["u1"])
    respuesta, _, _, _, _ = _consultar(client, artefacto, [CANDIDATOS], _Reranker(_logit_solo(4)), [_respuesta()])
    registro = _registro(db, respuesta)
    assert registro.outcome == "answered"
    assert registro.reject_reason == "Reranker: mejor 1.000, 1 de 30 sobre el mínimo 0.50"


def test_el_minimo_configurable_cambia_el_corte(client, base, make_artifact):
    artefacto = make_artifact(units=["u1"])
    def logit(texto):
        return 1.0  # sigmoide 0,73

    con_minimo_bajo, _, modelo, _, _ = _consultar(
        client, artefacto, [CANDIDATOS], _Reranker(logit), [_respuesta()], rerank_min_score=0.7
    )
    assert con_minimo_bajo.json()["no_info"] is False and len(_documentos(modelo)) == 8
    con_minimo_alto, _, modelo2, _, _ = _consultar(
        client, artefacto, [CANDIDATOS], _Reranker(logit), [_respuesta()], rerank_min_score=0.8
    )
    assert con_minimo_alto.json()["no_info"] is True and modelo2.answer.call_count == 0


def test_con_la_pregunta_limpia_el_reranker_puntua_contra_la_pregunta_original(client, db, base, make_artifact):
    artefacto = make_artifact(units=["u1"])
    reranker = _Reranker(lambda texto: -6.0 if texto != "texto del documento 20" else 6.0)
    # Primer intento: 3 candidatos sin aprobar. Segundo intento (nombre solo): trae el 20 y repite el 1.
    primera = CANDIDATOS[:3]
    segunda = [CANDIDATOS[0], CANDIDATOS[19]]
    respuesta, almacen, modelo, embeddings, _ = _consultar(
        client, artefacto, [primera, segunda], reranker, [_respuesta()], query_clean_question="on"
    )
    assert respuesta.json()["no_info"] is False and _documentos(modelo) == ["Doc20.pdf"]
    assert len(almacen.llamadas) == 2
    assert [c.args[0][0] for c in embeddings.embed.call_args_list] == [PREGUNTA, "Natalia Soto Solís"]
    # Las dos puntuaciones son contra la pregunta original, y el candidato repetido no se puntúa de nuevo.
    assert [c["query"] for c in reranker.llamadas] == [PREGUNTA, PREGUNTA]
    assert reranker.llamadas[1]["passages"] == [CANDIDATOS[19].text]
    registro = _registro(db, respuesta)
    assert registro.reject_reason == (
        "Reranker: mejor 0.998, 1 de 2 sobre el mínimo 0.50; Pregunta limpia: «Natalia Soto Solís» (con resultados)"
    )


def test_sin_informacion_tras_dos_intentos_lleva_las_dos_notas(client, db, base, make_artifact):
    artefacto = make_artifact(units=["u1"])
    reranker = _Reranker(lambda texto: -6.0)
    respuesta, _, modelo, _, _ = _consultar(
        client, artefacto, [CANDIDATOS[:3], CANDIDATOS[3:6]], reranker, query_clean_question="on"
    )
    assert respuesta.json()["no_info"] is True and modelo.answer.call_count == 0
    registro = _registro(db, respuesta)
    assert registro.reject_reason == (
        "Reranker: ninguno sobre el mínimo 0.50, mejor 0.002 de 3; Pregunta limpia: «Natalia Soto Solís» (sin resultados)"
    )


def test_las_notas_salen_en_el_orden_reranker_limpia_corte_citas(client, db, base, make_artifact):
    artefacto = make_artifact(units=["u1"])
    reranker = _Reranker(lambda texto: 6.0 if texto == "texto del documento 20" else -6.0)
    cortada = LLMAnswer(text="Parte uno.", finish_reason="length", cost_usd=0.01, prompt_tokens=10, completion_tokens=5)
    completa = LLMAnswer(
        text="Parte uno y dos.\nFUENTES: 1", finish_reason="stop", cost_usd=0.01, prompt_tokens=10, completion_tokens=5
    )
    respuesta, _, modelo, _, _ = _consultar(
        client, artefacto, [CANDIDATOS[:3], CANDIDATOS[19:20]], reranker, [cortada, completa],
        query_clean_question="on", query_retry_cut_answers="on", query_cited_sources="on",
        query_complete_context="on",
    )
    assert respuesta.status_code == 200 and modelo.answer.call_count == 2
    notas = _registro(db, respuesta).reject_reason.split("; ")
    assert notas[0].startswith("Reranker: mejor")
    assert notas[1].startswith("Pregunta limpia:")
    assert len(notas) >= 3  # sigue la nota del reintento de la 007
    # Con las citas encendidas, los pasajes numerados siguen el orden del reranker.
    assert modelo.answer.call_args.args[1][0].reference == 1


# --- US3: apagado y caídas ---------------------------------------------------------------------


@pytest.mark.parametrize("valor", ["none", "NONE", "xyz"])
def test_apagado_todo_es_como_antes(client, db, base, make_artifact, valor):
    artefacto = make_artifact(units=["u1"])
    reranker = _Reranker(_logit_solo(12))
    # get_rerank_provider real (sin parchear): con none o un valor inválido no hay proveedor.
    almacen = _Almacen([CANDIDATOS])
    embeddings = MagicMock()
    embeddings.embed.side_effect = lambda textos, is_query=False: [[1.0, 0.2]]
    modelo = MagicMock()
    modelo.answer.side_effect = [_respuesta()]
    with (
        patch.multiple(settings, rerank_provider=valor, query_similarity_threshold=UMBRAL, query_search_limit=8),
        patch.object(query_routes, "get_vector_store", return_value=almacen),
        patch.object(query_routes, "get_embedding_provider", return_value=embeddings),
        patch.object(query_routes, "get_llm_provider", return_value=modelo),
    ):
        respuesta = client.post(
            "/query", json={"domains": ["dom-1"], "question": PREGUNTA, "mode": "literal"}, headers=artefacto.headers
        )
    assert respuesta.status_code == 200
    assert [llamada["limit"] for llamada in almacen.llamadas] == [8]  # el límite del modo, no 30
    assert _documentos(modelo) == [f"Doc{i}.pdf" for i in range(1, 9)]  # el orden y el umbral de coseno
    assert reranker.llamadas == []
    registro = _registro(db, respuesta)
    assert registro.outcome == "answered" and registro.reject_reason is None


def test_el_valor_por_defecto_es_none():
    assert type(settings)(_env_file=None).rerank_provider == "none"


@pytest.mark.parametrize("error", [RuntimeError("boom"), RerankTimeout("tarde")])
def test_si_el_reranker_falla_se_responde_por_similitud_con_nota_y_aviso(
    client, db, base, make_artifact, caplog, error
):
    artefacto = make_artifact(units=["u1"])
    reranker = _Reranker(_logit_solo(12), error=error)
    with caplog.at_level(logging.WARNING):
        respuesta, _, modelo, _, _ = _consultar(client, artefacto, [CANDIDATOS], reranker, [_respuesta()])
    assert respuesta.status_code == 200 and respuesta.json()["no_info"] is False
    assert _documentos(modelo) == [f"Doc{i}.pdf" for i in range(1, 9)]  # los 8 primeros por coseno
    assert any("reranker falló" in m for m in caplog.messages)
    registro = _registro(db, respuesta)
    assert registro.reject_reason == "Reranker no disponible: se usó la similitud"


def test_la_caida_a_similitud_respeta_el_umbral_de_coseno(client, db, base, make_artifact):
    artefacto = make_artifact(units=["u1"])
    bajos = [SearchResult(chunk_id="x", document_id="doc-1", domain="dom-1", text="t", score=0.78, chunk_index=0)]
    reranker = _Reranker(_logit_solo(1), error=RuntimeError("boom"))
    respuesta, _, modelo, _, _ = _consultar(client, artefacto, [bajos], reranker, [_respuesta()])
    assert respuesta.json()["no_info"] is True and modelo.answer.call_count == 0
    assert _registro(db, respuesta).reject_reason == "Reranker no disponible: se usó la similitud"


def test_tras_una_caida_el_segundo_intento_no_vuelve_a_llamar_al_reranker(client, base, make_artifact):
    artefacto = make_artifact(units=["u1"])
    reranker = _Reranker(_logit_solo(1), error=RuntimeError("boom"))
    bajos = [SearchResult(chunk_id="x", document_id="doc-1", domain="dom-1", text="t", score=0.78, chunk_index=0)]
    respuesta, almacen, modelo, _, _ = _consultar(
        client, artefacto, [bajos, [CANDIDATOS[0]]], reranker, [_respuesta()], query_clean_question="on"
    )
    assert len(reranker.llamadas) == 1
    assert [llamada["limit"] for llamada in almacen.llamadas] == [30, 8]
    assert respuesta.json()["no_info"] is False and _documentos(modelo) == ["Doc1.pdf"]


def test_veinte_consultas_con_el_reranker_caido_responden_todas(client, base, make_artifact):
    artefacto = make_artifact(units=["u1"], cap=5)
    for _ in range(20):
        reranker = _Reranker(_logit_solo(1), error=RuntimeError("boom"))
        respuesta, *_ = _consultar(client, artefacto, [CANDIDATOS], reranker, [_respuesta(costo=0.0001)])
        assert respuesta.status_code == 200


def test_el_presupuesto_de_tiempo_se_pasa_al_reranker(client, base, make_artifact):
    artefacto = make_artifact(units=["u1"])
    con_presupuesto = _Reranker(_logit_solo(1))
    _consultar(client, artefacto, [CANDIDATOS], con_presupuesto, [_respuesta()], rerank_budget_ms=50)
    assert con_presupuesto.llamadas[0]["deadline"] is not None
    sin_presupuesto = _Reranker(_logit_solo(1))
    _consultar(client, artefacto, [CANDIDATOS], sin_presupuesto, [_respuesta()], rerank_budget_ms=0)
    assert sin_presupuesto.llamadas[0]["deadline"] is None


def test_una_consulta_rechazada_no_busca_ni_puntua(client, base, make_artifact):
    artefacto = make_artifact(units=["u1"], cap=0.0001)
    _consultar(client, artefacto, [CANDIDATOS], _Reranker(_logit_solo(1)), [_respuesta(costo=0.01)])  # gasta el tope
    reranker = _Reranker(_logit_solo(1))
    respuesta, almacen, modelo, _, _ = _consultar(client, artefacto, [CANDIDATOS], reranker, [_respuesta()])
    assert respuesta.status_code == 429
    assert almacen.llamadas == [] and reranker.llamadas == [] and modelo.answer.call_count == 0
    # Un modo no permitido tampoco llega a la búsqueda.
    respuesta2, almacen2, _, _, reranker2 = _consultar(
        client, make_artifact("Otro artefacto", units=["u1"]), [CANDIDATOS], _Reranker(_logit_solo(1)),
        modo="razonamiento"
    )
    assert respuesta2.status_code == 403
    assert almacen2.llamadas == [] and reranker2.llamadas == []
