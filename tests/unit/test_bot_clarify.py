"""Aclaración de programa en POST /bot/query (feature 013): búsqueda de decisión, BotQueryResponse y regresión de /query."""

import uuid
from unittest.mock import MagicMock, patch

import pytest

from mia.api.routes import query as query_routes
from mia.config import settings
from mia.rag import programs
from mia.rag.llm import LLMAnswer
from mia.storage.models import Bot, Document, Domain, QueryLog, Unit
from mia.storage.vector_store import SearchResult

CLAVE = "clave-del-servicio-de-prueba"
NUMERO = "647015955153740"

CIBER = "MAESTRÍA EN CIBERSEGURIDAD"
ANALITICA = "MAESTRÍA EN ANALÍTICA DE NEGOCIO (BUSINESS ANALYTICS)"
NO_INFO_TEXTO = "No encontré información suficiente"

TITULOS = {
    "ciber-admision": f"{CIBER}: ADMISIÓN\nFechas...",
    "ciber-plan": f"{CIBER}: PLAN DE ESTUDIOS\nBloques...",
    "ana-admision": f"{ANALITICA}: ADMISIÓN\nFechas...",
    "ana-presentacion": f"{ANALITICA}: PRESENTACIÓN\nCostos...",
    "suelto": "Un documento sin la forma del título\nTexto...",
}


@pytest.fixture(autouse=True)
def cache_de_programas_limpia():
    programs.clear_cache()
    yield
    programs.clear_cache()


@pytest.fixture
def servicio(monkeypatch):
    monkeypatch.setattr(settings, "bot_service_key", CLAVE)
    return {"X-Bot-Service-Key": CLAVE}


@pytest.fixture
def mundo(db, modes_config, make_artifact, monkeypatch):
    monkeypatch.setattr(settings, "bot_clarify", "on")
    monkeypatch.setattr(settings, "bot_clarify_min_similarity", 0.55)
    monkeypatch.setattr(settings, "bot_clarify_max_programs", 5)
    monkeypatch.setattr(settings, "query_context_neighbors", 0)
    with db() as session:
        session.add_all([Unit(id="u1", name="Computación"), Unit(id="u3", name="Vacía")])
        session.flush()
        session.add(Domain(id="dom-1", unit_id="u1", name="Apertura de promoción"))
        session.flush()
        session.add_all(
            Document(id=doc_id, domain_id="dom-1", filename=f"{doc_id}.txt", source_type="txt", file_hash=doc_id, status="done")
            for doc_id in TITULOS
        )
        session.commit()
    artefacto = make_artifact("Bot", units=["u1"], modes="literal", cap=1.0)
    sin_dominios = make_artifact("Bot sin dominios", units=["u3"], modes="literal", cap=1.0)
    with db() as session:
        session.add(Bot(id=str(uuid.uuid4()), name="Bot", kapso_number_id=NUMERO, artifact_id=artefacto.id))
        session.add(Bot(id=str(uuid.uuid4()), name="Bot vacío", kapso_number_id="999", artifact_id=sin_dominios.id))
        session.commit()
    return {"artefacto": artefacto}


class Pipeline:
    """Almacén, embeddings y modelo simulados. `puntajes` es {documento: puntaje} de lo que devuelve `search`."""

    def __init__(self, puntajes: dict[str, float], text="La fecha es el 5 de octubre.", fragmento="Inicio de lecciones y fechas."):
        self.store = MagicMock()
        self.store.count_chunks.return_value = 100
        self.store.search.return_value = [
            SearchResult(chunk_id=f"c-{d}", document_id=d, domain="dom-1", text=fragmento, score=s)
            for d, s in sorted(puntajes.items(), key=lambda kv: -kv[1])
        ]
        self.store.get_chunks.side_effect = self._chunks
        self.embeddings = MagicMock()
        self.embeddings.embed.return_value = [[0.1, 0.2]]
        self.llm = MagicMock()
        self.llm.answer.return_value = LLMAnswer(text=text, model="modelo", prompt_tokens=100, completion_tokens=20, cost_usd=0.0004)

    def _chunks(self, document_id, indexes):
        if indexes == [0] and document_id in TITULOS:
            return [SearchResult(chunk_id="c0", document_id=document_id, domain="dom-1", text=TITULOS[document_id], score=0.0)]
        return []

    def __enter__(self):
        self._patches = [
            patch.object(query_routes, "get_vector_store", return_value=self.store),
            patch.object(query_routes, "get_embedding_provider", return_value=self.embeddings),
            patch.object(query_routes, "get_llm_provider", MagicMock(return_value=self.llm)),
        ]
        for p in self._patches:
            p.start()
        return self

    def __exit__(self, *exc):
        for p in self._patches:
            p.stop()


