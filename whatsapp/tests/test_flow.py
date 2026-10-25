"""El flujo de cada mensaje con la API de MIA, Kapso y el reloj simulados (contracts/servicio-whatsapp.md)."""

import asyncio
import json

import httpx
import pytest
from support import NUMBER_ID, FakeClock, FakeMia, make_deps, make_message

from mia_whatsapp.config import (
    DEFAULT_TEXT_GREETING,
    DEFAULT_TEXT_NO_INFO,
    DEFAULT_TEXT_NOT_TEXT,
    DEFAULT_TEXT_TOO_LONG,
    DEFAULT_TEXT_UNAVAILABLE,
)
from mia_whatsapp.flow import handle_message
from mia_whatsapp.kapso import KapsoClient


def run(deps, message):
    asyncio.run(handle_message(message, deps))


def lineas(capsys):
    return [json.loads(l) for l in capsys.readouterr().out.splitlines() if l.startswith("{")]


def api_calls(fake_mia: FakeMia) -> list[tuple[str, dict]]:
    return [(r["path"].removeprefix("/bot/"), r["json"]) for r in fake_mia.recorded.requests]


@pytest.fixture
def mundo(fake_mia, fake_kapso):
    return fake_mia, fake_kapso, make_deps(fake_mia, fake_kapso)


# --- Una pregunta con respuesta --------------------------------------------------------------------------------


def test_una_pregunta_cuenta_consulta_responde_con_saludo_texto_y_fuentes_y_cuenta_lo_enviado(mundo, capsys):
    fake_mia, fake_kapso, deps = mundo

    run(deps, make_message())

    assert api_calls(fake_mia) == [
        ("messages", {"number_id": NUMBER_ID, "received": 1, "sent": 0}),
        ("query", {"number_id": NUMBER_ID, "question": "¿Cuándo es la matrícula?"}),
        ("messages", {"number_id": NUMBER_ID, "received": 0, "sent": 1}),
    ]
    assert fake_kapso.texts == [
        f"{DEFAULT_TEXT_GREETING}\n\nLa matrícula es del 3 al 7 de agosto.\n\nFuentes: horario_matricula.pdf"
    ]
    assert fake_kapso.recorded.requests[0]["json"]["to"] == "16315551181"
    [linea] = lineas(capsys)
    assert linea["resultado"] == "respondido" and linea["mensajes_enviados"] == 1 and linea["imagenes"] == 0
    assert linea["message_id"] == "wamid.1"


def test_la_respuesta_del_modelo_se_envia_en_formato_de_whatsapp(mundo):
    fake_mia, fake_kapso, deps = mundo
    fake_mia.query_body["answer"] = "## Requisitos\n\n**Título** y *cédula*"

    run(deps, make_message())

    assert "*Requisitos*" in fake_kapso.texts[0] and "*Título* y _cédula_" in fake_kapso.texts[0]
    assert "##" not in fake_kapso.texts[0] and "**" not in fake_kapso.texts[0]


def test_la_segunda_pregunta_de_la_misma_persona_en_24_horas_no_repite_el_saludo(mundo):
    _, fake_kapso, deps = mundo

    run(deps, make_message(message_id="wamid.1"))
    run(deps, make_message(message_id="wamid.2"))

    assert DEFAULT_TEXT_GREETING in fake_kapso.texts[0]
    assert DEFAULT_TEXT_GREETING not in fake_kapso.texts[1]
    assert fake_kapso.texts[1].startswith("La matrícula es del 3 al 7 de agosto.")


def test_pasadas_24_horas_se_vuelve_a_saludar(fake_mia, fake_kapso):
    reloj = FakeClock()
    deps = make_deps(fake_mia, fake_kapso, reloj)

    run(deps, make_message(message_id="wamid.1"))
    reloj.now += 24 * 3600 + 1
    run(deps, make_message(message_id="wamid.2"))

    assert all(DEFAULT_TEXT_GREETING in t for t in fake_kapso.texts)


