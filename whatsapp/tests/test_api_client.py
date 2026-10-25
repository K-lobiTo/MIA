"""Cliente de la API de MIA: cuenta de mensajes y consulta, con los errores traducidos a resultados."""

import asyncio
import logging

import httpx
from support import NUMBER_ID, FakeMia, make_settings

from mia_whatsapp.api_client import CountResult, ImageRef, MiaApiClient, QueryResult


def _client(fake: FakeMia, **settings) -> MiaApiClient:
    return MiaApiClient(make_settings(**settings), httpx.AsyncClient(transport=fake.transport()))


def _client_with(handler, **settings) -> MiaApiClient:
    return MiaApiClient(make_settings(**settings), httpx.AsyncClient(transport=httpx.MockTransport(handler)))


def _count(client, **kwargs):
    return asyncio.run(client.count_messages(NUMBER_ID, **kwargs))


def _query(client, question="¿Cuándo es la matrícula?"):
    return asyncio.run(client.query(NUMBER_ID, question))


# --- count_messages --------------------------------------------------------------------------------------------


def test_la_cuenta_llama_a_bot_messages_con_la_credencial_de_servicio():
    fake = FakeMia()

    resultado = _count(_client(fake), received=1)

    assert resultado == CountResult(status="ok", month_messages=1, month_cap=1800)
    [peticion] = fake.recorded.requests
    assert peticion["method"] == "POST" and peticion["url"] == "https://mia.example.com/bot/messages"
    assert peticion["headers"]["x-bot-service-key"] == "clave-de-servicio"
    assert peticion["json"] == {"number_id": NUMBER_ID, "received": 1, "sent": 0}


def test_lo_enviado_se_cuenta_con_sent():
    fake = FakeMia()
    _count(_client(fake), sent=3)
    assert fake.recorded.requests[0]["json"] == {"number_id": NUMBER_ID, "received": 0, "sent": 3}


def test_los_estados_de_la_api_se_devuelven_tal_cual():
    for estado in ("ok", "disabled", "cap_reached", "unknown_bot"):
        fake = FakeMia()
        fake.status = estado
        assert _count(_client(fake), received=1).status == estado


def test_unknown_bot_no_trae_cifras():
    fake = FakeMia()
    fake.status = "unknown_bot"
    assert _count(_client(fake)) == CountResult(status="unknown_bot", month_messages=None, month_cap=None)


def test_un_error_de_la_api_o_de_red_al_contar_es_el_estado_error():
    fake = FakeMia()
    fake.counts_error = 500
    assert _count(_client(fake), received=1).status == "error"

    def sin_red(request):
        raise httpx.ConnectError("sin conexión")

    assert _count(_client_with(sin_red), received=1).status == "error"

    def lenta(request):
        raise httpx.ReadTimeout("tarda")

    assert _count(_client_with(lenta), received=1).status == "error"


def test_una_respuesta_sin_la_forma_esperada_al_contar_es_error():
    assert _count(_client_with(lambda r: httpx.Response(200, json={"algo": 1}))).status == "error"
    assert _count(_client_with(lambda r: httpx.Response(200, text="no es json"))).status == "error"


def test_la_credencial_rechazada_al_contar_es_error_y_se_registra_como_configuracion(caplog):
    fake = FakeMia()
    fake.counts_error = 401
    with caplog.at_level(logging.ERROR, logger="mia_whatsapp"):
        resultado = _count(_client(fake), received=1)
    assert resultado.status == "error"
    assert any("BOT_SERVICE_KEY" in r.getMessage() for r in caplog.records)


# --- query -----------------------------------------------------------------------------------------------------


def test_la_consulta_llama_a_bot_query_con_el_numero_y_la_pregunta():
    fake = FakeMia()

    resultado = _query(_client(fake))

    [peticion] = fake.recorded.requests
    assert peticion["url"] == "https://mia.example.com/bot/query"
    assert peticion["headers"]["x-bot-service-key"] == "clave-de-servicio"
    assert peticion["json"] == {"number_id": NUMBER_ID, "question": "¿Cuándo es la matrícula?"}
    assert resultado == QueryResult(
        kind="answer", answer="La matrícula es del 3 al 7 de agosto.", sources=["horario_matricula.pdf"], images=[],
        status_code=200,
    )