def _bot(client, headers, question="¿Cuándo empiezan las lecciones?", number=NUMERO):
    return client.post("/bot/query", json={"number_id": number, "question": question}, headers=headers)


# --- Aclaración ------------------------------------------------------------------------------------------------


def test_dos_programas_sobre_el_umbral_bajo_piden_aclaracion_sin_dar_datos_ni_llamar_al_modelo(client, db, mundo, servicio):
    with Pipeline({"ciber-admision": 0.70, "ana-admision": 0.66}) as pipeline:
        cuerpo = _bot(client, servicio).json()

    assert cuerpo["no_info"] is True
    assert cuerpo["clarify"] == ["Maestría en Ciberseguridad", "Maestría en Analítica de Negocio (Business Analytics)"]
    assert cuerpo["programs"] == [] and cuerpo["sources"] == [] and cuerpo["images"] == []
    assert NO_INFO_TEXTO in cuerpo["answer"]
    pipeline.llm.answer.assert_not_called()
    assert pipeline.embeddings.embed.call_count == 1  # el mismo embedding de la pregunta, ninguno nuevo
    assert pipeline.store.search.call_count == 2  # la búsqueda de siempre y la de decisión


def test_la_consulta_de_una_aclaracion_queda_en_uso_como_sin_informacion(client, db, mundo, servicio):
    with Pipeline({"ciber-admision": 0.70, "ana-admision": 0.66}):
        _bot(client, servicio)

    with db() as session:
        registro = session.query(QueryLog).one()
    assert registro.outcome == "no_info" and registro.model is None


def test_los_programas_van_por_mejor_puntaje_y_varios_documentos_de_un_programa_cuentan_uno(client, db, mundo, servicio):
    puntajes = {"ana-admision": 0.70, "ana-presentacion": 0.69, "ciber-admision": 0.65, "ciber-plan": 0.64}
    with Pipeline(puntajes):
        cuerpo = _bot(client, servicio).json()

    assert cuerpo["clarify"] == ["Maestría en Analítica de Negocio (Business Analytics)", "Maestría en Ciberseguridad"]


@pytest.mark.parametrize(
    "puntajes",
    [
        {"ciber-admision": 0.70, "ciber-plan": 0.68},  # un solo programa
        {"ciber-admision": 0.40, "ana-admision": 0.39},  # ninguno sobre el umbral bajo
        {"suelto": 0.70},  # un documento sin programa
        {"ciber-admision": 0.70, "suelto": 0.69},  # un programa y un documento sin programa
        {},  # sin resultados
    ],
    ids=["un programa", "bajo el umbral bajo", "sin programa", "uno y uno sin programa", "sin resultados"],
)
def test_con_uno_o_ningun_programa_responde_sin_informacion_como_hoy(client, db, mundo, servicio, puntajes):
    with Pipeline(puntajes) as pipeline:
        cuerpo = _bot(client, servicio).json()

    assert cuerpo["no_info"] is True and cuerpo["clarify"] == [] and cuerpo["programs"] == []
    assert NO_INFO_TEXTO in cuerpo["answer"]
    pipeline.llm.answer.assert_not_called()


def test_con_la_aclaracion_apagada_una_respuesta_no_trae_programas_ni_lee_titulos(client, db, mundo, servicio, monkeypatch):
    monkeypatch.setattr(settings, "bot_clarify", "off")
    with Pipeline({"ana-admision": 0.95}) as pipeline:
        cuerpo = _bot(client, servicio).json()

    assert cuerpo["no_info"] is False and cuerpo["clarify"] == [] and cuerpo["programs"] == []
    pipeline.store.get_chunks.assert_not_called()