def test_otra_persona_recibe_su_propio_saludo(mundo):
    _, fake_kapso, deps = mundo

    run(deps, make_message(message_id="wamid.1", person_key="persona-1"))
    run(deps, make_message(message_id="wamid.2", person_key="persona-2"))

    assert all(DEFAULT_TEXT_GREETING in t for t in fake_kapso.texts)


# --- Duplicados ------------------------------------------------------------------------------------------------


def test_un_mensaje_repetido_se_responde_una_sola_vez(mundo, capsys):
    fake_mia, fake_kapso, deps = mundo

    run(deps, make_message(message_id="wamid.1"))
    run(deps, make_message(message_id="wamid.1"))

    assert len(fake_kapso.texts) == 1
    assert len([c for c in api_calls(fake_mia) if c[0] == "query"]) == 1
    assert [l["resultado"] for l in lineas(capsys)] == ["respondido", "duplicado"]


def test_la_misma_clave_de_idempotencia_con_otro_id_tambien_es_un_duplicado(mundo):
    _, fake_kapso, deps = mundo

    run(deps, make_message(message_id="wamid.1", idempotency_key="entrega-7"))
    run(deps, make_message(message_id="wamid.2", idempotency_key="entrega-7"))

    assert len(fake_kapso.texts) == 1


def test_un_duplicado_no_cuenta_ni_consulta_ni_envia(mundo):
    fake_mia, fake_kapso, deps = mundo
    run(deps, make_message(message_id="wamid.1"))
    antes = (len(fake_mia.recorded.requests), len(fake_kapso.recorded.requests))

    run(deps, make_message(message_id="wamid.1"))

    assert (len(fake_mia.recorded.requests), len(fake_kapso.recorded.requests)) == antes


# --- Estados de la cuenta --------------------------------------------------------------------------------------


def test_un_numero_sin_bot_se_ignora_y_el_registro_dice_cual_es(mundo, capsys):
    fake_mia, fake_kapso, deps = mundo
    fake_mia.status = "unknown_bot"

    run(deps, make_message())

    assert fake_kapso.recorded.requests == []
    assert [c[0] for c in api_calls(fake_mia)] == ["messages"]
    [linea] = lineas(capsys)
    assert linea["resultado"] == "bot_desconocido" and linea["number_id"] == NUMBER_ID


def test_con_el_tope_mensual_alcanzado_no_se_consulta_ni_se_envia_nada(mundo, capsys):
    fake_mia, fake_kapso, deps = mundo
    fake_mia.status = "cap_reached"

    run(deps, make_message())

    assert fake_kapso.recorded.requests == []
    assert [c[0] for c in api_calls(fake_mia)] == ["messages"]  # el mensaje recibido sí se contó
    assert lineas(capsys)[0]["resultado"] == "tope_mensual"


def test_un_bot_desactivado_responde_solo_el_aviso_de_no_disponible(mundo):
    fake_mia, fake_kapso, deps = mundo
    fake_mia.status = "disabled"

    run(deps, make_message())

    assert fake_kapso.texts == [f"{DEFAULT_TEXT_GREETING}\n\n{DEFAULT_TEXT_UNAVAILABLE}"]
    assert [c[0] for c in api_calls(fake_mia)] == ["messages", "messages"]  # recibido y enviado, sin consulta
    assert api_calls(fake_mia)[1][1]["sent"] == 1


def test_un_error_de_la_api_al_contar_no_responde_nada(mundo, capsys):
    fake_mia, fake_kapso, deps = mundo
    fake_mia.counts_error = 500

    run(deps, make_message())

    assert fake_kapso.recorded.requests == []
    assert lineas(capsys)[0]["resultado"] == "error_api"


# --- Sin información y fallas ----------------------------------------------------------------------------------


