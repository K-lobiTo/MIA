"""Estado en memoria del servicio: mensajes ya vistos y saludo por persona (con reloj simulado)."""

from support import make_settings

from mia_whatsapp import state as state_module
from mia_whatsapp.state import State

HORA = 3600


class Reloj:
    def __init__(self):
        self.now = 1_000_000.0

    def __call__(self) -> float:
        return self.now


def _state(reloj: Reloj, **settings) -> State:
    return State(make_settings(**settings), clock=reloj)


# --- Mensajes vistos -------------------------------------------------------------------------------------------


def test_un_id_nuevo_se_registra_y_uno_repetido_se_detecta():
    estado = _state(Reloj())
    assert estado.seen("wamid.1") is False
    assert estado.seen("wamid.1") is True
    assert estado.seen("wamid.2") is False


def test_un_id_vence_a_las_horas_configuradas():
    reloj = Reloj()
    estado = _state(reloj, bot_seen_ttl_hours=2)
    estado.seen("wamid.1")

    reloj.now += 2 * HORA - 1
    assert estado.seen("wamid.1") is True  # sigue vigente

    reloj.now += HORA + 2
    assert estado.seen("wamid.1") is False  # venció: se vuelve a tratar como nuevo


def test_la_limpieza_retira_los_ids_vencidos_y_deja_los_vigentes():
    reloj = Reloj()
    estado = _state(reloj, bot_seen_ttl_hours=1)
    estado.seen("viejo")
    reloj.now += 30 * 60
    estado.seen("reciente")
    reloj.now += 40 * 60  # "viejo" lleva 70 min; "reciente", 40

    estado.cleanup()

    assert estado.seen_count == 1
    assert estado.seen("reciente") is True
    assert estado.seen("viejo") is False


def test_los_ids_vistos_no_pasan_del_tope_y_salen_primero_los_mas_viejos(monkeypatch):
    monkeypatch.setattr(state_module, "MAX_SEEN", 3)
    estado = _state(Reloj())
    for i in range(5):
        estado.seen(f"id{i}")

    assert estado.seen_count == 3
    assert estado.seen("id4") is True and estado.seen("id3") is True
    assert estado.seen("id0") is False  # ya había salido


# --- Saludo ----------------------------------------------------------------------------------------------------


def test_se_saluda_la_primera_vez_y_no_las_siguientes_dentro_del_plazo():
    estado = _state(Reloj())
    assert estado.needs_greeting("ana") is True
    estado.mark_greeted("ana")
    assert estado.needs_greeting("ana") is False
    assert estado.needs_greeting("beto") is True


def test_se_vuelve_a_saludar_pasadas_las_horas_configuradas():
    reloj = Reloj()
    estado = _state(reloj, bot_greeting_hours=24)
    estado.mark_greeted("ana")

    reloj.now += 24 * HORA - 1
    assert estado.needs_greeting("ana") is False
    reloj.now += 2
    assert estado.needs_greeting("ana") is True


def test_no_se_marca_como_saludada_a_quien_no_se_le_respondio():
    estado = _state(Reloj())
    estado.needs_greeting("ana")  # preguntar no la marca
    assert estado.needs_greeting("ana") is True


def test_sin_clave_de_persona_siempre_se_saluda_y_marcar_no_falla():
    estado = _state(Reloj())
    assert estado.needs_greeting(None) is True
    estado.mark_greeted(None)
    assert estado.needs_greeting(None) is True


def test_los_saludos_no_pasan_del_tope_de_personas(monkeypatch):
    monkeypatch.setattr(state_module, "MAX_PEOPLE", 2)
    estado = _state(Reloj())
    for persona in ("a", "b", "c"):
        estado.mark_greeted(persona)
    assert estado.greeted_count == 2
    assert estado.needs_greeting("a") is True  # la más vieja salió
    assert estado.needs_greeting("c") is False


def test_la_limpieza_retira_los_saludos_vencidos():
    reloj = Reloj()
    estado = _state(reloj, bot_greeting_hours=1)
    estado.mark_greeted("ana")
    reloj.now += 2 * HORA

    estado.cleanup()

    assert estado.greeted_count == 0
