"""La ruta POST /query con la búsqueda híbrida (feature 010): documentos que llegan por palabras, siglas, casos sin
respuesta, apagado, caídas y convivencia con las features 006 a 009. El almacén, los embeddings y el modelo son
simulados; el índice de palabras es una tabla de palabra a fragmentos."""

import logging
import time
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import delete

from mia.api.routes import query as query_routes
from mia.config import settings
from mia.rag import lexical, rerank
from mia.rag.equivalences import invalidate_equivalences
from mia.rag.llm import NO_INFO_MARKER, LLMAnswer
from mia.rag.rerank import RerankProvider
from mia.storage.models import Document, Domain, QueryLog, SiglaEquivalence, Unit
from mia.storage.vector_store import SearchResult

UMBRAL = 0.82
PREGUNTA = "¿Quién es Joseph Obando Sandí?"
DOCUMENTOS = 12


@pytest.fixture(autouse=True)
def estado_limpio():
    lexical.reset_lexical_state()
    rerank.reset_rerank_state()
    invalidate_equivalences()
    yield
    lexical.reset_lexical_state()
    rerank.reset_rerank_state()
    invalidate_equivalences()


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


def fragmento(i, score=0.95, texto=None):
    return SearchResult(
        chunk_id=f"c{i}", document_id=f"doc-{i}", domain="dom-1", text=texto or f"texto del documento {i}",
        score=score, chunk_index=0,
    )


class _Almacen:
    """Búsqueda por significado fija (`vectores`) más un índice de palabras (`indice`: palabra o frase a ids)."""

    def __init__(self, vectores, indice=None, fragmentos=(), error=None, pausa=0.0):
        self.vectores = list(vectores)
        self.indice = indice or {}
        self.por_id = {f.chunk_id: f for f in fragmentos}
        self.error = error
        self.pausa = pausa
        self.busquedas = []
        self.palabras = []
        self.puntuaciones = []

    def search(self, vector, domains, limit):
        self.busquedas.append({"domains": domains, "limit": limit})
        return self.vectores[:limit]

    def match_chunks(self, domains, text, limit):
        self.palabras.append({"domains": list(domains), "text": text, "limit": limit})
        if self.pausa:
            time.sleep(self.pausa)
        if self.error is not None:
            raise self.error
        return list(self.indice.get(text, []))[:limit]

    def score_chunks(self, embedding, domains, chunk_ids):
        self.puntuaciones.append({"domains": list(domains), "ids": list(chunk_ids)})
        if isinstance(self.error, NotImplementedError):
            raise self.error
        return [self.por_id[i] for i in chunk_ids if i in self.por_id]

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


def respuesta(texto="Es una persona.", costo=0.01):
    return LLMAnswer(text=texto, finish_reason="stop", cost_usd=costo, prompt_tokens=100, completion_tokens=20)


def consultar(client, artefacto, almacen, respuestas=(), pregunta=PREGUNTA, modo="literal", reranker=None, **opciones):
    """Devuelve (respuesta HTTP, almacén, modelo)."""
    embeddings = MagicMock()
    embeddings.embed.side_effect = lambda textos, is_query=False: [[float(len(textos[0])), 0.2]]
    modelo = MagicMock()
    modelo.answer.side_effect = list(respuestas)
    valores = {
        "query_similarity_threshold": UMBRAL, "query_search_limit": 8, "query_search_limit_razonamiento": 16,
        "query_clean_question": "off", "query_complete_context": "off", "query_retry_cut_answers": "off",
        "query_cited_sources": "off", "rerank_provider": "none", "query_hybrid_search": "on",
        "hybrid_max_doc_freq": 5, "hybrid_lexical_limit": 20, "hybrid_lexical_slots": 3, "hybrid_budget_ms": 2000,
        "hybrid_equivalences_ttl_seconds": 0,
    }
    valores.update(opciones)
    with (
        patch.multiple(settings, **valores),
        patch.object(query_routes, "get_vector_store", return_value=almacen),
        patch.object(query_routes, "get_embedding_provider", return_value=embeddings),
        patch.object(query_routes, "get_llm_provider", return_value=modelo),
        patch.object(query_routes, "get_rerank_provider", return_value=reranker),
    ):
        http = client.post(
            "/query", json={"domains": ["dom-1"], "question": pregunta, "mode": modo}, headers=artefacto.headers
        )
    return http, almacen, modelo