def test_sin_informacion_responde_el_texto_fijo_sin_fuentes(mundo, capsys):
    fake_mia, fake_kapso, deps = mundo
    fake_mia.query_body.update({"no_info": True, "sources": [], "answer": "No encontré información suficiente"})

    run(deps, make_message())

    assert fake_kapso.texts == [f"{DEFAULT_TEXT_GREETING}\n\n{DEFAULT_TEXT_NO_INFO}"]
    assert "Fuentes" not in fake_kapso.texts[0]
    assert lineas(capsys)[0]["resultado"] == "sin_informacion"


@pytest.mark.parametrize("codigo", [403, 429, 502, 500])
def test_un_rechazo_o_una_falla_de_la_api_responde_no_disponible_sin_reintentar(fake_mia, fake_kapso, codigo, capsys):
    fake_mia.query_status = codigo
    deps = make_deps(fake_mia, fake_kapso)

    run(deps, make_message())

    assert fake_kapso.texts == [f"{DEFAULT_TEXT_GREETING}\n\n{DEFAULT_TEXT_UNAVAILABLE}"]
    assert len([c for c in api_calls(fake_mia) if c[0] == "query"]) == 1
    assert lineas(capsys)[0]["resultado"] == "no_disponible"


def test_el_tiempo_agotado_de_la_consulta_responde_no_disponible(fake_mia, fake_kapso):
    import httpx

    from mia_whatsapp.api_client import MiaApiClient

    def lenta(request):
        if request.url.path.endswith("/bot/messages"):
            return httpx.Response(200, json={"status": "ok", "month": "2026-10", "month_messages": 1, "month_cap": 1800})
        raise httpx.ReadTimeout("tarda demasiado")

    deps = make_deps(fake_mia, fake_kapso)
    deps.api = MiaApiClient(deps.settings, httpx.AsyncClient(transport=httpx.MockTransport(lenta)))

    run(deps, make_message())

    assert fake_kapso.texts[0].endswith(DEFAULT_TEXT_UNAVAILABLE)


def test_la_pregunta_se_envia_sin_los_espacios_de_los_bordes(mundo):
    fake_mia, _, deps = mundo

    run(deps, make_message(text="   ¿Cuándo es la matrícula?  \n"))

    assert api_calls(fake_mia)[1][1]["question"] == "¿Cuándo es la matrícula?"


# --- Respuestas largas -----------------------------------------------------------------------------------------


def test_una_respuesta_larga_se_envia_en_varios_mensajes_en_orden_y_se_cuentan_todos(mundo):
    fake_mia, fake_kapso, deps = mundo
    parrafos = [f"Párrafo {i}. " + "palabra " * 150 for i in range(8)]  # ~1.300 caracteres cada uno
    fake_mia.query_body["answer"] = "\n\n".join(parrafos)

    run(deps, make_message())

    assert len(fake_kapso.texts) > 1
    assert all(len(t) <= 4000 for t in fake_kapso.texts)
    # El saludo va solo en el primero y las fuentes al final del último.
    assert fake_kapso.texts[0].startswith(DEFAULT_TEXT_GREETING)
    assert all(DEFAULT_TEXT_GREETING not in t for t in fake_kapso.texts[1:])
    assert fake_kapso.texts[-1].endswith("Fuentes: horario_matricula.pdf")
    unido = "\n\n".join(fake_kapso.texts)
    posiciones = [unido.index(f"Párrafo {i}.") for i in range(8)]
    assert posiciones == sorted(posiciones)
    assert api_calls(fake_mia)[-1] == ("messages", {"number_id": NUMBER_ID, "received": 0, "sent": len(fake_kapso.texts)})


# --- Destino y fallas de envío ---------------------------------------------------------------------------------


def test_sin_destino_no_se_envia_nada_y_se_registra(mundo, capsys):
    fake_mia, fake_kapso, deps = mundo

    run(deps, make_message(destination=None))

    assert fake_kapso.recorded.requests == []
    assert lineas(capsys)[0]["resultado"] == "sin_destino"
    assert all(c[1]["sent"] == 0 for c in api_calls(fake_mia) if c[0] == "messages")


