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


# --- US2: respuestas cortadas ------------------------------------------------------------------


def _registro(db, respuesta):
    from mia.storage.models import QueryLog

    with db() as session:
        return session.get(QueryLog, respuesta.json()["id"])


def _respuesta(texto, motivo="stop", costo=0.01):
    return LLMAnswer(text=texto, finish_reason=motivo, cost_usd=costo, prompt_tokens=100, completion_tokens=20)


def test_motivo_normal_o_desconocido_no_reintenta(client, base, make_artifact):
    artefacto = make_artifact(units=["u1"])
    for motivo in ("stop", None):
        respuesta, modelo = _consultar(
            client, artefacto, [_respuesta("Lista completa.", motivo)], query_retry_cut_answers="on"
        )
        assert modelo.answer.call_count == 1
        assert respuesta.json()["answer"] == "Lista completa."


def test_corte_con_reintento_exitoso_entrega_el_segundo_y_suma_los_costos(client, db, base, make_artifact):
    artefacto = make_artifact(units=["u1"])
    respuesta, modelo = _consultar(
        client, artefacto,
        [_respuesta("Lista cortada a la mi", "length", 0.01), _respuesta("Lista completa.", "stop", 0.02)],
        query_retry_cut_answers="on",
    )
    assert modelo.answer.call_count == 2
    assert respuesta.json()["answer"] == "Lista completa."
    registro = _registro(db, respuesta)
    assert registro.reject_reason == completeness.NOTE_RETRIED and registro.outcome == "answered"
    assert float(registro.cost_usd) == pytest.approx(0.03)
    assert registro.prompt_tokens == 200 and registro.completion_tokens == 40


def test_dos_cortes_seguidos_entregan_el_texto_mas_largo_con_aviso(client, db, base, make_artifact):
    artefacto = make_artifact(units=["u1"])
    respuesta, modelo = _consultar(
        client, artefacto,
        [_respuesta("Corta", "length", 0.01), _respuesta("Un poco más larga pero cortada", "length", 0.01)],
        query_retry_cut_answers="on",
    )
    texto = respuesta.json()["answer"]
    assert modelo.answer.call_count == 2
    assert texto.startswith("Un poco más larga pero cortada") and texto.endswith(completeness.CUT_NOTICE)
    registro = _registro(db, respuesta)
    assert registro.reject_reason == completeness.NOTE_NOTICE
    assert float(registro.cost_usd) == pytest.approx(0.02)


def test_sin_informacion_con_motivo_anormal_no_se_reintenta(client, db, base, make_artifact):
    artefacto = make_artifact(units=["u1"])
    respuesta, modelo = _consultar(
        client, artefacto, [_respuesta("SIN_INFORMACION", "length")], query_retry_cut_answers="on"
    )
    assert modelo.answer.call_count == 1
    cuerpo = respuesta.json()
    assert cuerpo["no_info"] is True and cuerpo["sources"] == []
    assert _registro(db, respuesta).reject_reason is None


def test_un_tope_de_gasto_alcanzado_con_el_primer_intento_impide_reintentar(client, db, base, make_artifact):
    artefacto = make_artifact(units=["u1"], cap=0.005)  # el primer intento (0,01) ya lo supera
    respuesta, modelo = _consultar(
        client, artefacto, [_respuesta("Cortada", "length", 0.01)], query_retry_cut_answers="on"
    )
    assert modelo.answer.call_count == 1
    assert respuesta.json()["answer"].endswith(completeness.CUT_NOTICE)
    assert _registro(db, respuesta).reject_reason == completeness.NOTE_NOTICE


def test_si_el_reintento_falla_se_entrega_el_primer_texto_con_aviso(client, db, base, make_artifact):
    artefacto = make_artifact(units=["u1"])
    respuesta, modelo = _consultar(
        client, artefacto, [_respuesta("Cortada a la mi", "length"), RuntimeError("proveedor caído")],
        query_retry_cut_answers="on",
    )
    assert respuesta.status_code == 200
    assert modelo.answer.call_count == 2
    assert respuesta.json()["answer"].startswith("Cortada a la mi")
    assert respuesta.json()["answer"].endswith(completeness.CUT_NOTICE)
    assert _registro(db, respuesta).reject_reason == completeness.NOTE_NOTICE


def test_con_las_citas_de_la_006_las_notas_se_unen_y_el_aviso_va_despues_de_quitar_la_linea(
    client, db, base, make_artifact
):
    artefacto = make_artifact(units=["u1"])
    # Reintento exitoso, pero el segundo texto no cita nada válido: rige la regla de seguridad de las citas.
    respuesta, _ = _consultar(
        client, artefacto,
        [_respuesta("Cortada\nFUENTES: 9", "length"), _respuesta("Completa.\nFUENTES: 9", "stop")],
        query_retry_cut_answers="on", query_cited_sources="on",
    )
    assert respuesta.json()["answer"] == "Completa."
    assert _registro(db, respuesta).reject_reason == f"{completeness.NOTE_RETRIED}; {citations.SAFETY_RULE_NOTE}"

    # Dos cortes: la línea de fuentes se quita y el aviso queda como última línea.
    respuesta, _ = _consultar(
        client, artefacto,
        [_respuesta("Cortada\nFUENTES: 1", "length"), _respuesta("Cortada también\nFUENTES: 1", "length")],
        query_retry_cut_answers="on", query_cited_sources="on",
    )
    texto = respuesta.json()["answer"]
    assert "FUENTES" not in texto and texto.endswith(completeness.CUT_NOTICE)


