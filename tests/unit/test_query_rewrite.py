import logging

import pytest

from mia.rag import completeness, query_rewrite
from mia.rag.query_rewrite import clean_note, clean_question


@pytest.fixture(autouse=True)
def _sin_avisos_previos():
    completeness._INVALID_VALUES_WARNED.clear()
    yield
    completeness._INVALID_VALUES_WARNED.clear()


# --- Variable de encendido --------------------------------------------------------------------


@pytest.mark.parametrize("valor", ["on", "ON", "true", "1", "yes", " on "])
def test_clean_question_enabled_encendido(valor):
    assert query_rewrite.clean_question_enabled(valor) is True


@pytest.mark.parametrize("valor", ["off", "OFF", "false", "0", "no", ""])
def test_clean_question_enabled_apagado_sin_aviso(valor, caplog):
    with caplog.at_level(logging.WARNING, logger=completeness.__name__):
        assert query_rewrite.clean_question_enabled(valor) is False
    assert caplog.records == []


def test_clean_question_enabled_invalido_apaga_y_avisa_una_vez(caplog):
    with caplog.at_level(logging.WARNING, logger=completeness.__name__):
        assert query_rewrite.clean_question_enabled("quizás") is False
        assert query_rewrite.clean_question_enabled("quizás") is False
    avisos = [r.getMessage() for r in caplog.records]
    assert len(avisos) == 1 and "QUERY_CLEAN_QUESTION" in avisos[0]


# --- Reducción: casos positivos (US1) ----------------------------------------------------------


@pytest.mark.parametrize(
    ("pregunta", "esperado"),
    [
        ("¿Quién es Natalia Soto Solís?", "Natalia Soto Solís"),
        ("quien es natalia soto solis", "natalia soto solis"),
        ("¿Qué es el TFG?", "TFG"),
        ("¿Qué son las líneas de TFG?", "líneas de TFG"),
        ("¡Háblame de Cibercrimen!", "Cibercrimen"),
        ("¿Me puedes decir quién es Joseph Obando Sandí?", "Joseph Obando Sandí"),
        ("Por favor, dime qué es el IPA", "IPA"),
        ("Dame información sobre la maestría", "la maestría"),
        ("¿Qué se sabe de Cibercrimen?", "Cibercrimen"),
        ("¿Qué sabes de Luis Diego Cubillo Guevara?", "Luis Diego Cubillo Guevara"),
        ("¿Qué sabe de Cibercrimen el coordinador?", "Cibercrimen el coordinador"),
        ("Cuéntame sobre el curso de Criptografía", "el curso de Criptografía"),
        ("Quisiera saber qué es el IPA", "IPA"),
        ("¿Quiénes son los docentes de la maestría?", "docentes de la maestría"),
        ("¿Qué significa TFG?", "TFG"),
        ("Necesito saber quién fue Alan Turing", "Alan Turing"),
        ("Dame datos acerca de Cibercrimen", "Cibercrimen"),
        ("Busco toda la información que haya sobre el Cibercrimen", "el Cibercrimen"),
        # Tildes, mayúsculas y signos
        ("QUIÉN ES NATALIA SOTO SOLÍS", "NATALIA SOTO SOLÍS"),
        ("QUIEN ES NATALIA SOTO SOLIS", "NATALIA SOTO SOLIS"),
        ("quién es Natalia Soto Solís?", "Natalia Soto Solís"),
        ("¿Quién es Natalia Soto Solís", "Natalia Soto Solís"),
        ("  ¿Quién es Natalia Soto Solís?  .", "Natalia Soto Solís"),
        ("¿Quién es Natalia Soto Solís, por favor?", "Natalia Soto Solís"),
        ("¿Quién es Natalia Soto Solís? Gracias", "Natalia Soto Solís"),
        # "por favor" y "gracias" solo se quitan como palabras completas y tras puntuación (T031)
        ("¿Quién es Santa Desgracias?", "Santa Desgracias"),
        ("¿Quién es Juan Gracias?", "Juan Gracias"),
        ("¿Qué es el IPA, gracias?", "IPA"),
        ("¿Qué es el TFG? Gracias", "TFG"),
        ("¿Qué es el TFG por favor", "TFG"),
        ("¿Qué es el Sopor Favor?", "Sopor Favor"),
        # Espacios dobles en el medio: el corte del original debe seguir siendo correcto
        ("¿Quién   es   Natalia  Soto Solís?", "Natalia Soto Solís"),
    ],
)
def test_clean_question_reduce_la_envoltura(pregunta, esperado):
    assert clean_question(pregunta) == esperado