def test_sin_telefono_se_responde_al_identificador_de_usuario(mundo):
    _, fake_kapso, deps = mundo

    run(deps, make_message(destination=("recipient", "US.13491208655302741918")))

    cuerpo = fake_kapso.recorded.requests[0]["json"]
    assert cuerpo["recipient"] == "US.13491208655302741918" and "to" not in cuerpo


def test_si_kapso_rechaza_el_texto_no_se_marca_el_saludo_ni_se_cuenta_lo_no_enviado(fake_mia, fake_kapso, capsys):
    fake_kapso.status = 400
    deps = make_deps(fake_mia, fake_kapso)

    run(deps, make_message(message_id="wamid.1"))

    assert lineas(capsys)[0]["resultado"] == "error_envio"
    assert all(c[1]["sent"] == 0 for c in api_calls(fake_mia) if c[0] == "messages")
    # La persona no recibió nada: en el próximo mensaje se le saluda.
    fake_kapso.status = 200
    run(deps, make_message(message_id="wamid.2"))
    assert DEFAULT_TEXT_GREETING in fake_kapso.texts[-1]


# --- Robustez --------------------------------------------------------------------------------------------------


def test_un_error_inesperado_no_se_propaga_y_queda_registrado(mundo, capsys):
    _, fake_kapso, deps = mundo

    def falla(*args, **kwargs):
        raise RuntimeError("bug imprevisto")

    deps.api.count_messages = falla

    run(deps, make_message())  # no lanza

    assert fake_kapso.recorded.requests == []
    assert lineas(capsys)[0]["resultado"] == "error_interno"


def test_la_linea_del_registro_no_trae_telefonos_ni_texto(mundo, capsys):
    _, _, deps = mundo

    run(deps, make_message(text="Mi cédula es 1-2345-6789, ¿cuándo es la matrícula?"))

    salida = capsys.readouterr().out
    assert "16315551181" not in salida and "cédula" not in salida and "matrícula" not in salida


# --- Imágenes --------------------------------------------------------------------------------------------------

IMAGENES = [
    {"url": "/media/aaa", "caption": "Horario de matrícula", "document": "horario_matricula.pdf"},
    {"url": "/media/bbb", "caption": "Detalle", "document": "horario_matricula.pdf"},
    {"url": "/media/ccc", "caption": "", "document": "otro.pdf"},
]


def test_tras_el_texto_se_envia_la_primera_imagen_con_su_descripcion_como_pie_de_foto(fake_mia, fake_kapso, capsys):
    fake_mia.query_body["images"] = IMAGENES
    deps = make_deps(fake_mia, fake_kapso)

    run(deps, make_message())

    assert len(fake_kapso.texts) == 1
    # Por defecto el bot envía una sola imagen por respuesta, la primera en el orden de la API.
    assert fake_kapso.images == [{"link": "https://mia.example.com/media/aaa", "caption": "Horario de matrícula"}]
    # El texto sale antes que la imagen.
    assert [m["type"] for m in fake_kapso.messages] == ["text", "image"]
    # Se cuenta todo lo enviado: el texto y la imagen.
    assert api_calls(fake_mia)[-1] == ("messages", {"number_id": NUMBER_ID, "received": 0, "sent": 2})
    linea = lineas(capsys)[0]
    assert linea["resultado"] == "respondido" and linea["mensajes_enviados"] == 2 and linea["imagenes"] == 1


def test_con_mas_imagenes_permitidas_se_envian_en_el_orden_recibido(fake_mia, fake_kapso):
    fake_mia.query_body["images"] = IMAGENES
    deps = make_deps(fake_mia, fake_kapso, bot_max_images=2)

    run(deps, make_message())

    assert [i["link"] for i in fake_kapso.images] == [
        "https://mia.example.com/media/aaa", "https://mia.example.com/media/bbb",
    ]
    assert api_calls(fake_mia)[-1][1]["sent"] == 3


