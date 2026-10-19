import logging

import pytest

from mia.rag import citations
from mia.rag.llm import RagContext, format_context


@pytest.fixture(autouse=True)
def _sin_avisos_previos():
    citations._INVALID_VALUES_WARNED.clear()
    yield
    citations._INVALID_VALUES_WARNED.clear()


# --- Opción de configuración ---------------------------------------------------------


@pytest.mark.parametrize("valor", ["on", "ON", "true", "True", "1", "yes", " on ", " TRUE\n"])
def test_cited_sources_enabled_encendido(valor):
    assert citations.cited_sources_enabled(valor) is True


@pytest.mark.parametrize("valor", ["off", "OFF", "false", "0", "no", "", "  "])
def test_cited_sources_enabled_apagado(valor, caplog):
    with caplog.at_level(logging.WARNING, logger=citations.__name__):
        assert citations.cited_sources_enabled(valor) is False
    assert caplog.records == []  # un valor válido de apagado no avisa


def test_cited_sources_enabled_valor_invalido_apaga_y_avisa_una_sola_vez(caplog):
    with caplog.at_level(logging.WARNING, logger=citations.__name__):
        assert citations.cited_sources_enabled("quizas") is False
        assert citations.cited_sources_enabled("quizas") is False
        assert citations.cited_sources_enabled("otro") is False
    avisos = [r.getMessage() for r in caplog.records]
    assert len(avisos) == 2  # una vez por valor distinto
    assert "quizas" in avisos[0] and "QUERY_CITED_SOURCES" in avisos[0]


# --- Formato del contexto --------------------------------------------------------------


def test_format_context_sin_referencia_es_identico_al_formato_anterior():
    contexto = [
        RagContext(domain="Memoria", document="acta-1.pdf", excerpt="Texto uno."),
        RagContext(domain="Currículum", document="plan.docx", excerpt="Texto dos."),
    ]
    anterior = "\n\n".join(
        f"[Fuente: dominio={c.domain}, documento={c.document}]\n{c.excerpt}" for c in contexto
    )
    assert format_context(contexto) == anterior


def test_format_context_con_referencia_lleva_el_numero():
    contexto = [
        RagContext(domain="Memoria", document="acta-1.pdf", excerpt="Texto uno.", reference=1),
        RagContext(domain="Currículum", document="plan.docx", excerpt="Texto dos.", reference=2),
    ]
    assert format_context(contexto) == (
        "[Fuente 1: dominio=Memoria, documento=acta-1.pdf]\nTexto uno.\n\n"
        "[Fuente 2: dominio=Currículum, documento=plan.docx]\nTexto dos."
    )


# --- Interpretación de las citas: casos con citas válidas -------------------------------


@pytest.mark.parametrize(
    "linea, esperado",
    [
        ("FUENTES: 1, 3", [1, 3]),
        ("FUENTES: 3, 3, 1", [1, 3]),
        ("**FUENTES:** 2", [2]),
        ("fuentes: 2", [2]),
        ("Fuente: 4", [4]),
        ("FUENTES: [1], [3]", [1, 3]),
        ("FUENTES: 1 y 3", [1, 3]),
        ("> _FUENTES_: 2", [2]),
        ("FUENTES : 2", [2]),
    ],
)
def test_parse_citations_con_citas_validas(linea, esperado):
    parsed = citations.parse_citations(f"El dato es 14 horas.\n\n{linea}", total=4)
    assert parsed.cited == esperado
    assert parsed.invalid == []
    assert parsed.line_found is True
    assert parsed.text == "El dato es 14 horas."


def test_parse_citations_quita_la_linea_y_los_espacios_finales():
    parsed = citations.parse_citations("Respuesta.\nFUENTES: 1  \n\n  ", total=2)
    assert parsed.text == "Respuesta."
    assert parsed.cited == [1]


