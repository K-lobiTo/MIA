"""Reglas puras de la aclaración (feature 013): coincidir la respuesta de la persona con un candidato y componer la pregunta."""

import pytest

from mia_whatsapp.clarify import match_candidate, render_clarify, with_program

CIBER = "Maestría en Ciberseguridad"
ANA = "Maestría en Analítica de Negocio (Business Analytics)"
CANDIDATOS = [CIBER, ANA]


@pytest.mark.parametrize(
    "texto",
    ["Ciberseguridad", "ciberseguridad", "  CIBERSEGURIDAD  ", "MAESTRÍA EN CIBERSEGURIDAD", "maestria en ciberseguridad", "la de ciberseguridad", "1", " 1 "],
)
def test_resuelve_el_programa_de_ciberseguridad(texto):
    assert match_candidate(texto, CANDIDATOS) == CIBER


@pytest.mark.parametrize(
    "texto",
    [
        "Analítica",
        "analitica",
        "la de analítica",
        "Maestría en Analítica de Negocio",
        "analítica de negocios (business analytics)",
        "negocio",
        "Business Analytics",
        "2",
    ],
)
def test_resuelve_el_programa_de_analitica(texto):
    assert match_candidate(texto, CANDIDATOS) == ANA


@pytest.mark.parametrize(
    "texto",
    [
        "no sé",
        "las dos",
        "Computación",
        "ciberseguridad y analítica",  # nombra dos: no se puede decidir
        "maestría",  # tras quitar las palabras vacías no queda nada
        "la",
        "",
        "   ",
        "3",  # número fuera de rango
        "0",
        "12",
        "¿Cuánto cuesta?",
    ],
)
def test_no_resuelve_si_no_coincide_exactamente_un_candidato(texto):
    assert match_candidate(texto, CANDIDATOS) is None


def test_no_resuelve_sin_candidatos():
    assert match_candidate("ciberseguridad", []) is None
    assert match_candidate("1", []) is None


def test_una_palabra_compartida_por_dos_candidatos_no_decide():
    candidatos = ["Maestría en Computación con énfasis en Datos", "Maestría en Gerencia de Datos"]
    assert match_candidate("datos", candidatos) is None
    assert match_candidate("gerencia", candidatos) == candidatos[1]


def test_la_pregunta_con_programa_agrega_el_nombre_entre_parentesis():
    assert with_program("¿Cuándo empiezan las lecciones?", CIBER) == "¿Cuándo empiezan las lecciones? (Maestría en Ciberseguridad)"
    assert with_program("  ¿Cuánto cuesta?  ", ANA) == f"¿Cuánto cuesta? ({ANA})"


def test_la_lista_de_candidatos_va_numerada_en_el_lugar_de_programs():
    texto = render_clarify("¿A qué programa te refieres?\n{programs}\nResponde con el nombre.", CANDIDATOS)

    assert texto == f"¿A qué programa te refieres?\n1. {CIBER}\n2. {ANA}\nResponde con el nombre."


def test_un_texto_sin_programs_se_envia_seguido_de_la_lista_numerada():
    texto = render_clarify("¿A cuál te refieres?", CANDIDATOS)

    assert texto == f"¿A cuál te refieres?\n1. {CIBER}\n2. {ANA}"
