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


# --- Aclaración de programa y programas de las fuentes (feature 013) -------------------------------------------


def test_una_aclaracion_es_clarify_con_los_programas_candidatos_en_orden():
    fake = FakeMia()
    fake.query_body.update(
        {
            "no_info": True,
            "sources": [],
            "images": [],
            "answer": "No encontré información suficiente",
            "clarify": ["Maestría en Ciberseguridad", "Maestría en Analítica de Negocio (Business Analytics)"],
            "programs": [],
        }
    )

    resultado = _query(_client(fake))

    assert resultado.kind == "clarify"
    assert resultado.candidates == ["Maestría en Ciberseguridad", "Maestría en Analítica de Negocio (Business Analytics)"]
    assert resultado.sources == [] and resultado.images == []


def test_sin_informacion_y_sin_candidatos_sigue_siendo_no_info():
    fake = FakeMia()
    fake.query_body.update({"no_info": True, "sources": [], "images": [], "clarify": [], "programs": []})

    resultado = _query(_client(fake))

    assert resultado.kind == "no_info" and resultado.candidates == []


def test_una_respuesta_trae_los_programas_de_sus_fuentes():
    fake = FakeMia()
    fake.query_body.update({"clarify": [], "programs": ["Maestría en Ciberseguridad"]})

    resultado = _query(_client(fake))

    assert resultado.kind == "answer" and resultado.programs == ["Maestría en Ciberseguridad"]


def test_una_respuesta_de_una_api_anterior_sin_los_campos_nuevos_se_lee_como_antes():
    fake = FakeMia()  # el cuerpo por defecto no trae `clarify` ni `programs`

    resultado = _query(_client(fake))

    assert resultado.kind == "answer" and resultado.programs == [] and resultado.candidates == []


def test_un_clarify_o_programs_con_formas_raras_se_ignoran_sin_romper():
    fake = FakeMia()
    fake.query_body.update({"clarify": "no es una lista", "programs": [None, 3, "Maestría en A"]})

    resultado = _query(_client(fake))

    assert (
        resultado.kind == "answer"
        and resultado.candidates == []
        and resultado.programs == ["Maestría en A"]
    )


# --- Memoria del bot (feature 014) -------------------------------------------------------------------------------


def test_la_cuenta_lee_las_vueltas_de_memoria_que_informa_la_api():
    fake = FakeMia()
    fake.context_turns = 4

    assert _count(_client(fake), received=1).context_turns == 4


def test_sin_el_campo_o_con_una_forma_rara_la_memoria_queda_vacia():
    for valor in (None, 0, 11, "4", 2.5, True, [3]):
        fake = FakeMia()
        fake.context_turns = valor
        resultado = _count(_client(fake), received=1)

        assert resultado.status == "ok" and resultado.context_turns is None, valor


# --- contactos (feature 017) ---


def _put(client, event, **kwargs):
    return asyncio.run(client.put_contact(NUMBER_ID, "16315551181", event, **kwargs))


def test_el_telefono_va_solo_si_se_pasa():
    fake = FakeMia()
    cliente = _client(fake)

    _count(cliente, received=1)
    _count(cliente, received=1, phone="16315551181")

    sin, con = [r["json"] for r in fake.recorded.to("/bot/messages")]
    assert "phone" not in sin and con["phone"] == "16315551181"


def test_el_contacto_se_lee_de_la_cuenta():
    fake = FakeMia()

    resultado = _count(_client(fake), received=1, phone="16315551181")

    assert resultado.contact.status == "pendiente"
    assert (resultado.contact.has_name, resultado.contact.has_email, resultado.contact.email_retried) == (False, False, False)


def test_sin_telefono_o_con_una_forma_rara_el_contacto_es_nulo():
    assert _count(_client(FakeMia()), received=1).contact is None

    def raro(request):
        return httpx.Response(200, json={"status": "ok", "contact": {"status": "inventado", "has_name": 1}})

    assert _count(_client_with(raro), received=1, phone="1").contact is None


def test_put_contact_envia_el_evento_y_lee_el_resultado():
    fake = FakeMia()
    cliente = _client(fake)
    _count(cliente, received=1, phone="16315551181")

    claim = _put(cliente, "claim_invite")
    entregado = _put(cliente, "provided", name="Ana Pérez", email="ana@correo.com")

    assert claim.ok and claim.claimed and claim.state.status == "invitada"
    assert entregado.ok and entregado.state.has_name and entregado.state.has_email
    envio = fake.recorded.to("/bot/contacts")[-1]
    assert envio["method"] == "PUT" and envio["headers"]["x-bot-service-key"] == "clave-de-servicio"
    assert envio["json"] == {
        "number_id": NUMBER_ID, "phone": "16315551181", "event": "provided", "name": "Ana Pérez", "email": "ana@correo.com",
    }


def test_un_409_es_conflicto_y_no_falla():
    fake = FakeMia()
    cliente = _client(fake)
    _count(cliente, received=1, phone="16315551181")

    resultado = _put(cliente, "provided", name="Ana Pérez")  # el contacto sigue pendiente

    assert resultado.ok is False and resultado.conflict is True


def test_put_contact_nunca_lanza_y_no_registra_datos_personales(caplog):
    def con_codigo(codigo):
        return _client_with(lambda request: httpx.Response(codigo, json={"detail": "x"}))

    def sin_red(request):
        raise httpx.ConnectError("sin red")

    def rara(request):
        return httpx.Response(200, json={"contact": "no es un objeto"})

    with caplog.at_level(logging.DEBUG, logger="mia_whatsapp"):
        for cliente in (con_codigo(401), con_codigo(404), con_codigo(422), con_codigo(500), _client_with(sin_red), _client_with(rara)):
            resultado = _put(cliente, "provided", name="Ana Pérez", email="ana@correo.com")
            assert resultado.ok is False and resultado.conflict is False
    assert "Ana" not in caplog.text and "ana@correo.com" not in caplog.text and "16315551181" not in caplog.text


def test_un_error_de_contactos_en_el_fake_no_rompe_la_cuenta():
    fake = FakeMia()
    fake.contacts_error = 500
    cliente = _client(fake)

    cuenta = _count(cliente, received=1, phone="16315551181")

    assert cuenta.status == "ok" and cuenta.contact is None
    assert _put(cliente, "claim_invite").ok is False
