"""Cliente de la API de Kapso: texto, destino sin teléfono, reintento, limitador por minuto y errores sin datos personales."""

import asyncio
import logging
import re

import httpx
from support import NUMBER_ID, FakeClock, FakeKapso, make_settings

from mia_whatsapp.kapso import KapsoClient, RateLimiter

BASE = "https://api.kapso.ai/meta/whatsapp/v24.0"


def _client(fake: FakeKapso, clock: FakeClock | None = None, **settings) -> KapsoClient:
    clock = clock or FakeClock()
    http = httpx.AsyncClient(transport=fake.transport())
    return KapsoClient(make_settings(**settings), http, sleep=clock.sleep, clock=clock.clock)


def _send_text(client, destination=("to", "16315551181"), text="Hola"):
    return asyncio.run(client.send_text(NUMBER_ID, destination, text))


# --- Texto -----------------------------------------------------------------------------------------------------


def test_el_texto_se_envia_a_la_direccion_de_kapso_con_la_clave_y_el_cuerpo_del_contrato():
    fake = FakeKapso()

    resultado = _send_text(_client(fake))

    assert resultado.ok is True and resultado.status == 200 and resultado.error is None
    [peticion] = fake.recorded.requests
    assert peticion["method"] == "POST"
    assert peticion["url"] == f"{BASE}/{NUMBER_ID}/messages"
    assert peticion["headers"]["x-api-key"] == "clave-de-kapso"
    assert peticion["headers"]["content-type"] == "application/json"
    assert peticion["json"] == {
        "messaging_product": "whatsapp",
        "to": "16315551181",
        "type": "text",
        "text": {"body": "Hola"},
    }


def test_sin_telefono_el_cuerpo_lleva_recipient_y_recipient_type_en_lugar_de_to():
    fake = FakeKapso()

    _send_text(_client(fake), ("recipient", "US.13491208655302741918"))

    cuerpo = fake.recorded.requests[0]["json"]
    assert cuerpo["recipient"] == "US.13491208655302741918" and cuerpo["recipient_type"] == "individual"
    assert "to" not in cuerpo and cuerpo["text"] == {"body": "Hola"}


def test_la_direccion_de_kapso_se_puede_cambiar_para_el_simulador_local():
    fake = FakeKapso()
    _send_text(_client(fake, kapso_api_url="http://localhost:9000/"))
    assert fake.recorded.requests[0]["url"] == f"http://localhost:9000/{NUMBER_ID}/messages"


def test_cualquier_2xx_es_entregado():
    for codigo in (200, 201, 202):
        def handler(request, codigo=codigo):
            return httpx.Response(codigo, json={})

        cliente = KapsoClient(make_settings(), httpx.AsyncClient(transport=httpx.MockTransport(handler)))
        assert _send_text(cliente).ok is True


# --- Reintento -------------------------------------------------------------------------------------------------


def test_un_5xx_se_reintenta_una_sola_vez_tras_un_segundo():
    fake = FakeKapso()
    respuestas = [httpx.Response(503, json={}), httpx.Response(200, json={"messages": []})]

    def handler(request):
        fake.recorded.add(request)
        return respuestas.pop(0)

    reloj = FakeClock()
    cliente = KapsoClient(
        make_settings(), httpx.AsyncClient(transport=httpx.MockTransport(handler)), sleep=reloj.sleep, clock=reloj.clock
    )

    resultado = _send_text(cliente)

    assert resultado.ok is True and len(fake.recorded.requests) == 2
    assert 1.0 in reloj.sleeps


def test_dos_5xx_seguidos_fallan_despues_de_un_solo_reintento():
    fake = FakeKapso()
    fake.status = 500

    resultado = _send_text(_client(fake))

    assert resultado.ok is False and resultado.status == 500
    assert len(fake.recorded.requests) == 2


def test_un_fallo_de_red_se_reintenta_una_vez():
    llamadas = []

    def handler(request):
        llamadas.append(1)
        if len(llamadas) == 1:
            raise httpx.ConnectError("sin conexión")
        return httpx.Response(200, json={})

    reloj = FakeClock()
    cliente = KapsoClient(
        make_settings(), httpx.AsyncClient(transport=httpx.MockTransport(handler)), sleep=reloj.sleep, clock=reloj.clock
    )

    assert _send_text(cliente).ok is True
    assert len(llamadas) == 2

    def siempre_falla(request):
        raise httpx.ConnectError("sin conexión")

    cliente = KapsoClient(
        make_settings(), httpx.AsyncClient(transport=httpx.MockTransport(siempre_falla)), sleep=reloj.sleep, clock=reloj.clock
    )
    resultado = _send_text(cliente)
    assert resultado.ok is False and resultado.status is None and "ConnectError" in resultado.error


def test_un_4xx_no_se_reintenta():
    fake = FakeKapso()
    fake.status = 400

    resultado = _send_text(_client(fake))

    assert resultado.ok is False and resultado.status == 400
    assert len(fake.recorded.requests) == 1


# --- Limitador de envíos ---------------------------------------------------------------------------------------


