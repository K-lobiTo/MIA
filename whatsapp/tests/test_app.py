"""La aplicación: GET /health y POST /webhooks/kapso (firma, evento, lote y confirmación antes de procesar)."""

import asyncio
import json

from fastapi.testclient import TestClient
from support import (
    NUMBER_ID,
    SECRET,
    FakeKapso,
    FakeMia,
    batch_payload,
    kapso_payload,
    make_deps,
    make_settings,
    sign,
    webhook_request,
)

from mia_whatsapp.config import DEFAULT_TEXT_GREETING
from mia_whatsapp.main import create_app


class Recorder:
    """Manejador de mensajes de prueba: anota lo que recibe y si la respuesta ya había salido cuando lo recibió."""

    def __init__(self):
        self.messages = []
        self.sent_when_called = []
        self.sent: list[dict] = []  # lo que la aplicación envió al cliente (solo en las llamadas ASGI a mano)

    async def __call__(self, message, deps):
        self.messages.append(message)
        self.sent_when_called.append(any(m["type"] == "http.response.start" for m in self.sent))


def _app(handler=None, **kwargs):
    return create_app(settings=make_settings(), handler=handler, **kwargs)


def _post(client, payload, **kwargs):
    body, headers = webhook_request(payload, **kwargs)
    return client.post("/webhooks/kapso", content=body, headers=headers)


# --- /health ---------------------------------------------------------------------------------------------------


def test_health_responde_200_sin_llamar_a_nada_externo():
    recorder = Recorder()
    cliente = TestClient(_app(recorder))

    respuesta = cliente.get("/health")

    assert respuesta.status_code == 200 and respuesta.json() == {"status": "ok"}
    assert recorder.messages == []


# --- Firma -----------------------------------------------------------------------------------------------------


def test_una_firma_invalida_o_ausente_responde_401_sin_procesar_nada(capsys):
    recorder = Recorder()
    cliente = TestClient(_app(recorder))
    body, headers = webhook_request(kapso_payload("Mi cédula es 1-2345-6789"))

    sin_firma = {k: v for k, v in headers.items() if k != "x-webhook-signature"}
    mala = {**headers, "x-webhook-signature": sign(body, "otro-secreto")}

    assert cliente.post("/webhooks/kapso", content=body, headers=sin_firma).status_code == 401
    assert cliente.post("/webhooks/kapso", content=body, headers=mala).status_code == 401
    assert recorder.messages == []
    # No se registra el cuerpo de un aviso sin firma válida.
    assert "cédula" not in capsys.readouterr().out


def test_la_firma_es_sobre_el_cuerpo_crudo():
    recorder = Recorder()
    cliente = TestClient(_app(recorder))
    body = json.dumps(kapso_payload(), separators=(",", ":")).encode()
    headers = {"x-webhook-event": "whatsapp.message.received", "x-webhook-signature": sign(body)}

    assert cliente.post("/webhooks/kapso", content=body, headers=headers).status_code == 200
    assert len(recorder.messages) == 1


# --- Eventos y cuerpos -----------------------------------------------------------------------------------------


def test_un_aviso_valido_responde_200_y_se_procesa_el_mensaje():
    recorder = Recorder()
    cliente = TestClient(_app(recorder))

    respuesta = _post(cliente, kapso_payload("¿Cuándo es la matrícula?"))

    assert respuesta.status_code == 200 and respuesta.json() == {"status": "ok"}
    [mensaje] = recorder.messages
    assert mensaje.text == "¿Cuándo es la matrícula?" and mensaje.number_id == NUMBER_ID


def test_un_evento_que_no_es_de_mensaje_recibido_responde_200_y_no_se_procesa():
    recorder = Recorder()
    cliente = TestClient(_app(recorder))

    respuesta = _post(cliente, kapso_payload(), event="whatsapp.message.sent")

    assert respuesta.status_code == 200 and recorder.messages == []


def test_un_cuerpo_ilegible_con_firma_valida_responde_200_y_queda_en_el_registro(capsys):
    recorder = Recorder()
    cliente = TestClient(_app(recorder))
    body = b"esto no es json"
    headers = {"x-webhook-event": "whatsapp.message.received", "x-webhook-signature": sign(body, SECRET)}

    respuesta = cliente.post("/webhooks/kapso", content=body, headers=headers)

    assert respuesta.status_code == 200 and recorder.messages == []
    lineas = [json.loads(l) for l in capsys.readouterr().out.splitlines() if l.startswith("{")]
    assert [l["resultado"] for l in lineas] == ["cuerpo_ilegible"]
    assert "esto no es json" not in json.dumps(lineas)


def test_un_lote_procesa_cada_mensaje():
    recorder = Recorder()
    cliente = TestClient(_app(recorder))
    lote = batch_payload(kapso_payload("uno", message_id="wamid.1"), kapso_payload("dos", message_id="wamid.2"))

    respuesta = _post(cliente, lote)

    assert respuesta.status_code == 200
    assert [m.text for m in recorder.messages] == ["uno", "dos"]


