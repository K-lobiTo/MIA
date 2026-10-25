"""Límites del bot: por persona (con un solo aviso), cola de consultas con descarte y tope mensual."""

import asyncio
import json

import pytest
from support import NUMBER_ID, FakeClock, make_deps, make_message, make_settings

from mia_whatsapp import state as state_module
from mia_whatsapp.config import (
    DEFAULT_TEXT_GREETING,
    DEFAULT_TEXT_NOT_TEXT,
    DEFAULT_TEXT_RATE_LIMIT,
)
from mia_whatsapp.flow import handle_message
from mia_whatsapp.state import State

HORA = 3600
DIA = 24 * HORA


def run(deps, message):
    asyncio.run(handle_message(message, deps))


def lineas(capsys):
    return [json.loads(l) for l in capsys.readouterr().out.splitlines() if l.startswith("{")]


def resultados(capsys):
    return [l["resultado"] for l in lineas(capsys)]


def mensajes(n, persona="persona-1", desde=0):
    return [make_message(message_id=f"wamid.{persona}.{desde + i}", person_key=persona) for i in range(n)]


# --- State.allow: las ventanas por persona ---------------------------------------------------------------------


def _state(reloj=None, **settings):
    reloj = reloj or FakeClock()
    return State(make_settings(**settings), clock=reloj), reloj


def test_hasta_el_limite_por_hora_se_aceptan_y_el_siguiente_se_bloquea_con_un_solo_aviso():
    estado, _ = _state(bot_max_messages_per_hour=3)

    permisos = [estado.allow("ana") for _ in range(6)]

    assert [p.allowed for p in permisos] == [True, True, True, False, False, False]
    assert [p.notify for p in permisos] == [False, False, False, True, False, False]


def test_el_bloqueo_por_hora_termina_cuando_pasa_la_ventana():
    estado, reloj = _state(bot_max_messages_per_hour=2)
    estado.allow("ana")
    estado.allow("ana")
    assert estado.allow("ana").allowed is False

    reloj.now += HORA - 1
    assert estado.allow("ana").allowed is False
    reloj.now += 2
    assert estado.allow("ana").allowed is True


def test_los_mensajes_bloqueados_no_suman_a_la_ventana():
    estado, reloj = _state(bot_max_messages_per_hour=2)
    estado.allow("ana")
    estado.allow("ana")
    # Insiste durante casi una hora: nada de eso prolonga el bloqueo.
    for _ in range(10):
        reloj.now += 300
        assert estado.allow("ana").allowed is False

    reloj.now += HORA  # pasó una hora desde los dos mensajes aceptados
    assert estado.allow("ana").allowed is True


def test_el_limite_por_dia_bloquea_aunque_el_de_la_hora_no_se_alcance():
    estado, reloj = _state(bot_max_messages_per_hour=100, bot_max_messages_per_day=5)
    for _ in range(5):
        assert estado.allow("ana").allowed is True
        reloj.now += 1800  # un mensaje cada media hora: nunca más de 2 por hora

    permiso = estado.allow("ana")
    assert permiso.allowed is False and permiso.notify is True

    reloj.now += DIA - 5 * 1800 + 1  # pasa el día desde el primer mensaje
    assert estado.allow("ana").allowed is True


def test_el_aviso_se_repite_si_pasado_el_bloqueo_se_vuelve_a_superar_el_limite():
    estado, reloj = _state(bot_max_messages_per_hour=1)
    assert estado.allow("ana").allowed is True
    assert estado.allow("ana").notify is True
    assert estado.allow("ana").notify is False

    reloj.now += HORA + 1
    assert estado.allow("ana").allowed is True
    assert estado.allow("ana").notify is True  # otro bloqueo, otro aviso


def test_una_persona_bloqueada_no_afecta_a_otra():
    estado, _ = _state(bot_max_messages_per_hour=1)
    estado.allow("ana")
    assert estado.allow("ana").allowed is False
    assert estado.allow("beto").allowed is True


def test_sin_clave_de_persona_no_se_limita():
    estado, _ = _state(bot_max_messages_per_hour=1)
    assert all(estado.allow(None).allowed for _ in range(5))


def test_las_personas_en_memoria_no_pasan_del_tope_y_salen_primero_las_mas_viejas(monkeypatch):
    monkeypatch.setattr(state_module, "MAX_PEOPLE", 3)
    estado, _ = _state()
    for persona in ("a", "b", "c", "d", "e"):
        estado.allow(persona)

    assert estado.people_count == 3


def test_la_limpieza_retira_a_quien_ya_no_tiene_mensajes_vigentes():
    estado, reloj = _state()
    estado.allow("ana")
    reloj.now += DIA + 1
    estado.allow("beto")

    estado.cleanup()

    assert estado.people_count == 1


# --- El flujo con el límite por persona ------------------------------------------------------------------------