def test_con_cero_imagenes_permitidas_no_se_envia_ninguna(fake_mia, fake_kapso):
    fake_mia.query_body["images"] = IMAGENES
    deps = make_deps(fake_mia, fake_kapso, bot_max_images=0)

    run(deps, make_message())

    assert fake_kapso.images == []
    assert api_calls(fake_mia)[-1][1]["sent"] == 1


def test_una_respuesta_sin_informacion_o_de_no_disponible_no_envia_imagenes(fake_mia, fake_kapso):
    fake_mia.query_body.update({"no_info": True, "images": IMAGENES})
    deps = make_deps(fake_mia, fake_kapso)
    run(deps, make_message(message_id="wamid.1"))

    fake_mia.query_body["no_info"] = False
    fake_mia.query_status = 429
    run(deps, make_message(message_id="wamid.2"))

    assert fake_kapso.images == []


def test_si_una_imagen_falla_el_texto_se_conserva_el_resultado_lo_registra_y_se_siguen_enviando_las_demas(
    fake_mia, fake_kapso, capsys
):
    fake_mia.query_body["images"] = IMAGENES
    deps = make_deps(fake_mia, fake_kapso, bot_max_images=2)
    codigos = iter([400, 200])  # la primera imagen falla; la segunda sale

    def handler(request):
        entrada = fake_kapso.recorded.add(request)
        if entrada["json"]["type"] == "image":
            codigo = next(codigos)
            return httpx.Response(codigo, json={"error": {"message": "falló"}} if codigo >= 400 else {})
        return httpx.Response(200, json={})

    deps.kapso = KapsoClient(deps.settings, httpx.AsyncClient(transport=httpx.MockTransport(handler)))

    run(deps, make_message())

    tipos = [r["json"]["type"] for r in fake_kapso.recorded.requests]
    assert tipos == ["text", "image", "image"]  # la imagen que falló no frena a la siguiente
    linea = lineas(capsys)[0]
    assert linea["resultado"] == "imagen_fallida"
    # Cuenta solo lo realmente enviado: el texto y la segunda imagen.
    assert linea["mensajes_enviados"] == 2 and linea["imagenes"] == 1
    assert api_calls(fake_mia)[-1][1]["sent"] == 2


# --- Lo que no es una pregunta de texto razonable (historia 6) -------------------------------------------------


@pytest.mark.parametrize("tipo", ["audio", "image", "sticker", "document", "location", "video"])
def test_un_mensaje_que_no_es_texto_recibe_el_pedido_de_escribir_la_pregunta_sin_consultar_a_la_api(fake_mia, fake_kapso, tipo, capsys):
    deps = make_deps(fake_mia, fake_kapso)

    run(deps, make_message(type=tipo, text=None))

    assert fake_kapso.texts == [f"{DEFAULT_TEXT_GREETING}\n\n{DEFAULT_TEXT_NOT_TEXT}"]
    assert [c[0] for c in api_calls(fake_mia)] == ["messages", "messages"]  # recibido y enviado, sin consulta (sin modelo)
    assert api_calls(fake_mia)[0][1]["received"] == 1 and api_calls(fake_mia)[1][1]["sent"] == 1
    assert lineas(capsys)[0]["resultado"] == "no_texto"


def test_un_texto_de_solo_espacios_o_vacio_se_trata_como_si_no_fuera_texto(fake_mia, fake_kapso, capsys):
    deps = make_deps(fake_mia, fake_kapso)

    run(deps, make_message(message_id="wamid.1", text="   \n "))
    run(deps, make_message(message_id="wamid.2", text=None))

    assert resultados_de(capsys) == ["no_texto", "no_texto"]
    assert all(c[0] != "query" for c in api_calls(fake_mia))


def resultados_de(capsys):
    return [l["resultado"] for l in lineas(capsys)]