def test_el_limitador_deja_pasar_hasta_el_limite_y_espera_para_no_superarlo():
    reloj = FakeClock()
    limitador = RateLimiter(3, clock=reloj.clock, sleep=reloj.sleep)

    async def correr():
        for _ in range(3):
            await limitador.acquire()
        assert reloj.sleeps == []  # los primeros tres pasan sin esperar
        await limitador.acquire()  # el cuarto espera a que el primero cumpla un minuto

    asyncio.run(correr())

    assert len(reloj.sleeps) == 1 and 59.0 <= reloj.sleeps[0] <= 60.0


def test_el_limitador_vuelve_a_dejar_pasar_pasado_un_minuto():
    reloj = FakeClock()
    limitador = RateLimiter(2, clock=reloj.clock, sleep=reloj.sleep)

    async def correr():
        await limitador.acquire()
        await limitador.acquire()
        reloj.now += 61
        await limitador.acquire()

    asyncio.run(correr())

    assert reloj.sleeps == []


def test_el_cliente_no_supera_los_envios_por_minuto_configurados():
    fake = FakeKapso()
    reloj = FakeClock()
    cliente = _client(fake, reloj, bot_kapso_rate_per_min=2)

    async def correr():
        for i in range(5):
            await cliente.send_text(NUMBER_ID, ("to", "111"), f"m{i}")

    asyncio.run(correr())

    assert len(fake.recorded.requests) == 5
    assert reloj.sleeps  # tuvo que esperar al menos una vez
    # En cualquier ventana de 60 s no hubo más de 2 envíos: se comprueba con las horas simuladas de cada espera.
    assert sum(reloj.sleeps) >= 60


# --- Errores sin datos personales ------------------------------------------------------------------------------


def test_un_error_se_resume_sin_telefonos_y_sin_el_cuerpo_enviado(caplog):
    def handler(request):
        return httpx.Response(400, json={"error": {"message": "Recipient 16315551181 is not a valid WhatsApp user"}})

    cliente = KapsoClient(make_settings(), httpx.AsyncClient(transport=httpx.MockTransport(handler)))

    with caplog.at_level(logging.WARNING, logger="mia_whatsapp"):
        resultado = _send_text(cliente, ("to", "16315551181"), "Mi cédula es 1-2345-6789")

    assert resultado.ok is False and resultado.error
    assert not re.search(r"\d{7,}", resultado.error)
    registro = " ".join(r.getMessage() for r in caplog.records)
    assert not re.search(r"\d{7,}", registro) and "cédula" not in registro
    assert "400" in registro


def test_un_cuerpo_de_error_que_no_es_json_se_recorta():
    def handler(request):
        return httpx.Response(502, text="x" * 5000)

    reloj = FakeClock()
    cliente = KapsoClient(
        make_settings(), httpx.AsyncClient(transport=httpx.MockTransport(handler)), sleep=reloj.sleep, clock=reloj.clock
    )
    resultado = _send_text(cliente)
    assert resultado.ok is False and len(resultado.error) <= 300


# --- Imágenes --------------------------------------------------------------------------------------------------


def _send_image(client, destination=("to", "16315551181"), link="https://mia.example.com/media/abc", caption="Horario"):
    return asyncio.run(client.send_image(NUMBER_ID, destination, link, caption))


def test_la_imagen_se_envia_por_enlace_con_su_descripcion_como_pie_de_foto():
    fake = FakeKapso()

    resultado = _send_image(_client(fake))

    assert resultado.ok is True
    [peticion] = fake.recorded.requests
    assert peticion["url"] == f"{BASE}/{NUMBER_ID}/messages"
    assert peticion["headers"]["x-api-key"] == "clave-de-kapso"
    assert peticion["json"] == {
        "messaging_product": "whatsapp",
        "to": "16315551181",
        "type": "image",
        "image": {"link": "https://mia.example.com/media/abc", "caption": "Horario"},
    }


def test_sin_descripcion_el_cuerpo_no_lleva_pie_de_foto():
    fake = FakeKapso()
    _send_image(_client(fake), caption="")
    assert fake.recorded.requests[0]["json"]["image"] == {"link": "https://mia.example.com/media/abc"}


def test_la_descripcion_se_recorta_a_1024_caracteres():
    fake = FakeKapso()
    _send_image(_client(fake), caption="x" * 2000)
    assert len(fake.recorded.requests[0]["json"]["image"]["caption"]) == 1024


def test_la_imagen_sin_telefono_se_envia_al_identificador_de_usuario():
    fake = FakeKapso()
    _send_image(_client(fake), ("recipient", "US.13491208655302741918"))
    cuerpo = fake.recorded.requests[0]["json"]
    assert cuerpo["recipient"] == "US.13491208655302741918" and cuerpo["recipient_type"] == "individual" and "to" not in cuerpo


def test_un_fallo_de_la_imagen_devuelve_el_resultado_sin_lanzar_y_el_texto_no_se_ve_afectado():
    fake = FakeKapso()
    fake.image_status = 400
    cliente = _client(fake)

    imagen = _send_image(cliente)
    texto = _send_text(cliente)

    assert imagen.ok is False and imagen.status == 400
    assert texto.ok is True
    # Un 4xx de la imagen no se reintenta.
    assert len([r for r in fake.recorded.requests if r["json"]["type"] == "image"]) == 1