def test_el_mensaje_11_de_una_hora_recibe_un_solo_aviso_y_los_siguientes_nada(fake_mia, fake_kapso, capsys):
    deps = make_deps(fake_mia, fake_kapso)

    for mensaje in mensajes(14):
        run(deps, mensaje)

    assert resultados(capsys) == ["respondido"] * 10 + ["limite"] + ["limite_en_curso"] * 3
    # 10 respuestas más un solo aviso; el aviso no lleva saludo y no se consultó a la API por los bloqueados.
    assert len(fake_kapso.texts) == 11
    assert fake_kapso.texts[-1] == DEFAULT_TEXT_RATE_LIMIT
    assert len([c for c in fake_mia.recorded.requests if c["path"].endswith("/bot/query")]) == 10


def test_el_mensaje_31_de_un_dia_tambien_recibe_un_solo_aviso(fake_mia, fake_kapso, capsys):
    reloj = FakeClock()
    deps = make_deps(fake_mia, fake_kapso, reloj)

    for mensaje in mensajes(33):
        run(deps, mensaje)
        reloj.now += 600  # un mensaje cada 10 minutos: 6 por hora, 144 por día

    assert resultados(capsys) == ["respondido"] * 30 + ["limite", "limite_en_curso", "limite_en_curso"]


def test_los_mensajes_bloqueados_no_alargan_el_bloqueo(fake_mia, fake_kapso, capsys):
    reloj = FakeClock()
    deps = make_deps(fake_mia, fake_kapso, reloj)
    for mensaje in mensajes(10):
        run(deps, mensaje)  # 10 aceptados a la vez
    for i in range(5):
        reloj.now += 200
        run(deps, make_message(message_id=f"wamid.insiste.{i}", person_key="persona-1"))

    reloj.now += HORA  # una hora después de los 10 primeros
    run(deps, make_message(message_id="wamid.despues", person_key="persona-1"))

    assert resultados(capsys)[-1] == "respondido"


def test_los_mensajes_que_no_son_texto_tambien_suman_a_la_ventana(fake_mia, fake_kapso, capsys):
    deps = make_deps(fake_mia, fake_kapso)

    for i in range(5):
        run(deps, make_message(message_id=f"wamid.audio.{i}", type="audio", text=None))
    for mensaje in mensajes(6):
        run(deps, mensaje)

    esperado = ["no_texto"] * 5 + ["respondido"] * 5 + ["limite"]
    assert resultados(capsys) == esperado
    assert DEFAULT_TEXT_NOT_TEXT in fake_kapso.texts[0]


def test_otra_persona_sigue_atendida_mientras_una_esta_bloqueada(fake_mia, fake_kapso, capsys):
    deps = make_deps(fake_mia, fake_kapso)
    for mensaje in mensajes(12, "ana"):
        run(deps, mensaje)
    capsys.readouterr()

    run(deps, make_message(message_id="wamid.beto.1", person_key="beto"))

    assert resultados(capsys) == ["respondido"]


def test_con_el_limite_de_la_hora_configurado_se_aplica_ese_valor(fake_mia, fake_kapso, capsys):
    deps = make_deps(fake_mia, fake_kapso, bot_max_messages_per_hour=2)

    for mensaje in mensajes(4):
        run(deps, mensaje)

    assert resultados(capsys) == ["respondido", "respondido", "limite", "limite_en_curso"]


def test_el_aviso_de_limite_se_envia_al_destino_y_se_cuenta_como_enviado(fake_mia, fake_kapso):
    deps = make_deps(fake_mia, fake_kapso, bot_max_messages_per_hour=1)
    run(deps, make_message(message_id="wamid.1"))
    run(deps, make_message(message_id="wamid.2"))

    assert fake_kapso.texts[-1] == DEFAULT_TEXT_RATE_LIMIT
    assert fake_kapso.recorded.requests[-1]["json"]["to"] == "16315551181"
    ultimos = [r["json"] for r in fake_mia.recorded.requests if r["path"].endswith("/bot/messages")]
    assert ultimos[-1] == {"number_id": NUMBER_ID, "received": 0, "sent": 1}


def test_el_saludo_no_se_antepone_al_aviso_de_limite_ni_se_marca_como_enviado(fake_mia, fake_kapso):
    deps = make_deps(fake_mia, fake_kapso, bot_max_messages_per_hour=1)
    # Persona que ya habló antes de que el estado se reiniciara: su primer mensaje se acepta y se saluda.
    run(deps, make_message(message_id="wamid.1"))
    run(deps, make_message(message_id="wamid.2"))

    assert DEFAULT_TEXT_GREETING in fake_kapso.texts[0]
    assert DEFAULT_TEXT_GREETING not in fake_kapso.texts[1]


# --- Tope mensual ----------------------------------------------------------------------------------------------


