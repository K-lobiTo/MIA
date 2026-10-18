from unittest.mock import MagicMock, patch

import pytest

from mia.api.routes import query as query_routes
from mia.config import settings
from mia.rag import citations, completeness
from mia.rag.llm import LLMAnswer
from mia.storage.models import Document, Domain, Unit
from mia.storage.vector_store import SearchResult


@pytest.fixture
def base(db, modes_config):
    with db() as session:
        session.add(Unit(id="u1", name="Computación"))
        session.flush()
        session.add(Domain(id="dom-1", unit_id="u1", name="Currículum", description=""))
        session.flush()
        for numero in (1, 2, 3):
            session.add(
                Document(
                    id=f"doc-{numero}", domain_id="dom-1", filename=f"curso-{numero}.pdf", source_type="pdf",
                    file_hash=f"h{numero}", status="done",
                )
            )
        session.commit()


# --- Ayudas ---------------------------------------------------------------------------------


class _AlmacenDeRuta:
    """Almacén simulado: documentos de `n` fragmentos con texto `<documento>:<índice>`."""

    def __init__(self, tamanos, resultados):
        self.tamanos = tamanos
        self.resultados = resultados

    def search(self, vector, domains, limit):
        return self.resultados

    def count_chunks(self, document_id):
        return self.tamanos[document_id]

    def get_chunks(self, document_id, indexes):
        return [
            SearchResult(
                chunk_id=f"{document_id}-{i}", document_id=document_id, domain="dom-1",
                text=f"{document_id}:{i}".ljust(100, "."), score=0.0, chunk_index=i,
            )
            for i in indexes
            if 0 <= i < self.tamanos[document_id]
        ]


def _resultado(documento, indice, puntaje):
    return SearchResult(
        chunk_id=f"{documento}-{indice}", document_id=documento, domain="dom-1",
        text=f"{documento}:{indice}".ljust(100, "."), score=puntaje, chunk_index=indice,
    )


# doc-1: 15 fragmentos (cabe completo); doc-2: 60 fragmentos (largo); doc-3: 100 fragmentos (largo, secundario).
TAMANOS = {"doc-1": 15, "doc-2": 60, "doc-3": 100}
RESULTADOS = [_resultado("doc-1", 5, 0.95), _resultado("doc-2", 20, 0.90), _resultado("doc-3", 50, 0.85)]


def _consultar(client, artefacto, respuestas, modo="literal", resultados=None, **opciones):
    """Consulta con el almacén, los embeddings y el modelo simulados. `respuestas` es una lista de
    `LLMAnswer` (una por llamada al modelo). Devuelve (respuesta HTTP, modelo simulado)."""
    embeddings = MagicMock()
    embeddings.embed.return_value = [[0.1, 0.2]]
    modelo = MagicMock()
    modelo.answer.side_effect = list(respuestas)
    valores = {"query_complete_context": "off", "query_retry_cut_answers": "off", "query_cited_sources": "off",
               "query_context_neighbors": 1, "query_full_document_max_chunks": 12}
    valores.update(opciones)
    with (
        patch.multiple(settings, **valores),
        patch.object(query_routes, "get_vector_store", return_value=_AlmacenDeRuta(TAMANOS, resultados or RESULTADOS)),
        patch.object(query_routes, "get_embedding_provider", return_value=embeddings),
        patch.object(query_routes, "get_llm_provider", return_value=modelo),
    ):
        respuesta = client.post(
            "/query",
            json={"domains": ["dom-1"], "question": "¿Cuáles son los contenidos del curso?", "mode": modo},
            headers=artefacto.headers,
        )
    return respuesta, modelo


def _contexto_entregado(modelo, llamada=0):
    return modelo.answer.call_args_list[llamada].args[1]


def _por_documento(contexto):
    return {c.document: c for c in contexto}


# --- US1: contexto completo ------------------------------------------------------------------


def test_con_contexto_completo_el_documento_principal_llega_entero(client, base, make_artifact):
    artefacto = make_artifact(units=["u1"])
    respuesta, modelo = _consultar(client, artefacto, [LLMAnswer(text="Lista.")], query_complete_context="on")

    assert respuesta.status_code == 200
    contexto = _por_documento(_contexto_entregado(modelo))
    principal = contexto["curso-1.pdf"]
    # Los 15 fragmentos (hay un salto de línea entre uno y otro) y, al llegar al final, sin marca.
    assert principal.excerpt.count("doc-1:") == 15 and "doc-1:14" in principal.excerpt
    assert completeness.CONTINUES_MARKER not in principal.excerpt