def documentos(modelo):
    return [c.document for c in modelo.answer.call_args.args[1]]


def registro(db, http):
    with db() as session:
        return session.get(QueryLog, http.json()["id"])


JOSEPH = fragmento(
    7, score=0.78, texto="Arquitectura web. Joseph Obando2023800202 Resumen"
)
# Joseph (3 fragmentos), Obando (2, uno ajeno), Sandí no aparece en el corpus.
INDICE_JOSEPH = {"joseph": ["c7", "c9", "c10"], "obando": ["c7", "c11"], "sandi": []}
FRAGMENTOS = [JOSEPH, fragmento(9, 0.7), fragmento(10, 0.7), fragmento(11, 0.7, "Kenneth Obando asiste")]


# --- US1: documentos que llegan por palabras ------------------------------------------------------


def test_un_documento_bajo_el_umbral_llega_al_modelo_por_palabras(client, base, make_artifact, db):
    artefacto = make_artifact(units=["u1"])
    almacen = _Almacen([JOSEPH], INDICE_JOSEPH, FRAGMENTOS)
    http, almacen, modelo = consultar(client, artefacto, almacen, [respuesta()])
    assert http.status_code == 200 and http.json()["no_info"] is False
    assert documentos(modelo) == ["Doc7.pdf"]
    assert [s["document"] for s in http.json()["sources"]] == ["Doc7.pdf"]
    # La pregunta original va al modelo; los dominios de la consulta van a las dos búsquedas (FR-004).
    assert modelo.answer.call_args.args[0] == PREGUNTA
    assert {tuple(p["domains"]) for p in almacen.palabras} == {("dom-1",)}
    assert almacen.puntuaciones[0]["domains"] == ["dom-1"]
    assert {p["text"] for p in almacen.palabras} == {"joseph", "obando", "sandi"}
    assert all(p["limit"] == 6 for p in almacen.palabras)  # hybrid_max_doc_freq + 1
    assert registro(db, http).reject_reason == "Búsqueda híbrida: 1 por palabras, 1 nuevos"


def test_un_documento_que_ya_llegaba_por_significado_sigue_llegando(client, base, make_artifact):
    artefacto = make_artifact(units=["u1"])
    vectores = [fragmento(1, 0.95), fragmento(2, 0.9)]
    almacen = _Almacen(vectores, INDICE_JOSEPH, FRAGMENTOS + vectores)
    _, _, modelo = consultar(client, artefacto, almacen, [respuesta()])
    assert set(documentos(modelo)) == {"Doc1.pdf", "Doc2.pdf", "Doc7.pdf"}


@pytest.mark.parametrize(("modo", "limite"), [("literal", 8), ("razonamiento", 16)])
def test_nunca_llegan_mas_fragmentos_que_el_limite_del_modo(client, base, make_artifact, modo, limite):
    artefacto = make_artifact(units=["u1"], modes="literal,razonamiento")
    vectores = [fragmento(i, 0.99 - i * 0.001) for i in range(1, DOCUMENTOS + 1)]
    # Muchos candidatos léxicos que cumplen la regla (comparten palabras con todo el corpus).
    ids = [f"c{i}" for i in range(1, 6)]
    indice = {"joseph": ids, "obando": ids, "sandi": []}
    almacen = _Almacen(vectores, indice, vectores)
    _, _, modelo = consultar(client, artefacto, almacen, [respuesta()], modo=modo, hybrid_lexical_slots=16)
    assert len(documentos(modelo)) <= limite


def test_con_la_opcion_apagada_no_se_llama_a_la_parte_lexical(client, base, make_artifact, db):
    artefacto = make_artifact(units=["u1"])
    almacen = _Almacen([JOSEPH], INDICE_JOSEPH, FRAGMENTOS)
    http, almacen, modelo = consultar(client, artefacto, almacen, [], query_hybrid_search="off")
    assert http.json()["no_info"] is True  # el coseno de Joseph (0,78) está bajo el umbral, como hoy
    assert almacen.palabras == [] and almacen.puntuaciones == []
    modelo.answer.assert_not_called()
    assert registro(db, http).reject_reason is None


# --- US2: siglas ---------------------------------------------------------------------------------------

