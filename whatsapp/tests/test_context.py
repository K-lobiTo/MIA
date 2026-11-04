"""Contexto de conversación del servicio (feature 013): 4 turnos por persona, vencimiento, tope y sin datos de más."""

from support import make_settings

from mia_whatsapp import state as state_module
from mia_whatsapp.state import State, Turn

MINUTO = 60


class Reloj:
    def __init__(self):
        self.now = 1_000_000.0

    def __call__(self) -> float:
        return self.now


def _state(reloj: Reloj, **settings) -> State:
    return State(make_settings(**settings), clock=reloj)


def _persona(texto: str) -> Turn:
    return Turn(role="person", text=texto)


def _bot(kind: str, programs=(), candidates=()) -> Turn:
    return Turn(role="bot", kind=kind, programs=tuple(programs), candidates=tuple(candidates))


def test_guarda_los_turnos_de_una_persona_en_orden():
    estado = _state(Reloj())
    estado.conversations.add("ana", _persona("hola"), _bot("no_info"))

    assert [t.role for t in estado.conversations.turns("ana")] == ["person", "bot"]
    assert estado.conversations.turns("ana")[0].text == "hola"


def test_nunca_guarda_mas_turnos_que_los_configurados_y_sale_el_mas_viejo():
    estado = _state(Reloj())
    for i in range(1, 4):
        estado.conversations.add("ana", _persona(f"pregunta {i}"), _bot("answer", ["Maestría en Ciberseguridad"]))

    turnos = estado.conversations.turns("ana")
    assert len(turnos) == 4
    assert [t.text for t in turnos if t.role == "person"] == ["pregunta 2", "pregunta 3"]


def test_el_numero_de_turnos_se_configura():
    estado = _state(Reloj(), bot_context_messages=2)
    estado.conversations.add("ana", _persona("a"), _bot("no_info"), _persona("b"))

    assert [t.text for t in estado.conversations.turns("ana") if t.role == "person"] == ["b"]
    assert len(estado.conversations.turns("ana")) == 2


def test_una_persona_sin_clave_no_tiene_contexto():
    estado = _state(Reloj())
    estado.conversations.add(None, _persona("hola"))

    assert estado.conversations.turns(None) == []
    assert estado.conversations.pending(None) is None and estado.conversations.remembered_program(None) is None
    assert estado.conversations.count == 0


def test_cada_persona_tiene_su_propio_contexto():
    estado = _state(Reloj())
    estado.conversations.add("ana", _persona("de ana"), _bot("clarify", candidates=["A", "B"]))
    estado.conversations.add("beto", _persona("de beto"))

    assert estado.conversations.pending("ana") is not None
    assert estado.conversations.pending("beto") is None
    assert [t.text for t in estado.conversations.turns("beto")] == ["de beto"]


def test_la_conversacion_vence_por_inactividad_y_cada_turno_renueva_el_plazo():
    reloj = Reloj()
    estado = _state(reloj, bot_context_minutes=30)
    estado.conversations.add("ana", _persona("hola"))

    reloj.now += 29 * MINUTO
    assert estado.conversations.turns("ana") != []  # sigue vigente
    estado.conversations.add("ana", _bot("no_info"))  # renueva el plazo

    reloj.now += 29 * MINUTO
    assert len(estado.conversations.turns("ana")) == 2

    reloj.now += 2 * MINUTO
    assert estado.conversations.turns("ana") == []  # venció
    assert estado.conversations.count == 0


def test_una_conversacion_vencida_empieza_de_cero_al_volver_a_escribir():
    reloj = Reloj()
    estado = _state(reloj, bot_context_minutes=30)
    estado.conversations.add("ana", _persona("vieja"), _bot("clarify", candidates=["A", "B"]))

    reloj.now += 31 * MINUTO
    estado.conversations.add("ana", _persona("nueva"))

    assert [t.text for t in estado.conversations.turns("ana")] == ["nueva"]
    assert estado.conversations.pending("ana") is None


