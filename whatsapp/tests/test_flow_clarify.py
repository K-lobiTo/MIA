"""El flujo con aclaración de programa y contexto de conversación (feature 013, contracts/servicio-whatsapp-contexto.md)."""

import asyncio
import json

import pytest
from support import NUMBER_ID, FakeClock, make_deps, make_message

from mia_whatsapp.config import DEFAULT_TEXT_CLARIFY, DEFAULT_TEXT_GREETING, DEFAULT_TEXT_NO_INFO
from mia_whatsapp.flow import handle_message

CIBER = "Maestría en Ciberseguridad"
ANA = "Maestría en Analítica de Negocio (Business Analytics)"
AMBIGUA = "¿Cuándo empiezan las lecciones?"


def run(deps, message):
    asyncio.run(handle_message(message, deps))


def lineas(capsys):
    return [json.loads(l) for l in capsys.readouterr().out.splitlines() if l.startswith("{")]


def respuesta(texto, programs, document="Documento.txt"):
    return {
        "id": "q", "answer": texto, "sources": [{"domain": "Apertura", "document": document, "excerpt": "..."}],
        "mode": "literal", "latency_ms": 10, "no_info": False, "images": [], "clarify": [], "programs": list(programs),
    }


def sin_informacion():
    return {
        "id": "q", "answer": "No encontré información suficiente", "sources": [], "mode": "literal", "latency_ms": 10,
        "no_info": True, "images": [], "clarify": [], "programs": [],
    }


def aclaracion(*candidatos):
    return {**sin_informacion(), "clarify": list(candidatos)}


class Guion:
    """Respuestas de la API según la pregunta; guarda las preguntas recibidas, en orden."""

    def __init__(self, reglas):
        self.reglas = reglas  # lista de (texto que debe estar en la pregunta o None, cuerpo)
        self.preguntas: list[str] = []

    def __call__(self, pregunta):
        self.preguntas.append(pregunta)
        for fragmento, cuerpo in self.reglas:
            if fragmento is None or fragmento in pregunta:
                return cuerpo
        return sin_informacion()


@pytest.fixture
def mundo(fake_mia, fake_kapso):
    reloj = FakeClock()
    deps = make_deps(fake_mia, fake_kapso, reloj)
    return fake_mia, fake_kapso, deps, reloj


def escribir(deps, texto, persona="persona-1", message_id=None):
    mensaje = make_message(text=texto, person_key=persona, message_id=message_id or f"wamid.{texto}.{persona}")
    run(deps, mensaje)


def guion_de_dos_programas(fake_mia):
    guion = Guion(
        [
            (f"({CIBER})", respuesta("Las lecciones de Ciberseguridad inician en el I trimestre de 2027.", [CIBER], "Ciber_Admision.txt")),
            (f"({ANA})", respuesta("Las lecciones de Analítica inician el 5 de octubre de 2026.", [ANA], "Ana_Admision.txt")),
            (AMBIGUA, aclaracion(CIBER, ANA)),
        ]
    )
    fake_mia.query_responder = guion
    return guion


# --- US1: la aclaración ------------------------------------------------------------------------------------------


def test_una_pregunta_ambigua_envia_un_solo_mensaje_con_la_aclaracion_numerada_y_el_saludo(mundo, capsys):
    fake_mia, fake_kapso, deps, _ = mundo
    guion_de_dos_programas(fake_mia)

    escribir(deps, AMBIGUA)

    esperado = DEFAULT_TEXT_CLARIFY.format(programs=f"1. {CIBER}\n2. {ANA}")
    assert fake_kapso.texts == [f"{DEFAULT_TEXT_GREETING}\n\n{esperado}"]
    assert fake_kapso.images == []
    [linea] = lineas(capsys)
    assert linea["resultado"] == "aclaracion" and linea["mensajes_enviados"] == 1
    # Cuenta como un mensaje enviado más en la cuota del mes.
    cuentas = [r["json"] for r in fake_mia.recorded.to("/bot/messages")]
    assert cuentas == [
        {"number_id": NUMBER_ID, "received": 1, "sent": 0},
        {"number_id": NUMBER_ID, "received": 0, "sent": 1},
    ]