def test_las_imagenes_de_la_respuesta_se_devuelven_en_orden():
    fake = FakeMia()
    fake.query_body["images"] = [
        {"url": "/media/abc", "caption": "Horario", "document": "horario_matricula.pdf"},
        {"url": "/media/def", "caption": "", "document": "otro.pdf"},
    ]

    resultado = _query(_client(fake))

    assert resultado.images == [
        ImageRef(url="/media/abc", caption="Horario", document="horario_matricula.pdf"),
        ImageRef(url="/media/def", caption="", document="otro.pdf"),
    ]


def test_las_fuentes_son_los_nombres_de_los_documentos_en_orden():
    fake = FakeMia()
    fake.query_body["sources"] = [
        {"domain": "A", "document": "uno.pdf", "excerpt": "x"},
        {"domain": "B", "document": "dos.pdf", "excerpt": "y"},
    ]
    assert _query(_client(fake)).sources == ["uno.pdf", "dos.pdf"]


def test_una_respuesta_sin_informacion_es_no_info_sin_fuentes_ni_imagenes():
    fake = FakeMia()
    fake.query_body.update({"no_info": True, "sources": [], "images": [], "answer": "No encontré información suficiente"})

    resultado = _query(_client(fake))

    assert resultado.kind == "no_info" and resultado.sources == [] and resultado.images == []


def test_los_rechazos_y_las_fallas_de_la_api_son_no_disponible():
    for codigo in (403, 429, 502, 500, 503):
        fake = FakeMia()
        fake.query_status = codigo
        resultado = _query(_client(fake))
        assert resultado.kind == "unavailable" and resultado.status_code == codigo


def test_un_numero_sin_bot_es_unknown_bot():
    fake = FakeMia()
    fake.query_status = 404
    assert _query(_client(fake)).kind == "unknown_bot"


def test_la_credencial_rechazada_al_consultar_es_no_disponible_y_se_registra(caplog):
    fake = FakeMia()
    fake.query_status = 401
    with caplog.at_level(logging.ERROR, logger="mia_whatsapp"):
        resultado = _query(_client(fake))
    assert resultado.kind == "unavailable" and resultado.status_code == 401
    assert any("BOT_SERVICE_KEY" in r.getMessage() for r in caplog.records)


def test_el_tiempo_agotado_y_un_error_de_red_son_no_disponible():
    def lenta(request):
        raise httpx.ReadTimeout("tarda demasiado")

    def sin_red(request):
        raise httpx.ConnectError("sin conexión")

    assert _query(_client_with(lenta)).kind == "unavailable"
    assert _query(_client_with(sin_red)).kind == "unavailable"


def test_una_respuesta_200_sin_la_forma_esperada_es_no_disponible():
    assert _query(_client_with(lambda r: httpx.Response(200, json=["no", "es", "objeto"]))).kind == "unavailable"
    assert _query(_client_with(lambda r: httpx.Response(200, text="no es json"))).kind == "unavailable"
    assert _query(_client_with(lambda r: httpx.Response(200, json={"id": "x"}))).kind == "unavailable"


def test_la_consulta_espera_como_maximo_el_tiempo_configurado():
    vistos = []

    def handler(request):
        vistos.append(request.extensions["timeout"])
        return httpx.Response(200, json=FakeMia().query_body)

    _query(_client_with(handler, bot_query_timeout_s=17))

    assert vistos[0]["read"] == 17 and vistos[0]["connect"] == 17


def test_la_cuenta_de_mensajes_no_espera_tanto_como_la_consulta():
    vistos = []

    def handler(request):
        vistos.append(request.extensions["timeout"]["read"])
        return httpx.Response(200, json={"status": "ok", "month": "2026-10", "month_messages": 1, "month_cap": 1800})

    _count(_client_with(handler, bot_query_timeout_s=30), received=1)

    assert vistos[0] <= 10