def test_parse_citations_conserva_el_resto_del_texto_intacto():
    texto = "**Lo que dicen los documentos**\n- Dato 2 (acta-1)\n\n**Conclusión**: 4 + 4 = 8"
    parsed = citations.parse_citations(f"{texto}\nFUENTES: 1, 2", total=2)
    assert parsed.text == texto


def test_select_sources_con_citas_validas():
    parsed = citations.parse_citations("Dato.\nFUENTES: 3, 1", total=4)
    seleccion = citations.select_sources(parsed, total=4)
    assert seleccion.indexes == [1, 3]  # en el orden original de entrega
    assert seleccion.safety_rule is False


def test_citation_instructions_pide_la_linea_y_no_tiene_guion_largo():
    texto = citations.CITATION_INSTRUCTIONS
    assert "FUENTES:" in texto and "SIN_INFORMACION" in texto
    assert chr(0x2014) not in texto


# --- Interpretación de las citas: sin citas utilizables ---------------------------------


def test_parse_citations_sin_linea_deja_el_texto_igual():
    parsed = citations.parse_citations("Respuesta sin citas.", total=3)
    assert parsed.text == "Respuesta sin citas."
    assert parsed.cited == [] and parsed.line_found is False


@pytest.mark.parametrize("linea", ["FUENTES: ninguna", "FUENTES: ninguna.", "FUENTES:", "FUENTES: n/a", "Fuentes: Ninguno"])
def test_parse_citations_linea_sin_numeros_se_quita_y_no_cita_nada(linea):
    parsed = citations.parse_citations(f"Respuesta.\n{linea}", total=3)
    assert parsed.text == "Respuesta."
    assert parsed.cited == [] and parsed.line_found is True


def test_parse_citations_todo_fuera_de_rango():
    parsed = citations.parse_citations("Respuesta.\nFUENTES: 9, 12", total=4)
    assert parsed.cited == [] and parsed.invalid == [9, 12] and parsed.line_found is True
    assert parsed.text == "Respuesta."


def test_parse_citations_mezcla_de_validas_e_invalidas():
    parsed = citations.parse_citations("Respuesta.\nFUENTES: 2, 9, 0", total=4)
    assert parsed.cited == [2] and parsed.invalid == [0, 9]


def test_parse_citations_linea_en_medio_del_texto_no_se_interpreta():
    texto = "FUENTES: 1\nSigue la respuesta, que termina sin línea de citas."
    parsed = citations.parse_citations(texto, total=3)
    assert parsed.text == texto and parsed.cited == [] and parsed.line_found is False


def test_parse_citations_una_frase_que_empieza_por_fuentes_no_es_una_cita():
    texto = "Respuesta.\nFuentes: las actas 04-2026 y 05-2026 del consejo."
    parsed = citations.parse_citations(texto, total=6)
    assert parsed.text == texto and parsed.cited == [] and parsed.line_found is False


def test_parse_citations_respuesta_vacia_o_solo_la_linea():
    assert citations.parse_citations("", total=3).text == ""
    solo_linea = citations.parse_citations("FUENTES: 1", total=3)
    assert solo_linea.text == "FUENTES: 1" and solo_linea.line_found is False  # no se devuelve un texto vacío


def test_parse_citations_no_distingue_mayusculas_ni_tildes():
    for etiqueta in ("FUENTES", "fuentes", "Fuentes", "FÚENTES", "fuente", "Fuente"):
        assert citations.parse_citations(f"R.\n{etiqueta}: 1", total=2).cited == [1], etiqueta


def test_select_sources_sin_citas_validas_muestra_todo_y_activa_la_regla_de_seguridad():
    for texto in ("Sin línea.", "R.\nFUENTES: ninguna", "R.\nFUENTES: 9"):
        parsed = citations.parse_citations(texto, total=3)
        seleccion = citations.select_sources(parsed, total=3)
        assert seleccion.indexes == [1, 2, 3]
        assert seleccion.safety_rule is True