LINEAS = fragmento(8, 0.7, "Líneas de TFG de la maestría")
INDICE_TFG = {
    "tfg": ["c8"],
    "trabajo final de graduacion": [],
    "maestria": [f"x{i}" for i in range(20)],
    "lineas": ["c8", "c9", "c10"],
}


def test_la_forma_desarrollada_y_la_sigla_encuentran_el_mismo_documento(client, base, make_artifact):
    artefacto = make_artifact(units=["u1"])
    pregunta_larga = "¿Qué es el trabajo final de graduación?"
    pregunta_sigla = "¿Qué es el TFG?"
    resultados = []
    for pregunta in (pregunta_larga, pregunta_sigla):
        almacen = _Almacen([], INDICE_TFG, [LINEAS])
        http, _, modelo = consultar(client, artefacto, almacen, [respuesta()], pregunta=pregunta)
        assert http.json()["no_info"] is False
        resultados.append(documentos(modelo))
    assert resultados[0] == resultados[1] == ["Doc8.pdf"]


def test_sin_la_equivalencia_la_forma_desarrollada_no_se_relaciona_con_la_sigla(client, base, make_artifact, db):
    with db() as session:
        session.execute(delete(SiglaEquivalence))
        session.commit()
    artefacto = make_artifact(units=["u1"])
    indice = dict(INDICE_TFG, trabajo=list("abcdefgh"), final=list("abcdefgh"), graduacion=list("abcdefgh"))
    almacen = _Almacen([], indice, [LINEAS])
    http, _, modelo = consultar(
        client, artefacto, almacen, [respuesta()], pregunta="¿Qué es el trabajo final de graduación?"
    )
    assert http.json()["no_info"] is True
    modelo.answer.assert_not_called()


def test_una_equivalencia_nueva_se_usa_en_la_consulta_siguiente(client, base, make_artifact, db):
    artefacto = make_artifact(units=["u1"])
    almacen = _Almacen([], {"pln": ["c8"], "procesamiento de lenguaje natural": []}, [LINEAS])
    http, _, _ = consultar(client, artefacto, almacen, [], pregunta="¿Qué es el procesamiento de lenguaje natural?")
    assert http.json()["no_info"] is True
    with db() as session:
        session.add(
            SiglaEquivalence(
                id="e-pln", sigla="pln", form="procesamiento de lenguaje natural", sigla_display="PLN",
                form_display="Procesamiento de Lenguaje Natural", created_by="prueba",
            )
        )
        session.commit()
    invalidate_equivalences()
    almacen = _Almacen([], {"pln": ["c8"], "procesamiento de lenguaje natural": []}, [LINEAS])
    http, _, modelo = consultar(
        client, artefacto, almacen, [respuesta()], pregunta="¿Qué es el procesamiento de lenguaje natural?"
    )
    assert http.json()["no_info"] is False and documentos(modelo) == ["Doc8.pdf"]


# --- US3: sin información ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "pregunta",
    [
        "¿Quién es Zacarías Fernández Pizarro?",
        "¿Qué es el PRGX?",
        "¿Qué es el Departamento de Hidrología Lunar?",
    ],
)
def test_lo_inventado_responde_sin_informacion_sin_llamar_al_modelo(client, base, make_artifact, db, pregunta):
    artefacto = make_artifact(units=["u1"])
    # fernandez aparece en 4 fragmentos; el resto de las palabras no existe en el corpus.
    indice = {"fernandez": ["c1", "c2", "c3", "c4"]}
    almacen = _Almacen([], indice, [fragmento(i, 0.7) for i in range(1, 5)])
    http, _, modelo = consultar(client, artefacto, almacen, [], pregunta=pregunta)
    assert http.json()["no_info"] is True
    modelo.answer.assert_not_called()
    assert registro(db, http).reject_reason is None  # sin candidatos léxicos no hay nota


def test_una_pregunta_de_palabras_comunes_no_trae_candidatos(client, base, make_artifact):
    artefacto = make_artifact(units=["u1"])
    comunes = [f"x{i}" for i in range(40)]
    indice = {"horario": comunes, "atencion": comunes, "biblioteca": comunes}
    almacen = _Almacen([], indice, [])
    http, almacen, modelo = consultar(
        client, artefacto, almacen, [], pregunta="¿Cuál es el horario de atención de la biblioteca?"
    )
    assert http.json()["no_info"] is True
    modelo.answer.assert_not_called()
    assert almacen.puntuaciones == []  # sin candidatos no se pide texto ni coseno