# --- Confirmación inmediata ------------------------------------------------------------------------------------


async def _llamar_asgi(app, body: bytes, headers: dict, recorder: Recorder) -> None:
    """Llama a la aplicación a mano para ver el orden de los mensajes ASGI (el TestClient espera a las tareas de fondo
    antes de devolver, así que no puede demostrar que la respuesta salió primero)."""
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": "/webhooks/kapso",
        "raw_path": b"/webhooks/kapso",
        "query_string": b"",
        "root_path": "",
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
    }

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    async def send(message):
        recorder.sent.append(message)

    await app(scope, receive, send)


def test_el_200_sale_antes_de_que_empiece_a_procesarse_el_mensaje():
    recorder = Recorder()
    app = _app(recorder)
    body, headers = webhook_request(kapso_payload())

    asyncio.run(_llamar_asgi(app, body, headers, recorder))

    start = next(m for m in recorder.sent if m["type"] == "http.response.start")
    assert start["status"] == 200
    # El manejador se ejecutó, y lo hizo cuando la respuesta ya se había enviado.
    assert len(recorder.messages) == 1
    assert recorder.sent_when_called == [True]


def test_el_200_no_espera_a_una_consulta_lenta():
    """Con una consulta que tarda, la confirmación a Kapso (que exige 200 en menos de 10 s) sale igual al principio."""
    orden: list[str] = []

    class Lento(Recorder):
        async def __call__(self, message, deps):
            orden.append("manejador empieza")
            await asyncio.sleep(0.2)  # una consulta lenta
            orden.append("manejador termina")

    recorder = Lento()
    app = _app(recorder)
    body, headers = webhook_request(kapso_payload())

    async def correr():
        original = recorder.sent

        class Lista(list):
            def append(self, item):
                if item["type"] == "http.response.start":
                    orden.append("respuesta enviada")
                super().append(item)

        recorder.sent = Lista(original)
        await _llamar_asgi(app, body, headers, recorder)

    asyncio.run(correr())

    assert orden == ["respuesta enviada", "manejador empieza", "manejador termina"]


# --- De punta a punta con la API y Kapso simulados -------------------------------------------------------------


def test_de_punta_a_punta_un_aviso_firmado_produce_una_respuesta_por_kapso():
    fake_mia, fake_kapso = FakeMia(), FakeKapso()
    deps = make_deps(fake_mia, fake_kapso)
    cliente = TestClient(create_app(settings=deps.settings, api=deps.api, kapso=deps.kapso))

    respuesta = _post(cliente, kapso_payload("¿Cuándo es la matrícula?"))

    assert respuesta.status_code == 200
    assert fake_kapso.texts == [
        f"{DEFAULT_TEXT_GREETING}\n\nLa matrícula es del 3 al 7 de agosto.\n\nFuentes: horario_matricula.pdf"
    ]


def test_la_aplicacion_arranca_y_se_apaga_con_su_ciclo_de_vida():
    with TestClient(_app(Recorder())) as cliente:
        assert cliente.get("/health").status_code == 200


def test_la_limpieza_periodica_del_estado_corre_mientras_la_aplicacion_esta_viva(monkeypatch):
    import time

    from mia_whatsapp import main as main_module

    monkeypatch.setattr(main_module, "CLEANUP_INTERVAL_S", 0.01)
    app = _app(Recorder())
    llamadas = []
    monkeypatch.setattr(app.state.deps.state, "cleanup", lambda: llamadas.append(1))

    with TestClient(app):
        time.sleep(0.15)

    assert len(llamadas) >= 2


def test_el_estado_de_la_aplicacion_tiene_la_cola_de_consultas_de_la_configuracion():
    app = create_app(settings=make_settings(bot_max_concurrent_queries=2, bot_queue_size=7), handler=Recorder())
    gate = app.state.deps.state.gate
    assert gate._queue_size == 7 and gate._semaphore._value == 2


def test_al_arrancar_se_avisa_de_un_texto_cambiado_que_trae_contacto_y_no_se_impide_el_arranque(caplog):
    import logging

    app = create_app(
        settings=make_settings(bot_text_no_info="Escribe a admision@tec.ac.cr"), handler=Recorder()
    )

    with caplog.at_level(logging.WARNING, logger="mia_whatsapp"), TestClient(app) as cliente:
        assert cliente.get("/health").status_code == 200

    mensajes = [r.getMessage() for r in caplog.records]
    assert any("BOT_TEXT_NO_INFO" in m for m in mensajes)


def test_con_los_textos_por_defecto_el_arranque_no_avisa_de_contacto(caplog):
    import logging

    with caplog.at_level(logging.WARNING, logger="mia_whatsapp"), TestClient(_app(Recorder())):
        pass

    assert not any("contacto" in r.getMessage() for r in caplog.records)