def test_con_la_opcion_apagada_no_se_reintenta_pero_si_se_registra_el_motivo_de_fin(
    client, base, make_artifact, caplog
):
    import logging

    artefacto = make_artifact(units=["u1"])
    with caplog.at_level(logging.INFO, logger="mia.api.routes.query"):
        respuesta, modelo = _consultar(client, artefacto, [_respuesta("Cortada", "length")])
    assert modelo.answer.call_count == 1
    assert respuesta.json()["answer"] == "Cortada"
    assert any("length" in r.getMessage() and "literal" in r.getMessage() for r in caplog.records)
    with caplog.at_level(logging.INFO, logger="mia.api.routes.query"):
        caplog.clear()
        _consultar(client, artefacto, [_respuesta("Completa.", "stop")])
    assert any("stop" in r.getMessage() for r in caplog.records)


# --- US3: independencia y apagado ---------------------------------------------------------------


def test_con_ambas_opciones_apagadas_todo_es_como_antes(client, db, base, make_artifact):
    from mia.rag.llm import RAG_SYSTEM_PROMPT

    artefacto = make_artifact(units=["u1"])
    assert settings.query_complete_context == "off" and settings.query_retry_cut_answers == "off"
    texto = "Lista que termina con la línea\nFUENTES: 1"
    respuesta, modelo = _consultar(
        client, artefacto, [_respuesta(texto, "length")],
        query_complete_context=settings.query_complete_context,
        query_retry_cut_answers=settings.query_retry_cut_answers,
    )
    contexto = _contexto_entregado(modelo)
    assert modelo.answer.call_count == 1  # sin reintento aunque el motivo sea "length"
    assert all(completeness.CONTINUES_MARKER not in c.excerpt for c in contexto)
    assert [c.reference for c in contexto] == [None] * len(contexto)
    # Contexto de siempre: el fragmento relevante con un vecino a cada lado (3), o completo si es corto (doc-1 15 > 12).
    por_doc = _por_documento(contexto)
    assert por_doc["curso-1.pdf"].excerpt.count("doc-1:") == 3
    assert modelo.answer.call_args.kwargs["instructions"] == RAG_SYSTEM_PROMPT
    assert respuesta.json()["answer"] == texto  # intacto
    assert len(respuesta.json()["sources"]) == len(contexto)
    assert _registro(db, respuesta).reject_reason is None


def test_solo_el_contexto_completo_no_reintenta_aunque_el_motivo_sea_length(client, base, make_artifact):
    artefacto = make_artifact(units=["u1"])
    respuesta, modelo = _consultar(
        client, artefacto, [_respuesta("Cortada", "length")], query_complete_context="on"
    )
    assert modelo.answer.call_count == 1
    assert completeness.COMPLETENESS_INSTRUCTIONS in modelo.answer.call_args.kwargs["instructions"]
    assert "Aviso" not in respuesta.json()["answer"]


def test_solo_el_reintento_deja_el_contexto_de_siempre(client, base, make_artifact):
    from mia.rag.llm import RAG_SYSTEM_PROMPT

    artefacto = make_artifact(units=["u1"])
    respuesta, modelo = _consultar(
        client, artefacto, [_respuesta("Cortada", "length"), _respuesta("Completa.", "stop")],
        query_retry_cut_answers="on",
    )
    assert modelo.answer.call_count == 2
    assert modelo.answer.call_args.kwargs["instructions"] == RAG_SYSTEM_PROMPT
    assert all(completeness.CONTINUES_MARKER not in c.excerpt for c in _contexto_entregado(modelo))
    assert respuesta.json()["answer"] == "Completa."


def test_un_valor_invalido_se_comporta_como_apagado_y_avisa_una_sola_vez(client, base, make_artifact, caplog):
    import logging

    completeness._INVALID_VALUES_WARNED.clear()
    artefacto = make_artifact(units=["u1"])
    with caplog.at_level(logging.WARNING, logger=completeness.__name__):
        for _ in range(2):
            respuesta, modelo = _consultar(
                client, artefacto, [_respuesta("Cortada", "length")],
                query_complete_context="quizas", query_retry_cut_answers="tal vez",
            )
            assert respuesta.status_code == 200 and modelo.answer.call_count == 1
            assert all(completeness.CONTINUES_MARKER not in c.excerpt for c in _contexto_entregado(modelo))
    avisos = [r.getMessage() for r in caplog.records]
    assert sum("QUERY_COMPLETE_CONTEXT" in a for a in avisos) == 1
    assert sum("QUERY_RETRY_CUT_ANSWERS" in a for a in avisos) == 1
    completeness._INVALID_VALUES_WARNED.clear()


@pytest.mark.parametrize("valor", ["ON", " true ", "1", "yes"])
def test_los_valores_de_encendido_con_otra_forma(client, base, make_artifact, valor):
    artefacto = make_artifact(units=["u1"])
    _, modelo = _consultar(
        client, artefacto, [_respuesta("Cortada", "length"), _respuesta("Completa.")],
        query_complete_context=valor, query_retry_cut_answers=valor,
    )
    assert modelo.answer.call_count == 2
    assert completeness.COMPLETENESS_INSTRUCTIONS in modelo.answer.call_args.kwargs["instructions"]


def test_las_opciones_se_leen_en_cada_consulta(client, base, make_artifact):
    artefacto = make_artifact(units=["u1"])
    _, primera = _consultar(client, artefacto, [_respuesta("Ok.")], query_complete_context="on")
    _, segunda = _consultar(client, artefacto, [_respuesta("Ok.")], query_complete_context="off")
    assert completeness.COMPLETENESS_INSTRUCTIONS in primera.answer.call_args.kwargs["instructions"]
    assert completeness.COMPLETENESS_INSTRUCTIONS not in segunda.answer.call_args.kwargs["instructions"]