def test_sin_informacion_sin_candidatos_sigue_enviando_el_texto_de_siempre(mundo, capsys):
    fake_mia, fake_kapso, deps, _ = mundo
    fake_mia.query_responder = Guion([(None, sin_informacion())])

    escribir(deps, "¿Cuánto cuesta la luna?")

    assert fake_kapso.texts == [f"{DEFAULT_TEXT_GREETING}\n\n{DEFAULT_TEXT_NO_INFO}"]
    assert lineas(capsys)[0]["resultado"] == "sin_informacion"


def test_la_aclaracion_no_se_guarda_si_el_envio_falla(mundo, capsys):
    fake_mia, fake_kapso, deps, _ = mundo
    guion_de_dos_programas(fake_mia)
    fake_kapso.status = 500

    escribir(deps, AMBIGUA)

    assert lineas(capsys)[0]["resultado"] == "error_envio"
    assert deps.state.conversations.pending("persona-1") is None
    assert deps.state.conversations.turns("persona-1") == []


def test_un_texto_de_aclaracion_configurado_se_usa_con_los_candidatos(fake_mia, fake_kapso):
    deps = make_deps(fake_mia, fake_kapso, bot_text_clarify="¿Cuál? {programs}")
    guion_de_dos_programas(fake_mia)

    escribir(deps, AMBIGUA)

    assert fake_kapso.texts[0].endswith(f"¿Cuál? 1. {CIBER}\n2. {ANA}")


# --- US2: resolver la aclaración -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("respuesta_de_la_persona", "programa", "fragmento"),
    [
        ("Ciberseguridad", CIBER, "I trimestre de 2027"),
        ("la de analítica", ANA, "5 de octubre de 2026"),
        ("Maestría en Analítica de Negocio", ANA, "5 de octubre de 2026"),
        ("2", ANA, "5 de octubre de 2026"),
        ("1", CIBER, "I trimestre de 2027"),
    ],
)
def test_contestar_un_candidato_repite_la_pregunta_original_con_ese_programa_y_la_responde(
    mundo, respuesta_de_la_persona, programa, fragmento
):
    fake_mia, fake_kapso, deps, _ = mundo
    guion = guion_de_dos_programas(fake_mia)
    escribir(deps, AMBIGUA)

    escribir(deps, respuesta_de_la_persona)

    assert guion.preguntas == [AMBIGUA, f"{AMBIGUA} ({programa})"]
    assert fragmento in fake_kapso.texts[-1] and fake_kapso.texts[-1].endswith("Admision.txt")
    assert DEFAULT_TEXT_GREETING not in fake_kapso.texts[-1]  # ya se saludó en la aclaración


def test_la_respuesta_resuelta_lleva_imagen_y_fuentes_como_cualquier_otra(mundo):
    fake_mia, fake_kapso, deps, _ = mundo
    guion_de_dos_programas(fake_mia)
    cuerpo = respuesta("Las lecciones de Ciberseguridad inician en 2027.", [CIBER], "Ciber_Admision.txt")
    cuerpo["images"] = [{"url": "/media/abc", "caption": "Calendario", "document": "Ciber_Admision.txt"}]
    fake_mia.query_responder = Guion([(f"({CIBER})", cuerpo), (AMBIGUA, aclaracion(CIBER, ANA))])
    escribir(deps, AMBIGUA)

    escribir(deps, "Ciberseguridad")

    assert fake_kapso.images == [{"link": "https://mia.example.com/media/abc", "caption": "Calendario"}]


@pytest.mark.parametrize("texto", ["no sé", "Computación", "¿Cuánto cuesta?"])
def test_una_respuesta_que_no_decide_descarta_la_aclaracion_y_es_una_pregunta_nueva_sin_volver_a_preguntar(mundo, texto):
    fake_mia, fake_kapso, deps, _ = mundo
    guion = guion_de_dos_programas(fake_mia)
    escribir(deps, AMBIGUA)

    escribir(deps, texto)

    assert guion.preguntas == [AMBIGUA, texto]  # el mensaje se consulta tal cual, sin la pregunta original
    assert fake_kapso.texts[-1] == DEFAULT_TEXT_NO_INFO
    assert deps.state.conversations.pending("persona-1") is None