def test_el_resultado_conserva_tildes_y_mayusculas_del_original():
    assert clean_question("¿Qué es la Maestría en Analítica?") == "Maestría en Analítica"
    assert clean_question("¿QUÉ ES LA MAESTRÍA EN ANALÍTICA?") == "MAESTRÍA EN ANALÍTICA"


# --- Reducción: negativos (US2) ----------------------------------------------------------------


@pytest.mark.parametrize(
    "pregunta",
    [
        "¿Cuántos créditos tiene el curso de IPA en Big Data?",
        "¿Cuál es el costo del curso X?",
        "¿Qué es lo que establece el reglamento sobre las becas?",
        "¿Qué es el TFG que ofrece la maestría?",
        "¿Quién es Natalia Soto? ¿Y cuántos créditos tiene el curso?",
        "¿Quién es?",
        "¿Qué es la I?",
        "Por favor, ¿cuántos créditos tiene X?",
        "Natalia Soto Solís",
        "¿Cómo se aprueba el curso?",
        "¿Qué requisitos tiene el curso X?",
        "¿Cuántas horas tiene el curso?",
        "¿Por qué se cerró la matrícula?",
        "¿Qué es necesario para graduarse?",
        "¿Qué es obligatorio en el TFG?",
        "¿Qué hay de nuevo en la maestría?",
        "¿Qué es nuevo en la maestría?",
        "¿Qué tiene de especial el curso?",
        "¿Qué tiene de malo el plan?",
        "¿Qué hay de cierto en el rumor?",
        "¿Qué tienes de información sobre Cibercrimen?",
        "¿Quién fue designado coordinador específico del proyecto ante FUNDATEC?",
        "¿Quiénes fueron elegidas representantes del Consejo?",
        "Who is Natalia Soto?",
        "",
        "   ",
        "¿?!",
    ],
)
def test_clean_question_negativos_no_se_reformulan(pregunta):
    assert clean_question(pregunta) is None


@pytest.mark.parametrize(
    ("pregunta", "esperado"),
    [
        ("¿Qué es el IP?", None),  # candidato de 2 letras
        ("¿Qué es el TFG?", "TFG"),  # 3 caracteres
        ("¿Quién es uno dos tres cuatro cinco seis siete ocho?", "uno dos tres cuatro cinco seis siete ocho"),
        ("¿Quién es uno dos tres cuatro cinco seis siete ocho nueve?", None),  # 9 palabras
        ("¿Quién es lo mejor del curso?", None),  # empieza con "lo"
        ("¿Quién es que aprueba?", None),  # empieza con "que"
        ("¿Qué es la matrícula cuando se abre?", None),
        ("¿Qué es el curso donde se matricula?", None),
        ("¿Qué son los cursos cuantos hay?", None),
        ("¿Qué son los cursos porque sí?", None),
        ("¿Qué es posible estudiar?", None),
        ("¿Qué es suficiente para aprobar?", None),
        ("¿Qué es importante saber?", None),
        ("¿Qué es mejor para graduarse?", None),
        ("¿Qué es diferente en el plan?", None),
        # Palabras que solo contienen las prohibidas no activan la guarda
        ("¿Quién es Francisco Quevedo?", "Francisco Quevedo"),
        ("¿Quién es Ana Dondelio?", "Ana Dondelio"),
        ("¿Quién fue Alan Turing?", "Alan Turing"),
        ("¿Quién es Alvarado Rojas?", "Alvarado Rojas"),  # el participio solo cuenta tras un verbo en pasado
    ],
)
def test_clean_question_guardas_del_candidato(pregunta, esperado):
    assert clean_question(pregunta) == esperado


def test_un_candidato_igual_a_la_pregunta_normalizada_no_se_reformula(monkeypatch):
    # Si una envoltura dejara la pregunta intacta no hay segundo intento (guarda 1).
    assert query_rewrite._es_igual("Natalia Soto", "natalia soto") is True
    assert query_rewrite._es_igual("Natalia", "natalia soto") is False


# --- Nota de Uso (US3) -------------------------------------------------------------------------


def test_clean_note_con_y_sin_resultados():
    assert clean_note("Natalia Soto Solís", True) == "Pregunta limpia: «Natalia Soto Solís» (con resultados)"
    assert clean_note("Natalia Soto Solís", False) == "Pregunta limpia: «Natalia Soto Solís» (sin resultados)"


def test_clean_note_recorta_el_texto_a_120_caracteres():
    nota = clean_note("a" * 300, True)
    assert nota == "Pregunta limpia: «" + "a" * 120 + "» (con resultados)"
