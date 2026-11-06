"""Barrido de secciones (feature 016): detección de la pregunta, recorte de la fila «Contenidos» y lectura por
documento con un almacén simulado. Sin red."""

import pytest

from mia.ingestion.chunker import chunk_text
from mia.rag.sections import (
    SWEEP_INSTRUCTIONS,
    has_contents_heading,
    section_from,
    section_sweep_enabled,
    sweep_sections,
    wants_course_contents,
)
from mia.storage.vector_store import SearchResult


@pytest.mark.parametrize(
    "pregunta",
    [
        "Resuma el contenido de la materia de los 14 cursos",
        "Quisiera que me des un resumen de los cursos para darme una idea lo que puedo aprender?",
        "¿Cuáles son los contenidos de todos los cursos?",
        "Resumen de los temas de las materias de la maestría",
        "¿Qué se ve en los cursos?",
    ],
)
def test_detecta_preguntas_de_resumen_de_los_cursos(pregunta):
    assert wants_course_contents(pregunta)


@pytest.mark.parametrize(
    "pregunta",
    [
        "¿Cuáles son los contenidos del curso Pronósticos para Negocios?",
        "¿Cuántos créditos tienen los cursos?",
        "Resume los contenidos de los cursos y sus requisitos",
        "¿Cuántos cursos son?",
        "¿Qué dijo Ronald Alvarado sobre becar estudiantes?",
        "Resume el acta de la sesión 03-2026",
    ],
)
def test_no_detecta_otras_preguntas(pregunta):
    assert not wants_course_contents(pregunta)


def test_interruptor(caplog):
    assert section_sweep_enabled("on") and not section_sweep_enabled("off")
    assert not section_sweep_enabled("quizas")


@pytest.mark.parametrize(
    "texto,esperado",
    [
        ("3. Objetivos | x\n4. Contenidos | 1. Introducción", True),
        ("4 Contenidos | Unidad I", True),
        ("Contenidos | 1. Pre-procesado", True),
        ("8.Cronograma | Semana | Contenidos\n1 | Unidad 1", False),
        ("Los contenidos del programa se revisan cada año.", False),
    ],
)
def test_reconoce_la_fila_de_contenidos(texto, esperado):
    assert has_contents_heading(texto) is esperado


def test_la_seccion_termina_en_la_fila_siguiente():
    texto = "2. Descripción | algo\n4. Contenidos | 1. Series\n1.1 Componentes\n5. Reseña de otros abordajes\n5. Metodología de enseñanza | Lecciones"
    assert section_from(texto, 6000) == "4. Contenidos | 1. Series\n1.1 Componentes\n5. Reseña de otros abordajes"


def test_la_seccion_se_acota_y_sin_encabezado_es_nula():
    assert len(section_from("Contenidos | " + "x" * 500, 100)) == 100
    assert section_from("nada", 100) is None


class _Almacen:
    def __init__(self, documentos, dominio="dom-1"):
        self.chunks = [
            SearchResult(f"{doc}-{i}", doc, dominio, texto, 0.0, i)
            for doc, contenido in documentos.items()
            for i, texto in enumerate(chunk_text(contenido))
        ]
        self.falla = False

    def scan_chunks(self, domains, text, limit):
        if self.falla:
            raise RuntimeError("Qdrant no responde")
        return [c for c in self.chunks if text in c.text.lower()][:limit]

    def get_chunks(self, document_id, indexes):
        return [c for c in self.chunks if c.document_id == document_id and c.chunk_index in indexes]


def _programa(nombre, temas):
    relleno = f"Programa del curso {nombre}. " + "Descripción general del curso. " * 40
    return f"{relleno}\n4. Contenidos | " + "\n".join(temas) + "\n5. Metodología de enseñanza | Lecciones magistrales\n" + "Bibliografía. " * 80


def test_toma_la_seccion_de_cada_documento_que_la_tiene():
    almacen = _Almacen(
        {
            "a": _programa("A", [f"Tema A{i}" for i in range(60)]),  # la sección cruza varios fragmentos
            "b": _programa("B", ["Tema B1", "Tema B2"]),
            "acta": "Acta de la sesión. " * 100 + "Se discutieron los contenidos del plan.",
        }
    )
    pasajes = {p.document_id: p for p in sweep_sections(almacen, ["dom-1"], 40, 6000)}
    assert set(pasajes) == {"a", "b"}
    assert pasajes["a"].text.startswith("4. Contenidos | Tema A0") and "Tema A59" in pasajes["a"].text
    assert "Metodología" not in pasajes["a"].text and "Bibliografía" not in pasajes["a"].text
    assert pasajes["b"].text == "4. Contenidos | Tema B1\nTema B2"
    assert pasajes["b"].domain == "dom-1" and not pasajes["b"].continues


def test_respeta_el_maximo_de_documentos_y_de_caracteres():
    almacen = _Almacen({f"d{i}": _programa(str(i), ["Tema " * 200]) for i in range(5)})
    pasajes = sweep_sections(almacen, ["dom-1"], 3, 300)
    assert [p.document_id for p in pasajes] == ["d0", "d1", "d2"]
    assert all(len(p.text) <= 300 for p in pasajes)


def test_un_fallo_del_almacen_devuelve_vacio_y_no_lanza(caplog):
    almacen = _Almacen({"a": _programa("A", ["x"])})
    almacen.falla = True
    assert sweep_sections(almacen, ["dom-1"], 40, 6000) == []
    assert "Falló el barrido de secciones" in caplog.text


def test_las_instrucciones_piden_todos_los_cursos():
    assert "CADA curso" in SWEEP_INSTRUCTIONS
