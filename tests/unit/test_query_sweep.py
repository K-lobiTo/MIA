"""Barrido de secciones en POST /query (feature 016): con QUERY_SECTION_SWEEP=on, "resume los contenidos de los cursos"
entrega al modelo la sección «Contenidos» de cada programa y no hace la búsqueda por similitud."""

from unittest.mock import MagicMock, patch

import pytest

from mia.api.routes import query as query_routes
from mia.config import settings
from mia.rag.llm import LLMAnswer
from mia.rag.sections import SWEEP_INSTRUCTIONS
from mia.storage.models import Document, Domain, QueryLog, Unit
from mia.storage.vector_store import SearchResult


@pytest.fixture
def base(db, modes_config):
    with db() as session:
        session.add(Unit(id="u1", name="Analítica"))
        session.flush()
        session.add(Domain(id="dom-1", unit_id="u1", name="Currículum", description=""))
        session.flush()
        for documento in ("curso-b", "curso-a", "acta"):
            session.add(
                Document(
                    id=documento, domain_id="dom-1", filename=f"{documento}.docx", source_type="docx",
                    file_hash=documento, status="done",
                )
            )
        session.commit()


def _fragmento(documento, indice, texto, puntaje=0.0):
    return SearchResult(f"{documento}-{indice}", documento, "dom-1", texto, puntaje, indice)


FRAGMENTOS = [
    _fragmento("curso-a", 0, "Descripción del curso A.\n4. Contenidos | Tema A1\nTema A2\n5. Metodología | Clases"),
    _fragmento("curso-b", 0, "Datos generales B."),
    _fragmento("curso-b", 1, "4 Contenidos | Tema B1\nTema B2\n5 Metodología | Clases"),
    _fragmento("acta", 0, "Se revisaron los contenidos de la maestría."),
]


class _Almacen:
    def __init__(self, fragmentos=FRAGMENTOS):
        self.fragmentos = fragmentos
        self.busquedas = 0

    def search(self, vector, domains, limit):
        self.busquedas += 1
        return []

    def scan_chunks(self, domains, text, limit):
        return [f for f in self.fragmentos if text in f.text.lower()]

    def get_chunks(self, document_id, indexes):
        return [f for f in self.fragmentos if f.document_id == document_id and f.chunk_index in indexes]

    def count_chunks(self, document_id):
        return sum(1 for f in self.fragmentos if f.document_id == document_id)


def _consultar(client, artefacto, pregunta, barrido="on", almacen=None, modo="literal"):
    embeddings = MagicMock()
    embeddings.embed.return_value = [[0.1, 0.2]]
    modelo = MagicMock()
    modelo.answer.return_value = LLMAnswer(text="Resumen de los cursos.")
    almacen = almacen or _Almacen()
    with (
        patch.multiple(
            settings, query_section_sweep=barrido, query_section_sweep_max_documents=40,
            query_section_sweep_max_chars=6000, query_hybrid_search="off", query_complete_context="off",
            query_cited_sources="off",
        ),
        patch.object(query_routes, "get_vector_store", return_value=almacen),
        patch.object(query_routes, "get_embedding_provider", return_value=embeddings),
        patch.object(query_routes, "get_llm_provider", return_value=modelo),
    ):
        respuesta = client.post(
            "/query", json={"domains": ["dom-1"], "question": pregunta, "mode": modo}, headers=artefacto.headers
        )
    return respuesta, modelo, almacen, embeddings


def test_resumen_de_los_cursos_entrega_la_seccion_de_cada_programa(client, base, make_artifact):
    artefacto = make_artifact(units=["u1"])
    respuesta, modelo, almacen, embeddings = _consultar(client, artefacto, "Resume el contenido de todos los cursos")

    assert respuesta.status_code == 200
    assert respuesta.json()["answer"] == "Resumen de los cursos."
    contexto = modelo.answer.call_args.args[1]
    # En orden de documento, solo la fila Contenidos de los dos programas, y no el acta que repite la palabra.
    assert [c.document for c in contexto] == ["curso-a.docx", "curso-b.docx"]
    assert contexto[0].excerpt == "4. Contenidos | Tema A1\nTema A2"
    assert contexto[1].excerpt == "4 Contenidos | Tema B1\nTema B2"
    assert SWEEP_INSTRUCTIONS in modelo.answer.call_args.kwargs["instructions"]
    assert [s["document"] for s in respuesta.json()["sources"]] == ["curso-a.docx", "curso-b.docx"]
    # Sin búsqueda por similitud ni embedding de la pregunta.
    assert almacen.busquedas == 0
    embeddings.embed.assert_not_called()


def test_deja_una_nota_en_el_registro_de_uso(client, base, make_artifact, db):
    artefacto = make_artifact(units=["u1"])
    _consultar(client, artefacto, "Resume el contenido de todos los cursos")
    with db() as session:
        registro = session.query(QueryLog).one()
        assert registro.outcome == "answered"
        assert "Barrido de secciones: 2 documentos" in registro.reject_reason


def test_apagado_la_consulta_es_la_de_siempre(client, base, make_artifact):
    artefacto = make_artifact(units=["u1"])
    respuesta, modelo, almacen, embeddings = _consultar(
        client, artefacto, "Resume el contenido de todos los cursos", barrido="off"
    )
    assert almacen.busquedas == 1
    embeddings.embed.assert_called_once()
    modelo.answer.assert_not_called()  # el almacén simulado no devuelve resultados
    assert respuesta.json()["no_info"] is True


def test_una_pregunta_de_otro_tipo_no_hace_barrido(client, base, make_artifact):
    artefacto = make_artifact(units=["u1"])
    _, _, almacen, _ = _consultar(client, artefacto, "¿Cuáles son los contenidos del curso A?")
    assert almacen.busquedas == 1


def test_con_menos_de_dos_documentos_sigue_la_busqueda_de_siempre(client, base, make_artifact):
    artefacto = make_artifact(units=["u1"])
    almacen = _Almacen(FRAGMENTOS[:1])
    _, _, almacen, _ = _consultar(client, artefacto, "Resume el contenido de todos los cursos", almacen=almacen)
    assert almacen.busquedas == 1