def test_un_dato_que_no_existe_con_una_palabra_ausente_no_llega_al_modelo(client, base, make_artifact):
    # EN9: obligatorio no existe en el corpus y cuenta como específico: joseph y obando solo suman 2 de 4.
    artefacto = make_artifact(units=["u1"])
    almacen = _Almacen([], INDICE_JOSEPH, FRAGMENTOS)
    http, _, modelo = consultar(
        client, artefacto, almacen, [], pregunta="¿Qué es obligatorio en el trabajo de Joseph Obando Sandí?"
    )
    assert http.json()["no_info"] is True
    modelo.answer.assert_not_called()


def test_un_nombre_real_con_un_dato_que_no_existe_llega_al_modelo_y_sigue_sin_informacion(
    client, base, make_artifact, db
):
    artefacto = make_artifact(units=["u1"])
    almacen = _Almacen([JOSEPH], INDICE_JOSEPH, FRAGMENTOS)
    sin_info = respuesta(NO_INFO_MARKER)
    http, _, modelo = consultar(client, artefacto, almacen, [sin_info])
    assert http.json()["no_info"] is True and http.json()["sources"] == []
    modelo.answer.assert_called_once()
    log = registro(db, http)
    assert log.outcome == "no_info" and float(log.cost_usd) > 0
    assert log.reject_reason == "Búsqueda híbrida: 1 por palabras, 1 nuevos"


def test_la_nota_se_une_a_las_demas_en_el_orden_estable(client, base, make_artifact, db):
    artefacto = make_artifact(units=["u1"])
    almacen = _Almacen([JOSEPH], INDICE_JOSEPH, FRAGMENTOS)
    http, _, _ = consultar(
        client, artefacto, almacen, [respuesta("Es una persona.\nFUENTES: 1")], query_cited_sources="on"
    )
    assert registro(db, http).reject_reason == "Búsqueda híbrida: 1 por palabras, 1 nuevos"
    # El reranker simulado aprueba todo: su nota precede a la híbrida.
    class Aprueba(RerankProvider):
        def score(self, query, passages, deadline=None):
            return [5.0 for _ in passages]

    almacen = _Almacen([JOSEPH], INDICE_JOSEPH, FRAGMENTOS)
    http, _, _ = consultar(
        client, artefacto, almacen, [respuesta()], reranker=Aprueba(), rerank_provider="local", rerank_min_score=0.5
    )
    nota = registro(db, http).reject_reason
    assert nota.startswith("Reranker:") and "; Búsqueda híbrida: " in nota


# --- US4: apagado y fallos ------------------------------------------------------------------------------


@pytest.mark.parametrize("valor", ["off", "", "si"])
def test_apagada_o_invalida_el_comportamiento_es_el_de_antes(client, base, make_artifact, db, valor):
    artefacto = make_artifact(units=["u1"])
    vectores = [fragmento(1, 0.95)]
    almacen = _Almacen(vectores, INDICE_JOSEPH, FRAGMENTOS + vectores)
    http, almacen, modelo = consultar(client, artefacto, almacen, [respuesta()], query_hybrid_search=valor)
    assert documentos(modelo) == ["Doc1.pdf"]
    assert almacen.palabras == [] and almacen.puntuaciones == []
    assert registro(db, http).reject_reason is None


def test_la_opcion_apagada_no_consulta_la_tabla_de_equivalencias(client, base, make_artifact):
    artefacto = make_artifact(units=["u1"])
    almacen = _Almacen([fragmento(1, 0.95)], {}, [])
    with patch.object(query_routes, "get_equivalences", side_effect=AssertionError("no debe leerse")):
        http, _, _ = consultar(client, artefacto, almacen, [respuesta()], query_hybrid_search="off")
    assert http.status_code == 200


