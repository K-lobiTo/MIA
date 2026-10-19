from unittest.mock import MagicMock, patch

import pytest

from mia.api.routes import query as query_routes
from mia.config import settings
from mia.rag import citations
from mia.rag.llm import LLMAnswer
from mia.storage.models import Document, Domain, QueryLog, Unit
from mia.storage.vector_store import SearchResult


@pytest.fixture
def base(db, modes_config):
    with db() as session:
        session.add(Unit(id="u1", name="Computación"))
        session.flush()
        session.add(Domain(id="dom-1", unit_id="u1", name="Memoria del Consejo", description=""))
        session.flush()
        for numero in (1, 2, 3):
            session.add(
                Document(
                    id=f"doc-{numero}", domain_id="dom-1", filename=f"acta-{numero}.txt", source_type="txt",
                    file_hash=f"h{numero}", status="done",
                )
            )
        session.commit()


PASAJES = [
    SearchResult(chunk_id=f"c{n}", document_id=f"doc-{n}", domain="dom-1", text=f"Texto del acta {n}.", score=0.9 - n / 100)
    for n in (1, 2, 3)
]


def _consultar(client, artefacto, respuesta_del_modelo, modo="literal", cited="on"):
    """Hace una consulta con el almacén, los embeddings y el modelo simulados. Devuelve (respuesta, modelo)."""
    almacen = MagicMock()
    almacen.count_chunks.return_value = 100  # documentos largos: no se pasan completos
    almacen.search.return_value = PASAJES
    almacen.get_chunks.return_value = []
    embeddings = MagicMock()
    embeddings.embed.return_value = [[0.1, 0.2]]
    modelo = MagicMock()
    modelo.answer.return_value = LLMAnswer(text=respuesta_del_modelo)
    with (
        patch.object(settings, "query_cited_sources", cited),
        patch.object(settings, "query_context_neighbors", 0),
        patch.object(query_routes, "get_vector_store", return_value=almacen),
        patch.object(query_routes, "get_embedding_provider", return_value=embeddings),
        patch.object(query_routes, "get_llm_provider", return_value=modelo),
    ):
        respuesta = client.post(
            "/query",
            json={"domains": ["dom-1"], "question": "¿Qué se aprobó?", "mode": modo},
            headers=artefacto.headers,
        )
    return respuesta, modelo


def _documentos(respuesta):
    return [fuente["document"] for fuente in respuesta.json()["sources"]]


@pytest.mark.parametrize("modo", ["literal", "razonamiento"])
def test_con_la_opcion_encendida_solo_se_listan_las_fuentes_citadas(client, base, make_artifact, modo):
    artefacto = make_artifact(units=["u1"], modes="literal,razonamiento")
    respuesta, modelo = _consultar(client, artefacto, "Dato.\nFUENTES: 2", modo=modo)

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["answer"] == "Dato."
    assert _documentos(respuesta) == ["acta-2.txt"]
    assert cuerpo["sources"][0]["excerpt"] == "Texto del acta 2."
    # El modelo recibe los pasajes numerados y las instrucciones del modo más el párrafo de citas.
    contexto = modelo.answer.call_args.args[1]
    assert [c.reference for c in contexto] == [1, 2, 3]
    instrucciones = modelo.answer.call_args.kwargs["instructions"]
    assert instrucciones.endswith(citations.CITATION_INSTRUCTIONS)
    assert len(instrucciones) > len(citations.CITATION_INSTRUCTIONS)


def test_el_registro_guarda_solo_los_documentos_citados(client, db, base, make_artifact):
    artefacto = make_artifact(units=["u1"])
    respuesta, _ = _consultar(client, artefacto, "Dato.\nFUENTES: 1, 3")

    with db() as session:
        consulta = session.get(QueryLog, respuesta.json()["id"])
        assert consulta.outcome == "answered"
        assert [s["document"] for s in __import__("json").loads(consulta.sources)] == ["acta-1.txt", "acta-3.txt"]


def test_el_contexto_entregado_es_el_mismo_con_la_opcion_encendida_y_apagada(client, base, make_artifact):
    """FR-007: la opción no cambia qué pasajes se entregan, ni su orden ni su contenido (solo `reference`)."""
    artefacto = make_artifact(units=["u1"])
    _, apagada = _consultar(client, artefacto, "Dato.", cited="off")
    _, encendida = _consultar(client, artefacto, "Dato.\nFUENTES: 1", cited="on")

    def lo_entregado(modelo):
        return [(c.domain, c.document, c.excerpt) for c in modelo.answer.call_args.args[1]]

    assert lo_entregado(apagada) == lo_entregado(encendida)
    assert len(lo_entregado(apagada)) == 3


NOTA_REGLA_DE_SEGURIDAD = "Fuentes: sin citas utilizables, se mostraron todas"


def _registro(db, respuesta):
    with db() as session:
        return session.get(QueryLog, respuesta.json()["id"])


@pytest.mark.parametrize(
    "texto_del_modelo",
    ["Dato sin citas.", "Dato.\nFUENTES: ninguna", "Dato.\nFUENTES: 7, 9", "Dato cortado a la mitad y sin"],
)
def test_sin_citas_utilizables_se_muestran_todas_las_fuentes_y_se_anota(client, db, base, make_artifact, texto_del_modelo):
    artefacto = make_artifact(units=["u1"])
    respuesta, _ = _consultar(client, artefacto, texto_del_modelo)

    assert respuesta.status_code == 200
    assert _documentos(respuesta) == ["acta-1.txt", "acta-2.txt", "acta-3.txt"]
    assert "FUENTES" not in respuesta.json()["answer"]
    consulta = _registro(db, respuesta)
    assert consulta.outcome == "answered"
    assert consulta.reject_reason == NOTA_REGLA_DE_SEGURIDAD