def test_el_pasaje_que_no_llega_al_final_lleva_la_marca_solo_en_el_contexto(client, base, make_artifact):
    artefacto = make_artifact(units=["u1"])
    respuesta, modelo = _consultar(client, artefacto, [LLMAnswer(text="Lista.")], query_complete_context="on")

    contexto = _por_documento(_contexto_entregado(modelo))
    assert contexto["curso-2.pdf"].excerpt.endswith(completeness.CONTINUES_MARKER)
    assert contexto["curso-3.pdf"].excerpt.endswith(completeness.CONTINUES_MARKER)
    # La persona ve el texto original en las fuentes, sin la marca.
    for fuente in respuesta.json()["sources"]:
        assert completeness.CONTINUES_MARKER not in fuente["excerpt"]


def test_el_documento_principal_largo_avanza_hacia_adelante_y_los_demas_no(client, base, make_artifact):
    artefacto = make_artifact(units=["u1"])
    # El de mejor resultado es el largo doc-2 (60 fragmentos); doc-3 (100) es secundario.
    resultados = [_resultado("doc-2", 20, 0.99), _resultado("doc-3", 50, 0.85)]
    _, modelo = _consultar(
        client, artefacto, [LLMAnswer(text="Lista.")], resultados=resultados, query_complete_context="on"
    )
    contexto = _por_documento(_contexto_entregado(modelo))
    principal = contexto["curso-2.pdf"].excerpt
    assert all(f"doc-2:{i}" in principal for i in range(19, 25))
    assert "doc-2:25" not in principal and "doc-2:18" not in principal
    # El secundario sigue con un vecino a cada lado.
    assert contexto["curso-3.pdf"].excerpt.count("doc-3:") == 3


def test_las_instrucciones_llevan_la_completitud_antes_que_las_citas(client, base, make_artifact):
    from mia.rag.llm import RAG_SYSTEM_PROMPT

    artefacto = make_artifact(units=["u1"])
    _, modelo = _consultar(client, artefacto, [LLMAnswer(text="Lista.")], query_complete_context="on")
    instrucciones = modelo.answer.call_args.kwargs["instructions"]
    assert instrucciones == f"{RAG_SYSTEM_PROMPT}\n\n{completeness.COMPLETENESS_INSTRUCTIONS}"

    _, modelo = _consultar(
        client, artefacto, [LLMAnswer(text="Lista.\nFUENTES: 1")], query_complete_context="on", query_cited_sources="on"
    )
    instrucciones = modelo.answer.call_args.kwargs["instructions"]
    assert instrucciones.endswith(f"{completeness.COMPLETENESS_INSTRUCTIONS}\n\n{citations.CITATION_INSTRUCTIONS}")


def test_el_tope_de_contexto_descarta_secundarios_y_conserva_el_principal(client, base, make_artifact):
    artefacto = make_artifact(units=["u1"])
    _, modelo = _consultar(
        client, artefacto, [LLMAnswer(text="Lista.")], query_complete_context="on", query_context_max_chars=1600
    )
    documentos = {c.document for c in _contexto_entregado(modelo)}
    assert "curso-1.pdf" in documentos and "curso-3.pdf" not in documentos


def test_con_las_citas_de_la_006_la_numeracion_usa_los_pasajes_finales(client, base, make_artifact):
    artefacto = make_artifact(units=["u1"])
    respuesta, modelo = _consultar(
        client, artefacto, [LLMAnswer(text="Lista.\nFUENTES: 2")],
        query_complete_context="on", query_cited_sources="on", query_context_max_chars=1900,
    )
    contexto = _contexto_entregado(modelo)
    # El tope dejó fuera a doc-3: se numeran solo los pasajes que de verdad se entregan.
    assert [c.document for c in contexto] == ["curso-1.pdf", "curso-2.pdf"]
    assert [c.reference for c in contexto] == [1, 2]
    assert [f["document"] for f in respuesta.json()["sources"]] == ["curso-2.pdf"]