@pytest.mark.parametrize(
    "texto",
    ["ciberseguridad y analítica", "la de ciberseguridad y la de analítica", "las dos", "ambas", "todas", "Ciberseguridad, Analítica"],
)
def test_una_respuesta_que_nombra_varios_candidatos_da_sin_informacion_sin_consultar_ni_volver_a_preguntar(mundo, texto):
    fake_mia, fake_kapso, deps, _ = mundo
    # Una API que ante cualquier texto respondería con otra aclaración: no debe llegar a consultarse.
    guion = Guion([(None, aclaracion(CIBER, ANA))])
    fake_mia.query_responder = guion
    escribir(deps, AMBIGUA)

    escribir(deps, texto)

    assert guion.preguntas == [AMBIGUA]  # el mensaje con varios candidatos no se consulta
    assert len(fake_kapso.texts) == 2 and fake_kapso.texts[1] == DEFAULT_TEXT_NO_INFO
    assert deps.state.conversations.pending("persona-1") is None
    ultimo = deps.state.conversations.turns("persona-1")[-1]
    assert (ultimo.role, ultimo.kind) == ("bot", "no_info")


def test_el_mensaje_que_nombra_varios_candidatos_cuenta_en_la_cuota_como_cualquier_otro(mundo, capsys):
    fake_mia, _, deps, _ = mundo
    fake_mia.query_responder = Guion([(None, aclaracion(CIBER, ANA))])
    escribir(deps, AMBIGUA)
    capsys.readouterr()

    escribir(deps, "las dos")

    assert lineas(capsys)[0]["resultado"] == "sin_informacion"
    cuentas = [r["json"] for r in fake_mia.recorded.to("/bot/messages")]
    assert cuentas[-2:] == [
        {"number_id": NUMBER_ID, "received": 1, "sent": 0},
        {"number_id": NUMBER_ID, "received": 0, "sent": 1},
    ]


def test_si_la_consulta_con_el_programa_elegido_vuelve_a_pedir_aclaracion_se_responde_sin_informacion(mundo):
    fake_mia, fake_kapso, deps, _ = mundo
    fake_mia.query_responder = Guion([(None, aclaracion(CIBER, ANA))])  # siempre ambigua, incluso con programa
    escribir(deps, AMBIGUA)

    escribir(deps, "Ciberseguridad")

    assert len(fake_kapso.texts) == 2
    assert fake_kapso.texts[1] == DEFAULT_TEXT_NO_INFO  # nunca dos aclaraciones por pregunta


def test_una_aclaracion_vencida_no_se_resuelve_y_ciberseguridad_es_un_mensaje_nuevo(mundo):
    fake_mia, _, deps, reloj = mundo
    guion = guion_de_dos_programas(fake_mia)
    escribir(deps, AMBIGUA)

    reloj.now += (deps.settings.bot_context_minutes + 1) * 60
    escribir(deps, "Ciberseguridad")

    assert guion.preguntas == [AMBIGUA, "Ciberseguridad"]


def test_sin_aclaracion_previa_ciberseguridad_es_una_pregunta_nueva(mundo):
    fake_mia, _, deps, _ = mundo
    guion = guion_de_dos_programas(fake_mia)

    escribir(deps, "Ciberseguridad")

    assert guion.preguntas == ["Ciberseguridad"]


def test_dos_personas_con_aclaraciones_pendientes_no_se_mezclan(mundo):
    fake_mia, _, deps, _ = mundo
    guion = guion_de_dos_programas(fake_mia)
    escribir(deps, AMBIGUA, persona="ana")
    escribir(deps, "¿Cuánto cuesta?", persona="beto")
    fake_mia.query_responder = guion  # sigue el mismo guion

    escribir(deps, "Ciberseguridad", persona="ana")

    assert guion.preguntas[-1] == f"{AMBIGUA} ({CIBER})"
    assert deps.state.conversations.pending("beto") is None


def test_un_mensaje_duplicado_no_cuenta_dos_veces_en_el_contexto(mundo):
    fake_mia, fake_kapso, deps, _ = mundo
    guion_de_dos_programas(fake_mia)

    escribir(deps, AMBIGUA, message_id="wamid.igual")
    escribir(deps, AMBIGUA, message_id="wamid.igual")  # reintento de Kapso

    assert len(deps.state.conversations.turns("persona-1")) == 2  # la pregunta y la aclaración, una vez
    assert len(fake_kapso.texts) == 1


# --- US3: recordar el programa ---------------------------------------------------------------------------------