@pytest.mark.parametrize(
    "error",
    [RuntimeError("sin índice"), NotImplementedError("sin búsqueda por palabras")],
)
def test_si_la_parte_lexical_falla_la_consulta_sigue_por_significado(client, base, make_artifact, db, caplog, error):
    artefacto = make_artifact(units=["u1"])
    vectores = [fragmento(1, 0.95)]
    almacen = _Almacen(vectores, INDICE_JOSEPH, FRAGMENTOS + vectores, error=error)
    with caplog.at_level(logging.WARNING):
        http, _, modelo = consultar(client, artefacto, almacen, [respuesta()])
    assert http.status_code == 200 and documentos(modelo) == ["Doc1.pdf"]
    assert registro(db, http).reject_reason == "Búsqueda por palabras no disponible: se usó el significado"
    assert [r for r in caplog.records if "búsqueda por palabras falló" in r.getMessage()]


def test_si_score_chunks_falla_la_consulta_sigue_por_significado(client, base, make_artifact, db):
    artefacto = make_artifact(units=["u1"])
    almacen = _Almacen([fragmento(1, 0.95)], INDICE_JOSEPH, FRAGMENTOS)
    almacen.score_chunks = MagicMock(side_effect=RuntimeError("Qdrant caído"))
    http, _, modelo = consultar(client, artefacto, almacen, [respuesta()])
    assert http.status_code == 200 and documentos(modelo) == ["Doc1.pdf"]
    assert registro(db, http).reject_reason == "Búsqueda por palabras no disponible: se usó el significado"


def test_si_la_parte_lexical_tarda_mas_que_el_presupuesto_la_consulta_sigue_por_significado(
    client, base, make_artifact, db
):
    artefacto = make_artifact(units=["u1"])
    almacen = _Almacen([fragmento(1, 0.95)], INDICE_JOSEPH, FRAGMENTOS, pausa=0.5)
    http, _, modelo = consultar(client, artefacto, almacen, [respuesta()], hybrid_budget_ms=50)
    assert http.status_code == 200 and documentos(modelo) == ["Doc1.pdf"]
    assert registro(db, http).reject_reason == "Búsqueda por palabras no disponible: se usó el significado"


def test_si_la_lista_de_equivalencias_no_se_puede_leer_la_consulta_sigue_sin_siglas(client, base, make_artifact):
    artefacto = make_artifact(units=["u1"])
    almacen = _Almacen([JOSEPH], INDICE_JOSEPH, FRAGMENTOS)
    with patch.object(query_routes, "get_equivalences", side_effect=RuntimeError("tabla ausente")):
        http, _, modelo = consultar(client, artefacto, almacen, [respuesta()])
    assert http.status_code == 200 and documentos(modelo) == ["Doc7.pdf"]


def test_el_aviso_de_fallo_sale_a_lo_sumo_una_vez_por_minuto(client, base, make_artifact, caplog, monkeypatch):
    artefacto = make_artifact(units=["u1"])
    monkeypatch.setattr(lexical, "_now", lambda: 5000.0)
    with caplog.at_level(logging.WARNING):
        for _ in range(3):
            almacen = _Almacen([fragmento(1, 0.95)], INDICE_JOSEPH, FRAGMENTOS, error=RuntimeError("caído"))
            consultar(client, artefacto, almacen, [respuesta()])
    assert len([r for r in caplog.records if "búsqueda por palabras falló" in r.getMessage()]) == 1


# --- Convivencia con 006 a 009 -----------------------------------------------------------------------------


def test_con_citas_las_fuentes_se_validan_contra_la_lista_fusionada(client, base, make_artifact):
    artefacto = make_artifact(units=["u1"])
    vectores = [fragmento(1, 0.95)]
    almacen = _Almacen(vectores, INDICE_JOSEPH, FRAGMENTOS + vectores)
    http, _, modelo = consultar(
        client, artefacto, almacen, [respuesta("Es una persona.\nFUENTES: 2")], query_cited_sources="on"
    )
    contexto = modelo.answer.call_args.args[1]
    assert [c.reference for c in contexto] == [1, 2]
    elegida = contexto[1].document
    assert [s["document"] for s in http.json()["sources"]] == [elegida]


def test_con_contexto_completo_el_documento_de_mayor_valor_de_fusion_es_el_principal(client, base, make_artifact):
    artefacto = make_artifact(units=["u1"])
    vectores = [fragmento(1, 0.95)]
    almacen = _Almacen(vectores, INDICE_JOSEPH, FRAGMENTOS + vectores)
    http, _, modelo = consultar(client, artefacto, almacen, [respuesta()], query_complete_context="on")
    assert http.status_code == 200 and "Doc1.pdf" in documentos(modelo)