def test_respeta_el_tope_de_conversaciones_y_salen_primero_las_mas_viejas(monkeypatch):
    monkeypatch.setattr(state_module, "MAX_CONVERSATIONS", 3)
    estado = _state(Reloj())
    for persona in ("a", "b", "c", "d"):
        estado.conversations.add(persona, _persona(persona))

    assert estado.conversations.count == 3
    assert estado.conversations.turns("a") == []
    assert estado.conversations.turns("d") != []


def test_el_tope_de_conversaciones_sale_de_la_configuracion():
    estado = _state(Reloj(), bot_context_max_people=100)
    for i in range(130):
        estado.conversations.add(f"p{i}", _persona("x"))

    assert estado.conversations.count == 100
    assert estado.conversations.turns("p0") == [] and estado.conversations.turns("p129") != []


def test_la_limpieza_retira_las_conversaciones_vencidas_y_deja_las_vigentes():
    reloj = Reloj()
    estado = _state(reloj, bot_context_minutes=30)
    estado.conversations.add("vieja", _persona("x"))
    reloj.now += 20 * MINUTO
    estado.conversations.add("reciente", _persona("y"))
    reloj.now += 15 * MINUTO  # "vieja" lleva 35 min; "reciente", 15

    estado.cleanup()

    assert estado.conversations.count == 1
    assert estado.conversations.turns("reciente") != []


def test_el_turno_del_bot_no_guarda_el_texto_de_la_respuesta():
    turno = _bot("answer", ["Maestría en Ciberseguridad"])

    assert not hasattr(turno, "answer") and turno.text == ""
    assert (turno.kind, turno.programs) == ("answer", ("Maestría en Ciberseguridad",))


def test_el_turno_de_la_persona_recorta_el_texto_al_maximo_de_la_pregunta():
    estado = _state(Reloj(), bot_max_question_chars=40)
    estado.conversations.add_person("ana", "x" * 500)

    assert len(estado.conversations.turns("ana")[0].text) == 40


def test_la_aclaracion_pendiente_es_el_ultimo_turno_del_bot_con_la_pregunta_original():
    estado = _state(Reloj())
    estado.conversations.add(
        "ana", _persona("¿Cuándo empiezan las lecciones?"), _bot("clarify", candidates=["Maestría en A", "Maestría en B"])
    )

    pendiente = estado.conversations.pending("ana")

    assert pendiente.question == "¿Cuándo empiezan las lecciones?"
    assert pendiente.candidates == ("Maestría en A", "Maestría en B")


def test_no_hay_aclaracion_pendiente_si_el_ultimo_turno_no_es_una_aclaracion_del_bot():
    estado = _state(Reloj())
    estado.conversations.add("ana", _persona("p"), _bot("clarify", candidates=["A", "B"]), _persona("no sé"))
    assert estado.conversations.pending("ana") is None

    estado.conversations.add("beto", _persona("p"), _bot("answer", ["A"]))
    assert estado.conversations.pending("beto") is None


def test_el_programa_recordado_es_el_unico_programa_de_la_ultima_respuesta():
    estado = _state(Reloj())
    estado.conversations.add("ana", _persona("p"), _bot("answer", ["Maestría en A"]), _persona("q"), _bot("no_info"))

    assert estado.conversations.remembered_program("ana") == "Maestría en A"  # un "sin información" posterior no lo borra


def test_sin_programa_recordado_si_la_ultima_respuesta_cito_varios_o_ninguno_o_no_hubo_respuesta():
    estado = _state(Reloj())
    estado.conversations.add("varios", _persona("p"), _bot("answer", ["A", "B"]))
    estado.conversations.add("ninguno", _persona("p"), _bot("answer", []))
    estado.conversations.add("solo_sin_info", _persona("p"), _bot("no_info"))

    for persona in ("varios", "ninguno", "solo_sin_info"):
        assert estado.conversations.remembered_program(persona) is None


def test_el_programa_recordado_es_el_de_la_respuesta_mas_reciente():
    estado = _state(Reloj())
    estado.conversations.add("ana", _persona("p"), _bot("answer", ["A"]), _persona("q"), _bot("answer", ["B"]))

    assert estado.conversations.remembered_program("ana") == "B"