def con_programa_recordado(fake_mia, deps):
    """Una respuesta previa de Ciberseguridad deja a la persona hablando de ese programa."""
    guion = Guion(
        [
            (f"({CIBER})", respuesta("Cuesta ₡69.290 por crédito.", [CIBER], "Ciber_Presentacion.txt")),
            ("lecciones de la maestría en ciberseguridad", respuesta("Inician en 2027.", [CIBER], "Ciber_Admision.txt")),
        ]
    )
    fake_mia.query_responder = guion
    escribir(deps, "¿Cuándo empiezan las lecciones de la maestría en ciberseguridad?")
    guion.preguntas.clear()
    return guion


def test_una_pregunta_siguiente_sin_programa_que_daria_sin_informacion_se_reintenta_con_el_programa_recordado(mundo):
    fake_mia, fake_kapso, deps, _ = mundo
    guion = con_programa_recordado(fake_mia, deps)

    escribir(deps, "¿Y cuánto cuesta?")

    assert guion.preguntas == ["¿Y cuánto cuesta?", f"¿Y cuánto cuesta? ({CIBER})"]
    assert "₡69.290" in fake_kapso.texts[-1]
    assert deps.state.conversations.remembered_program("persona-1") == CIBER


def test_el_reintento_usa_un_solo_lugar_de_la_cola_y_no_cuenta_mensajes_extra(mundo):
    fake_mia, fake_kapso, deps, _ = mundo
    con_programa_recordado(fake_mia, deps)
    entradas = []
    entrar = deps.state.gate.enter

    async def contar_entrada():
        entradas.append(1)
        return await entrar()

    deps.state.gate.enter = contar_entrada
    enviados_antes = len(fake_kapso.texts)

    escribir(deps, "¿Y cuánto cuesta?")

    assert len(entradas) == 1
    assert len(fake_kapso.texts) == enviados_antes + 1
    ultima_cuenta = fake_mia.recorded.to("/bot/messages")[-1]["json"]
    assert ultima_cuenta == {"number_id": NUMBER_ID, "received": 0, "sent": 1}


def test_si_el_reintento_tampoco_responde_se_da_sin_informacion_y_nunca_un_segundo_reintento(mundo):
    fake_mia, fake_kapso, deps, _ = mundo
    guion = con_programa_recordado(fake_mia, deps)
    guion.reglas = [(None, sin_informacion())]

    escribir(deps, "¿Y la residencia?")

    assert guion.preguntas == ["¿Y la residencia?", f"¿Y la residencia? ({CIBER})"]  # exactamente dos
    assert fake_kapso.texts[-1] == DEFAULT_TEXT_NO_INFO


def test_una_aclaracion_con_programa_recordado_se_reintenta_en_lugar_de_preguntar(mundo):
    fake_mia, fake_kapso, deps, _ = mundo
    guion = con_programa_recordado(fake_mia, deps)
    guion.reglas = [
        (f"({CIBER})", respuesta("Las lecciones inician en 2027.", [CIBER], "Ciber_Admision.txt")),
        (None, aclaracion(CIBER, ANA)),
    ]

    escribir(deps, AMBIGUA)

    assert guion.preguntas == [AMBIGUA, f"{AMBIGUA} ({CIBER})"]
    assert "2027" in fake_kapso.texts[-1] and "¿A qué programa" not in fake_kapso.texts[-1]


def test_si_el_reintento_no_responde_se_envia_la_aclaracion_original(mundo):
    fake_mia, fake_kapso, deps, _ = mundo
    guion = con_programa_recordado(fake_mia, deps)
    guion.reglas = [(None, aclaracion(CIBER, ANA))]

    escribir(deps, AMBIGUA)

    assert guion.preguntas == [AMBIGUA, f"{AMBIGUA} ({CIBER})"]
    assert f"1. {CIBER}" in fake_kapso.texts[-1]


def test_una_pregunta_que_se_responde_sin_contexto_no_se_reintenta_ni_se_modifica(mundo):
    fake_mia, fake_kapso, deps, _ = mundo
    guion = con_programa_recordado(fake_mia, deps)
    guion.reglas = [
        ("residencia", respuesta("Hay residencias.", [ANA], "Ana_Presentacion.txt")),
        (None, sin_informacion()),
    ]

    escribir(deps, "¿Hay residencia?")

    assert guion.preguntas == ["¿Hay residencia?"]  # sin reintento
    assert "Hay residencias" in fake_kapso.texts[-1]
    assert deps.state.conversations.remembered_program("persona-1") == ANA  # nombrar otro programa lo cambia


