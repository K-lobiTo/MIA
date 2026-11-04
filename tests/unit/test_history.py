"""El historial de la consulta (feature 014): validación, recorte por vueltas y por tamaño, y el bloque para el modelo."""

import pytest

from mia.api.routes.query import NO_INFO_ANSWER
from mia.config import settings
from mia.rag.history import HistoryTurn, format_history, sanitize_history


def vuelta(n, respuesta=None, modo=None):
    return HistoryTurn(question=f"pregunta {n}", answer=respuesta or f"respuesta {n}", mode=modo)


@pytest.fixture(autouse=True)
def topes(monkeypatch):
    monkeypatch.setattr(settings, "history_max_question_chars", 500)
    monkeypatch.setattr(settings, "history_max_answer_chars", 1500)
    monkeypatch.setattr(settings, "history_max_chars", 6000)


def test_con_memoria_cero_el_resultado_es_vacio_sin_mirar_la_entrada():
    class Explota:
        def __iter__(self):
            raise AssertionError("no debe leerse")

    assert sanitize_history(Explota(), 0, "literal") == []
    assert sanitize_history([vuelta(1)], 0, "razonamiento") == []


def test_devuelve_las_ultimas_vueltas_en_orden():
    historial = [vuelta(n) for n in range(1, 6)]

    resultado = sanitize_history(historial, 3, "literal")

    assert [v.question for v in resultado] == ["pregunta 3", "pregunta 4", "pregunta 5"]


def test_con_menos_vueltas_que_la_memoria_devuelve_las_que_hay():
    assert [v.question for v in sanitize_history([vuelta(1), vuelta(2)], 10, "literal")] == [
        "pregunta 1",
        "pregunta 2",
    ]
    assert sanitize_history([], 3, "literal") == []


@pytest.mark.parametrize(
    "respuesta",
    [
        NO_INFO_ANSWER,
        "SIN_INFORMACION",
        "sin_informacion.",
        "No encontré información suficiente en los dominios consultados.",
    ],
)
def test_descarta_las_vueltas_con_respuesta_de_sin_informacion(respuesta):
    historial = [vuelta(1), vuelta(2, respuesta), vuelta(3)]

    assert [v.question for v in sanitize_history(historial, 5, "literal")] == [
        "pregunta 1",
        "pregunta 3",
    ]


def test_descarta_las_vueltas_con_pregunta_o_respuesta_vacia_y_las_excluidas_no_cuentan_para_la_memoria():
    historial = [
        vuelta(1),
        HistoryTurn(question="  ", answer="x"),
        HistoryTurn(question="y", answer=""),
        vuelta(2, NO_INFO_ANSWER),
        vuelta(3),
    ]

    # La memoria de 2 vueltas se cuenta sobre las vueltas válidas: las excluidas no ocupan lugar.
    assert [v.question for v in sanitize_history(historial, 2, "literal")] == [
        "pregunta 1",
        "pregunta 3",
    ]


def test_recorta_cada_pregunta_y_cada_respuesta_por_modo():
    larga = "a" * 5000
    historial = [HistoryTurn(question=larga, answer=larga)]

    literal = sanitize_history(historial, 1, "literal")[0]
    razonamiento = sanitize_history(historial, 1, "razonamiento")[0]

    assert len(literal.question) == 500 and len(razonamiento.question) == 500
    assert (
        len(literal.answer) == 1500 and len(razonamiento.answer) == 3000
    )  # el modo con razonamiento admite el doble


def test_si_el_total_se_pasa_descarta_las_vueltas_mas_viejas_hasta_que_cabe():
    # Cada vuelta pesa unos 1.500 + 20 caracteres: en literal (6.000) caben 3.
    historial = [HistoryTurn(question=f"q{n}", answer="a" * 1500) for n in range(1, 7)]

    literal = sanitize_history(historial, 6, "literal")
    razonamiento = sanitize_history(historial, 6, "razonamiento")

    assert [v.question for v in literal] == ["q4", "q5", "q6"]
    assert sum(len(v.question) + len(v.answer) for v in literal) <= 6000
    assert len(razonamiento) == 6  # 12.000 de tope: caben las seis
    assert all(
        len(v.answer) == 1500 for v in literal
    )  # ninguna queda cortada a la mitad por el total


def test_los_topes_salen_de_la_configuracion(monkeypatch):
    monkeypatch.setattr(settings, "history_max_question_chars", 50)
    monkeypatch.setattr(settings, "history_max_answer_chars", 200)
    monkeypatch.setattr(settings, "history_max_chars", 500)
    historial = [HistoryTurn(question="q" * 100, answer="a" * 400) for _ in range(4)]

    resultado = sanitize_history(historial, 4, "literal")

    assert all(len(v.question) == 50 and len(v.answer) == 200 for v in resultado)
    assert sum(len(v.question) + len(v.answer) for v in resultado) <= 500 and len(resultado) == 2


def test_el_bloque_va_rotulado_con_pregunta_y_respuesta_por_vuelta():
    bloque = format_history([vuelta(1), vuelta(2)])

    assert bloque.startswith(
        "Conversación anterior (solo para entender la pregunta; no es una fuente de datos):"
    )
    assert "Pregunta: pregunta 1\nRespuesta: respuesta 1" in bloque
    assert bloque.index("pregunta 1") < bloque.index("pregunta 2")


def test_solo_las_vueltas_de_razonamiento_llevan_la_advertencia_de_calculos():
    bloque = format_history([vuelta(1, modo="literal"), vuelta(2, modo="razonamiento"), vuelta(3)])
    advertencia = "(respuesta del modo con razonamiento: puede incluir cálculos o inferencias que no dicen los documentos)"

    assert bloque.count(advertencia) == 1
    assert bloque.index("pregunta 2") < bloque.index(advertencia) < bloque.index("pregunta 3")


def test_sin_vueltas_el_bloque_es_vacio():
    assert format_history([]) == ""
    assert format_history(None) == ""