def test_una_pregunta_sin_relacion_con_puntajes_parecidos_pero_sin_evidencia_lexical_no_pide_aclaracion(client, db, mundo, servicio):
    """Calibración del 27 de octubre: "¿Cuánto cuesta la luna?" (0,803) y "¿Cuándo empiezan las lecciones?" (0,816) son
    casi iguales en puntaje con los dos programas; solo la evidencia léxica las separa."""
    with Pipeline({"ciber-admision": 0.803, "ana-admision": 0.794}) as pipeline:
        luna = _bot(client, servicio, "¿Cuánto cuesta la luna?").json()
        lecciones = _bot(client, servicio, "¿Cuándo empiezan las lecciones?").json()

    assert luna["no_info"] is True and luna["clarify"] == []
    assert len(lecciones["clarify"]) == 2
    pipeline.llm.answer.assert_not_called()


def test_sin_palabras_con_contenido_no_hay_aclaracion(client, db, mundo, servicio):
    with Pipeline({"ciber-admision": 0.70, "ana-admision": 0.66}):
        cuerpo = _bot(client, servicio, "¿Qué es esto?").json()

    assert cuerpo["no_info"] is True and cuerpo["clarify"] == []


def test_la_busqueda_de_decision_pide_mas_candidatos_que_la_consulta(client, db, mundo, servicio, monkeypatch):
    monkeypatch.setattr(settings, "bot_clarify_candidates", 40)
    with Pipeline({"ciber-admision": 0.70, "ana-admision": 0.66}) as pipeline:
        _bot(client, servicio)

    primera, decision = pipeline.store.search.call_args_list
    assert decision.kwargs["limit"] == 40 and decision.kwargs["limit"] > primera.kwargs["limit"]


@pytest.mark.parametrize("valor", ["off", "", "tal vez"])
def test_con_la_aclaracion_apagada_no_hay_busqueda_extra_ni_candidatos(client, db, mundo, servicio, monkeypatch, valor):
    monkeypatch.setattr(settings, "bot_clarify", valor)
    with Pipeline({"ciber-admision": 0.70, "ana-admision": 0.66}) as pipeline:
        cuerpo = _bot(client, servicio).json()

    assert cuerpo["no_info"] is True and cuerpo["clarify"] == []
    assert pipeline.store.search.call_count == 1
    pipeline.store.get_chunks.assert_not_called()


def test_se_listan_como_maximo_los_programas_configurados(client, db, mundo, servicio, monkeypatch):
    monkeypatch.setattr(settings, "bot_clarify_max_programs", 2)
    with Pipeline({"ciber-admision": 0.70, "ana-admision": 0.66}) as pipeline:
        pipeline.store.search.return_value.append(
            SearchResult(chunk_id="c3", document_id="x", domain="dom-1", text="t", score=0.6)
        )
        cuerpo = _bot(client, servicio).json()

    assert len(cuerpo["clarify"]) == 2


def test_el_puntaje_minimo_sale_de_la_configuracion(client, db, mundo, servicio, monkeypatch):
    monkeypatch.setattr(settings, "bot_clarify_min_similarity", 0.68)
    with Pipeline({"ciber-admision": 0.70, "ana-admision": 0.66}):
        cuerpo = _bot(client, servicio).json()

    assert cuerpo["clarify"] == []  # solo un programa llega a 0,68


def test_una_respuesta_sin_informacion_del_modelo_con_fragmentos_relevantes_no_pide_aclaracion(client, db, mundo, servicio):
    with Pipeline({"ciber-admision": 0.90, "ana-admision": 0.89}, text="SIN_INFORMACION") as pipeline:
        cuerpo = _bot(client, servicio).json()

    assert cuerpo["no_info"] is True and cuerpo["clarify"] == []
    assert pipeline.store.search.call_count == 1


# --- Respuestas ------------------------------------------------------------------------------------------------


def test_una_respuesta_con_fuentes_trae_los_programas_de_sus_documentos_sin_repetir(client, db, mundo, servicio):
    with Pipeline({"ana-admision": 0.95, "ana-presentacion": 0.90}) as pipeline:
        cuerpo = _bot(client, servicio, "¿Cuándo inician las lecciones de la maestría en analítica de negocio?").json()

    assert cuerpo["no_info"] is False and cuerpo["clarify"] == []
    assert "5 de octubre" in cuerpo["answer"]
    assert cuerpo["programs"] == ["Maestría en Analítica de Negocio (Business Analytics)"]
    assert pipeline.store.search.call_count == 1  # una respuesta no hace la búsqueda de decisión