def test_una_respuesta_que_cita_varios_programas_no_deja_programa_recordado(mundo):
    fake_mia, _, deps, _ = mundo
    fake_mia.query_responder = Guion([(None, respuesta("Ambos.", [CIBER, ANA], "Varios.txt"))])

    escribir(deps, "¿Qué ofrecen?")

    assert deps.state.conversations.remembered_program("persona-1") is None


def test_la_aclaracion_resuelta_deja_recordado_el_programa_elegido(mundo):
    fake_mia, _, deps, _ = mundo
    guion_de_dos_programas(fake_mia)
    escribir(deps, AMBIGUA)

    escribir(deps, "Ciberseguridad")

    assert deps.state.conversations.remembered_program("persona-1") == CIBER


def test_un_programa_recordado_vencido_no_se_usa(mundo):
    fake_mia, _, deps, reloj = mundo
    guion = con_programa_recordado(fake_mia, deps)
    guion.reglas = [(None, sin_informacion())]

    reloj.now += (deps.settings.bot_context_minutes + 1) * 60
    escribir(deps, "¿Y cuánto cuesta?")

    assert guion.preguntas == ["¿Y cuánto cuesta?"]  # sin reintento: no hay contexto


def test_sin_contexto_el_flujo_es_el_de_antes(mundo, capsys):
    fake_mia, fake_kapso, deps, _ = mundo
    # La API de antes: sin `clarify` ni `programs` en la respuesta.
    fake_mia.query_responder = None

    escribir(deps, "¿Cuándo es la matrícula?")

    assert fake_kapso.texts[-1].endswith("Fuentes: horario_matricula.pdf")
    assert [r["json"]["question"] for r in fake_mia.recorded.to("/bot/query")] == ["¿Cuándo es la matrícula?"]
    assert lineas(capsys)[0]["resultado"] == "respondido"


def test_un_texto_de_aclaracion_sin_programs_envia_la_lista_igual(fake_mia, fake_kapso):
    deps = make_deps(fake_mia, fake_kapso, bot_text_clarify="¿A cuál te refieres?")
    guion_de_dos_programas(fake_mia)

    escribir(deps, AMBIGUA)

    assert fake_kapso.texts[0].endswith(f"¿A cuál te refieres?\n1. {CIBER}\n2. {ANA}")


# --- Lo demás no cambia y el contexto es privado (US4 y US5) ---------------------------------------------------


@pytest.mark.parametrize("estado", ["disabled", "cap_reached"])
def test_el_bot_desactivado_o_con_el_tope_alcanzado_no_toca_el_contexto(mundo, estado):
    fake_mia, _, deps, _ = mundo
    guion_de_dos_programas(fake_mia)
    escribir(deps, AMBIGUA)
    antes = deps.state.conversations.turns("persona-1")
    fake_mia.status = estado

    escribir(deps, "Ciberseguridad")

    assert deps.state.conversations.turns("persona-1") == antes  # nada se agregó ni se resolvió
    assert len(fake_mia.recorded.to("/bot/query")) == 1  # no se consultó


def test_los_mensajes_que_no_son_texto_ni_los_largos_no_tocan_el_contexto(mundo):
    fake_mia, _, deps, _ = mundo
    guion_de_dos_programas(fake_mia)
    escribir(deps, AMBIGUA)
    antes = deps.state.conversations.turns("persona-1")

    run(deps, make_message(type="audio", text=None, person_key="persona-1", message_id="wamid.audio"))
    escribir(deps, "x" * 600)

    assert deps.state.conversations.turns("persona-1") == antes
    assert deps.state.conversations.pending("persona-1") is not None  # la aclaración sigue esperando


def test_el_registro_del_servicio_no_lleva_textos_telefonos_ni_nombres_de_programas(mundo, capsys):
    fake_mia, _, deps, _ = mundo
    guion_de_dos_programas(fake_mia)

    escribir(deps, AMBIGUA)
    escribir(deps, "Ciberseguridad")
    escribir(deps, "¿Y cuánto cuesta?")
    registro = capsys.readouterr().out
    lineas_json = [json.loads(l) for l in registro.splitlines() if l.startswith("{")]

    assert lineas_json[0]["resultado"] == "aclaracion"
    assert all("ms" in l and "resultado" in l for l in lineas_json)
    for secreto in ("Ciberseguridad", "Analítica", "lecciones", "cuesta", "16315551181", "persona-1"):
        assert secreto not in registro