def test_con_el_tope_mensual_alcanzado_no_se_envia_ni_un_mensaje_aunque_llegue_una_rafaga(fake_mia, fake_kapso, capsys):
    fake_mia.status = "cap_reached"
    deps = make_deps(fake_mia, fake_kapso)

    for mensaje in mensajes(5):
        run(deps, mensaje)

    assert fake_kapso.recorded.requests == []
    assert resultados(capsys) == ["tope_mensual"] * 5
    # Cada mensaje recibido se cuenta igual (consume la cuota aunque no se responda) y nunca se consulta.
    llamadas = [r["path"] for r in fake_mia.recorded.requests]
    assert llamadas == ["/bot/messages"] * 5


def test_si_el_tope_se_alcanza_a_mitad_de_la_conversacion_el_bot_deja_de_responder(fake_mia, fake_kapso, capsys):
    deps = make_deps(fake_mia, fake_kapso)
    run(deps, make_message(message_id="wamid.1"))
    fake_mia.status = "cap_reached"

    run(deps, make_message(message_id="wamid.2"))
    run(deps, make_message(message_id="wamid.3"))

    assert resultados(capsys) == ["respondido", "tope_mensual", "tope_mensual"]
    assert len(fake_kapso.texts) == 1


# --- Consultas simultáneas y cola ------------------------------------------------------------------------------


class Compuerta:
    """Retiene las consultas de la API simulada hasta que se libere, y mide cuántas hubo a la vez."""

    def __init__(self):
        self.liberar = None
        self.en_curso = 0
        self.maximo = 0

    async def __call__(self, entrada):
        self.en_curso += 1
        self.maximo = max(self.maximo, self.en_curso)
        try:
            await self.liberar.wait()
        finally:
            self.en_curso -= 1


def _rafaga(fake_mia, fake_kapso, cantidad, **settings):
    compuerta = Compuerta()
    fake_mia.query_delay = compuerta
    deps = make_deps(fake_mia, fake_kapso, **settings)

    async def correr():
        compuerta.liberar = asyncio.Event()
        tareas = [
            asyncio.create_task(handle_message(make_message(message_id=f"wamid.{i}", person_key=f"persona-{i}"), deps))
            for i in range(cantidad)
        ]
        await asyncio.sleep(0.05)  # todos llegan: uno consulta, algunos esperan y el resto se descarta
        compuerta.liberar.set()
        await asyncio.gather(*tareas)

    asyncio.run(correr())
    return compuerta


def test_una_rafaga_mayor_que_la_cola_atiende_una_parte_y_descarta_el_resto_sin_responder(fake_mia, fake_kapso, capsys):
    compuerta = _rafaga(fake_mia, fake_kapso, 6, bot_max_concurrent_queries=1, bot_queue_size=2)

    resultado = resultados(capsys)

    assert sorted(resultado) == ["descartado"] * 3 + ["respondido"] * 3
    assert len(fake_kapso.texts) == 3  # los descartados no reciben nada
    assert compuerta.maximo == 1


def test_nunca_hay_mas_consultas_simultaneas_que_las_configuradas(fake_mia, fake_kapso):
    compuerta = _rafaga(fake_mia, fake_kapso, 12, bot_max_concurrent_queries=3, bot_queue_size=20)

    assert compuerta.maximo == 3
    assert len(fake_kapso.texts) == 12  # con la cola de 20 nadie se descarta


def test_con_los_valores_por_defecto_una_rafaga_de_50_no_supera_5_consultas_simultaneas(fake_mia, fake_kapso, capsys):
    compuerta = _rafaga(fake_mia, fake_kapso, 50)

    resultado = resultados(capsys)
    assert compuerta.maximo == 5
    # 5 consultando y 20 esperando se atienden; el resto (25) se descarta.
    assert resultado.count("respondido") == 25 and resultado.count("descartado") == 25


def test_un_error_en_la_consulta_libera_su_lugar_en_la_cola(fake_mia, fake_kapso, capsys):
    deps = make_deps(fake_mia, fake_kapso, bot_max_concurrent_queries=1, bot_queue_size=0)
    original = deps.api.query

    async def falla(*args, **kwargs):
        raise RuntimeError("bug imprevisto")

    deps.api.query = falla
    run(deps, make_message(message_id="wamid.1"))
    deps.api.query = original
    run(deps, make_message(message_id="wamid.2", person_key="otra"))

    assert resultados(capsys) == ["error_interno", "respondido"]


@pytest.mark.parametrize("cola", [0])
def test_con_la_cola_en_cero_solo_se_atiende_lo_que_cabe_en_las_consultas_simultaneas(fake_mia, fake_kapso, capsys, cola):
    _rafaga(fake_mia, fake_kapso, 4, bot_max_concurrent_queries=2, bot_queue_size=cola)

    resultado = resultados(capsys)
    assert resultado.count("respondido") == 2 and resultado.count("descartado") == 2


def test_los_mensajes_descartados_ya_se_contaron_como_recibidos(fake_mia, fake_kapso):
    _rafaga(fake_mia, fake_kapso, 4, bot_max_concurrent_queries=1, bot_queue_size=0)

    recibidos = [r["json"]["received"] for r in fake_mia.recorded.requests if r["path"].endswith("/bot/messages")
                 and r["json"]["received"]]
    assert len(recibidos) == 4