def test_citas_mezcladas_listan_solo_las_validas_sin_anotar(client, db, base, make_artifact):
    artefacto = make_artifact(units=["u1"])
    respuesta, _ = _consultar(client, artefacto, "Dato.\nFUENTES: 3, 9, 3")

    assert _documentos(respuesta) == ["acta-3.txt"]
    assert _registro(db, respuesta).reject_reason is None


def test_una_cita_valida_no_deja_nota(client, db, base, make_artifact):
    artefacto = make_artifact(units=["u1"])
    respuesta, _ = _consultar(client, artefacto, "Dato.\nFUENTES: 1")
    assert _registro(db, respuesta).reject_reason is None


@pytest.mark.parametrize("texto_del_modelo", ["SIN_INFORMACION", " SIN_INFORMACION.\n", "SIN_INFORMACION\nFUENTES: 1", "SIN_INFORMACION.\n\n**FUENTES:** 2"])
def test_sin_informacion_con_o_sin_linea_de_citas_no_lista_fuentes(client, db, base, make_artifact, texto_del_modelo):
    artefacto = make_artifact(units=["u1"])
    respuesta, _ = _consultar(client, artefacto, texto_del_modelo)

    cuerpo = respuesta.json()
    assert cuerpo["no_info"] is True and cuerpo["sources"] == []
    consulta = _registro(db, respuesta)
    assert consulta.outcome == "no_info" and consulta.reject_reason is None


def test_una_respuesta_con_contenido_nunca_queda_sin_fuentes(client, base, make_artifact):
    artefacto = make_artifact(units=["u1"])
    for texto in ("Dato.", "Dato.\nFUENTES: ninguna", "Dato.\nFUENTES: 1", "Dato.\nFUENTES: 50", "**Dato**\n\nFUENTES:"):
        respuesta, _ = _consultar(client, artefacto, texto)
        assert respuesta.json()["no_info"] is False
        assert len(respuesta.json()["sources"]) >= 1, texto


# --- Opción apagada: idéntico al comportamiento anterior --------------------------------


def test_apagada_no_cambia_nada(client, db, base, make_artifact):
    from mia.rag.llm import RAG_SYSTEM_PROMPT

    artefacto = make_artifact(units=["u1"])
    # Valor por defecto de la configuración (sin forzarlo): apagada.
    assert settings.query_cited_sources == "off"
    texto = "Dato.\nFUENTES: 1"
    respuesta, modelo = _consultar(client, artefacto, texto, cited=settings.query_cited_sources)

    contexto = modelo.answer.call_args.args[1]
    assert [c.reference for c in contexto] == [None, None, None]
    assert modelo.answer.call_args.kwargs["instructions"] == RAG_SYSTEM_PROMPT
    cuerpo = respuesta.json()
    assert cuerpo["answer"] == texto  # no se interpreta nada: queda como llegó
    assert _documentos(respuesta) == ["acta-1.txt", "acta-2.txt", "acta-3.txt"]
    assert _registro(db, respuesta).reject_reason is None


def test_apagada_en_razonamiento_usa_las_instrucciones_del_modo(client, base, make_artifact):
    from mia.rag.llm import REASONING_SYSTEM_PROMPT

    artefacto = make_artifact(units=["u1"], modes="literal,razonamiento")
    _, modelo = _consultar(client, artefacto, "Dato.", modo="razonamiento", cited="off")
    assert modelo.answer.call_args.kwargs["instructions"] == REASONING_SYSTEM_PROMPT


def test_valor_invalido_se_comporta_como_apagado_y_avisa(client, base, make_artifact, caplog):
    import logging

    citations._INVALID_VALUES_WARNED.clear()
    artefacto = make_artifact(units=["u1"])
    with caplog.at_level(logging.WARNING, logger=citations.__name__):
        respuesta, modelo = _consultar(client, artefacto, "Dato.\nFUENTES: 1", cited="quizas")

    assert respuesta.status_code == 200
    assert [c.reference for c in modelo.answer.call_args.args[1]] == [None, None, None]
    assert len(_documentos(respuesta)) == 3
    assert any("QUERY_CITED_SOURCES" in r.getMessage() for r in caplog.records)
    citations._INVALID_VALUES_WARNED.clear()


@pytest.mark.parametrize("valor", ["ON", " true ", "1", "yes"])
def test_valores_de_encendido_con_otra_forma(client, base, make_artifact, valor):
    artefacto = make_artifact(units=["u1"])
    respuesta, modelo = _consultar(client, artefacto, "Dato.\nFUENTES: 2", cited=valor)
    assert _documentos(respuesta) == ["acta-2.txt"]
    assert [c.reference for c in modelo.answer.call_args.args[1]] == [1, 2, 3]


def test_la_opcion_se_lee_en_cada_consulta(client, base, make_artifact):
    artefacto = make_artifact(units=["u1"])
    primera, _ = _consultar(client, artefacto, "Dato.\nFUENTES: 2", cited="on")
    segunda, _ = _consultar(client, artefacto, "Dato.\nFUENTES: 2", cited="off")
    assert len(_documentos(primera)) == 1
    assert len(_documentos(segunda)) == 3