def test_una_respuesta_que_cita_dos_programas_los_trae_a_los_dos(client, db, mundo, servicio):
    with Pipeline({"ana-admision": 0.95, "ciber-admision": 0.90}):
        cuerpo = _bot(client, servicio).json()

    assert set(cuerpo["programs"]) == {"Maestría en Ciberseguridad", "Maestría en Analítica de Negocio (Business Analytics)"}


def test_una_respuesta_con_documentos_sin_programa_trae_programs_vacio(client, db, mundo, servicio):
    with Pipeline({"suelto": 0.95}):
        cuerpo = _bot(client, servicio).json()

    assert cuerpo["no_info"] is False and cuerpo["programs"] == []


def test_un_artefacto_sin_dominios_responde_sin_informacion_con_la_forma_del_bot(client, db, mundo, servicio):
    with Pipeline({"ciber-admision": 0.70, "ana-admision": 0.66}) as pipeline:
        cuerpo = _bot(client, servicio, number="999").json()

    assert cuerpo["no_info"] is True and cuerpo["clarify"] == [] and cuerpo["programs"] == []
    pipeline.store.search.assert_not_called()


def test_los_rechazos_del_bot_no_cambian(client, db, mundo, servicio):
    assert _bot(client, servicio, number="no-existe").status_code == 404
    assert client.post("/bot/query", json={"number_id": NUMERO, "question": "x"}).status_code == 401


# --- POST /query no cambia -------------------------------------------------------------------------------------


def test_post_query_sigue_igual_sin_clarify_ni_programs_y_sin_busqueda_extra(client, db, mundo):
    artefacto = mundo["artefacto"]
    with Pipeline({"ciber-admision": 0.70, "ana-admision": 0.66}) as pipeline:
        respuesta = client.post(
            "/query", json={"domains": ["dom-1"], "question": "¿Cuándo empiezan las lecciones?"}, headers=artefacto.headers
        )

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert set(cuerpo) == {"id", "answer", "sources", "mode", "latency_ms", "no_info", "images"}
    assert cuerpo["no_info"] is True and NO_INFO_TEXTO in cuerpo["answer"]
    assert pipeline.store.search.call_count == 1  # con BOT_CLARIFY=on, /query no hace la búsqueda de decisión
    pipeline.store.get_chunks.assert_not_called()


def test_post_query_con_respuesta_tampoco_trae_los_campos_del_bot(client, db, mundo):
    artefacto = mundo["artefacto"]
    with Pipeline({"ana-admision": 0.95}):
        cuerpo = client.post(
            "/query", json={"domains": ["dom-1"], "question": "¿Cuándo?"}, headers=artefacto.headers
        ).json()

    assert "clarify" not in cuerpo and "programs" not in cuerpo and cuerpo["no_info"] is False


def test_los_titulos_se_leen_una_sola_vez_por_documento_entre_consultas(client, db, mundo, servicio):
    with Pipeline({"ciber-admision": 0.70, "ana-admision": 0.66}) as pipeline:
        _bot(client, servicio)
        lecturas = pipeline.store.get_chunks.call_count
        _bot(client, servicio)
        _bot(client, servicio)

    assert lecturas == 2  # un título por cada documento candidato
    assert pipeline.store.get_chunks.call_count == lecturas  # las consultas siguientes usan la caché


def test_una_consulta_que_responde_no_llama_a_ningun_modelo_de_mas(client, db, mundo, servicio):
    with Pipeline({"ana-admision": 0.95}) as pipeline:
        _bot(client, servicio)

    pipeline.llm.answer.assert_called_once()  # el de la respuesta, nada para decidir ni para los programas
    assert pipeline.embeddings.embed.call_count == 1


# --- Memoria de conversación (feature 014): el bot no le entrega historial al modelo -----------------------------


def test_el_bot_nunca_entrega_historial_al_modelo_aunque_su_artefacto_tenga_memoria(
    client, db, mundo, servicio
):
    from mia.storage.models import Artifact

    with db() as session:
        session.get(Artifact, mundo["artefacto"].id).context_turns = 5
        session.commit()

    with Pipeline({"ciber-admision": 0.90}) as pipeline:
        cuerpo = _bot(client, servicio).json()

    assert cuerpo["no_info"] is False and cuerpo["answer"]
    llamada = pipeline.llm.answer.call_args
    assert "history" not in llamada.kwargs
    assert pipeline.embeddings.embed.call_args.args[0] == ["¿Cuándo empiezan las lecciones?"]