def test_un_texto_de_mas_de_500_caracteres_recibe_el_pedido_de_resumirlo_sin_consultar_a_la_api(fake_mia, fake_kapso, capsys):
    deps = make_deps(fake_mia, fake_kapso)

    run(deps, make_message(text="a" * 501))

    assert fake_kapso.texts == [f"{DEFAULT_TEXT_GREETING}\n\n{DEFAULT_TEXT_TOO_LONG}"]
    assert all(c[0] != "query" for c in api_calls(fake_mia))
    assert lineas(capsys)[0]["resultado"] == "muy_largo"


def test_un_texto_de_exactamente_500_caracteres_si_se_consulta(fake_mia, fake_kapso):
    deps = make_deps(fake_mia, fake_kapso)

    run(deps, make_message(text="a" * 500))

    assert [c[0] for c in api_calls(fake_mia)] == ["messages", "query", "messages"]


def test_el_largo_maximo_de_la_pregunta_es_configurable(fake_mia, fake_kapso):
    deps = make_deps(fake_mia, fake_kapso, bot_max_question_chars=50)

    run(deps, make_message(message_id="wamid.1", text="a" * 51))
    run(deps, make_message(message_id="wamid.2", text="a" * 50))

    assert fake_kapso.texts[0].endswith(DEFAULT_TEXT_TOO_LONG)
    assert [c[0] for c in api_calls(fake_mia)].count("query") == 1


def test_el_largo_se_mide_sin_los_espacios_de_los_bordes(fake_mia, fake_kapso):
    deps = make_deps(fake_mia, fake_kapso)

    run(deps, make_message(text="  " + "a" * 500 + "  \n"))

    assert any(c[0] == "query" for c in api_calls(fake_mia))


def test_el_saludo_solo_va_en_la_primera_respuesta_aunque_sea_de_un_aviso(fake_mia, fake_kapso):
    deps = make_deps(fake_mia, fake_kapso)

    run(deps, make_message(message_id="wamid.1", type="audio", text=None))
    run(deps, make_message(message_id="wamid.2", text="a" * 501))
    run(deps, make_message(message_id="wamid.3"))

    assert DEFAULT_TEXT_GREETING in fake_kapso.texts[0]
    assert DEFAULT_TEXT_GREETING not in fake_kapso.texts[1] and DEFAULT_TEXT_GREETING not in fake_kapso.texts[2]


def test_sin_destino_el_aviso_de_no_texto_no_se_envia_y_se_registra(fake_mia, fake_kapso, capsys):
    deps = make_deps(fake_mia, fake_kapso)

    run(deps, make_message(type="audio", text=None, destination=None))

    assert fake_kapso.recorded.requests == [] and lineas(capsys)[0]["resultado"] == "sin_destino"


def test_el_texto_de_sin_informacion_sugiere_otros_temas_y_no_da_el_contacto(fake_mia, fake_kapso):
    fake_mia.query_body.update({"no_info": True, "sources": [], "images": [
        {"url": "/media/x", "caption": "no debe salir", "document": "d.pdf"}
    ]})
    deps = make_deps(fake_mia, fake_kapso)

    run(deps, make_message())

    texto = fake_kapso.texts[0].lower()
    assert "otras palabras" in texto and "matrícula" in texto and "requisitos" in texto and "plan de estudios" in texto
    assert "@" not in texto and "http" not in texto and "teléfono" not in texto and "correo" not in texto
    assert fake_kapso.images == []


def test_los_textos_se_pueden_cambiar_por_configuracion_sin_tocar_el_codigo(fake_mia, fake_kapso):
    deps = make_deps(
        fake_mia, fake_kapso, bot_text_greeting="Hola desde Analítica.", bot_text_not_text="Escribe, por favor."
    )

    run(deps, make_message(type="audio", text=None))

    assert fake_kapso.texts == ["Hola desde Analítica.\n\nEscribe, por favor."]