def test_la_pregunta_limpia_se_repite_solo_si_la_lista_fusionada_quedo_vacia(client, base, make_artifact, db):
    artefacto = make_artifact(units=["u1"])
    # La primera búsqueda ya deja un fragmento por palabras: no hay segundo intento.
    almacen = _Almacen([], INDICE_JOSEPH, FRAGMENTOS)
    http, almacen, _ = consultar(client, artefacto, almacen, [respuesta()], query_clean_question="on")
    assert len(almacen.busquedas) == 1
    assert "Pregunta limpia" not in (registro(db, http).reject_reason or "")
    # Sin candidatos léxicos y sin coseno suficiente, sí se repite (y los léxicos no se piden otra vez).
    almacen = _Almacen([], {}, [])
    http, almacen, _ = consultar(client, artefacto, almacen, [], query_clean_question="on")
    assert len(almacen.busquedas) == 2
    assert len(almacen.palabras) == 3  # una vez por palabra de la pregunta original


def test_con_el_reranker_los_candidatos_lexicos_no_pasan_por_su_minimo(client, base, make_artifact):
    artefacto = make_artifact(units=["u1"])

    class Rechaza(RerankProvider):
        """Puntúa muy bajo todo, como el reranker hace con el documento de Joseph Obando."""

        def score(self, query, passages, deadline=None):
            return [-9.0 for _ in passages]

    almacen = _Almacen([JOSEPH], INDICE_JOSEPH, FRAGMENTOS)
    http, _, modelo = consultar(
        client, artefacto, almacen, [respuesta()], reranker=Rechaza(), rerank_provider="local", rerank_min_score=0.5
    )
    assert http.json()["no_info"] is False and documentos(modelo) == ["Doc7.pdf"]


@pytest.mark.parametrize("caso", ["permiso", "tope"])
def test_una_consulta_rechazada_no_llama_a_la_parte_lexical(client, base, make_artifact, caso):
    artefacto = make_artifact(units=["u1"], active=(caso != "permiso"), cap=0.0 if caso == "tope" else 0.5)
    almacen = _Almacen([JOSEPH], INDICE_JOSEPH, FRAGMENTOS)
    http, almacen, _ = consultar(client, artefacto, almacen, [])
    assert http.status_code in (403, 429)
    assert almacen.palabras == [] and almacen.puntuaciones == []


# --- US5: el índice de texto al arrancar ---------------------------------------------------------------------


def _arrancar(almacen, **opciones):
    from fastapi.testclient import TestClient

    from mia.api import main as api_main

    with (
        patch.multiple(settings, **opciones),
        patch.object(api_main, "init_db"),
        patch.object(api_main, "get_vector_store", return_value=almacen),
        patch.object(api_main, "get_embedding_provider", return_value=MagicMock(dimension=384)),
        patch.object(api_main, "warm_up_rerank_provider"),
        TestClient(api_main.app) as cliente,
    ):
        return cliente.get("/health").status_code


def test_con_la_opcion_encendida_el_arranque_asegura_el_indice_de_texto():
    almacen = MagicMock()
    assert _arrancar(almacen, query_hybrid_search="on") == 200
    almacen.ensure_text_index.assert_called_once_with()


@pytest.mark.parametrize("valor", ["off", "", "si"])
def test_con_la_opcion_apagada_el_arranque_no_toca_el_indice(valor):
    almacen = MagicMock()
    assert _arrancar(almacen, query_hybrid_search=valor) == 200
    almacen.ensure_text_index.assert_not_called()
    almacen.ensure_collection.assert_called_once_with(384)


def test_si_no_se_puede_crear_el_indice_la_api_arranca_igual_y_avisa(caplog):
    almacen = MagicMock()
    almacen.ensure_text_index.side_effect = RuntimeError("otros parámetros")
    with caplog.at_level(logging.WARNING):
        assert _arrancar(almacen, query_hybrid_search="on") == 200
    assert [r for r in caplog.records if "índice de texto" in r.getMessage()]


def test_la_ingesta_no_necesita_pasos_lexicales_adicionales():
    import inspect

    from mia.ingestion import pipeline

    fuente = inspect.getsource(pipeline)
    assert "match_chunks" not in fuente and "ensure_text_index" not in fuente
