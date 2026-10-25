"""Los simuladores locales (Kapso falso y envío de avisos firmados): sus funciones, sin abrir puertos."""

import importlib.util
import json
from pathlib import Path

from support import NUMBER_ID, SECRET, sign

from mia_whatsapp.webhook import EVENT, parse_event, verify_signature

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def _cargar(nombre: str):
    spec = importlib.util.spec_from_file_location(nombre, SCRIPTS / f"{nombre}.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


enviar = _cargar("enviar_webhook")
falso = _cargar("kapso_falso")


# --- enviar_webhook --------------------------------------------------------------------------------------------


def test_la_firma_del_script_es_la_que_acepta_el_bot():
    cuerpo = json.dumps(enviar.armar_aviso("hola", NUMBER_ID, "wamid.1"), ensure_ascii=False).encode()
    assert enviar.firmar(cuerpo, SECRET) == sign(cuerpo, SECRET)
    assert verify_signature(cuerpo, enviar.firmar(cuerpo, SECRET), SECRET) is True
    assert verify_signature(cuerpo, enviar.firmar(cuerpo, "otro"), SECRET) is False


def test_el_aviso_del_script_lo_lee_el_bot_con_el_numero_el_id_y_el_texto():
    aviso = enviar.armar_aviso("¿Cuándo es la matrícula?", NUMBER_ID, "wamid.77", persona="ana")
    cuerpo = json.dumps(aviso, ensure_ascii=False).encode()

    [mensaje] = parse_event({"x-webhook-event": EVENT}, cuerpo).messages

    assert mensaje.message_id == "wamid.77" and mensaje.number_id == NUMBER_ID
    assert mensaje.type == "text" and mensaje.text == "¿Cuándo es la matrícula?"
    assert mensaje.destination and mensaje.destination[0] == "to"


def test_la_misma_persona_repite_su_telefono_y_otra_persona_tiene_otro():
    uno = enviar.armar_aviso("a", NUMBER_ID, "1", persona="ana")["message"]["from"]
    otra_vez = enviar.armar_aviso("b", NUMBER_ID, "2", persona="ana")["message"]["from"]
    otra = enviar.armar_aviso("c", NUMBER_ID, "3", persona="beto")["message"]["from"]
    assert uno == otra_vez and uno != otra


def test_el_tipo_distinto_de_texto_no_lleva_texto():
    aviso = enviar.armar_aviso(None, NUMBER_ID, "wamid.1", tipo="audio")
    assert aviso["message"]["type"] == "audio" and "text" not in aviso["message"]


def test_sin_telefono_el_aviso_no_trae_from_ni_telefono_de_la_conversacion_pero_si_el_identificador_de_usuario():
    aviso = enviar.armar_aviso("hola", NUMBER_ID, "wamid.1", persona="ana", sin_telefono=True)
    assert "from" not in aviso["message"] and "phone_number" not in aviso["conversation"]
    [mensaje] = parse_event({"x-webhook-event": EVENT}, json.dumps(aviso).encode()).messages
    assert mensaje.destination and mensaje.destination[0] == "recipient"


def test_sin_secreto_el_script_se_niega_a_enviar(monkeypatch, capsys):
    monkeypatch.delenv("KAPSO_WEBHOOK_SECRET", raising=False)
    assert enviar.main(["--numero", NUMBER_ID, "hola"]) == 2
    assert "secreto" in capsys.readouterr().err


# --- kapso_falso -----------------------------------------------------------------------------------------------


def test_el_kapso_falso_responde_200_con_un_id_y_describe_el_texto():
    cuerpo = json.dumps({"messaging_product": "whatsapp", "to": "506123", "type": "text", "text": {"body": "Hola"}}).encode()

    estado, respuesta, linea = falso.responder(f"/{NUMBER_ID}/messages", cuerpo)

    assert estado == 200 and respuesta["messages"][0]["id"].startswith("wamid.falso.")
    assert "TEXTO" in linea and "506123" in linea and "Hola" in linea and NUMBER_ID in linea


def test_el_kapso_falso_describe_la_imagen_con_su_enlace_y_su_pie_de_foto():
    cuerpo = json.dumps({"to": "506123", "type": "image", "image": {"link": "https://x/media/abc", "caption": "Horario"}}).encode()

    estado, _, linea = falso.responder(f"/{NUMBER_ID}/messages", cuerpo)

    assert estado == 200 and "IMAGEN" in linea and "https://x/media/abc" in linea and "Horario" in linea


def test_con_fallar_imagenes_rechaza_solo_las_imagenes():
    imagen = json.dumps({"to": "1", "type": "image", "image": {"link": "https://x/m"}}).encode()
    texto = json.dumps({"to": "1", "type": "text", "text": {"body": "hola"}}).encode()

    assert falso.responder(f"/{NUMBER_ID}/messages", imagen, fallar_imagenes=True)[0] == 400
    assert falso.responder(f"/{NUMBER_ID}/messages", texto, fallar_imagenes=True)[0] == 200


def test_el_kapso_falso_describe_un_destino_por_identificador_de_usuario():
    cuerpo = json.dumps({"recipient": "US.123", "recipient_type": "individual", "type": "text", "text": {"body": "x"}}).encode()
    assert "US.123" in falso.responder(f"/{NUMBER_ID}/messages", cuerpo)[2]


def test_el_kapso_falso_no_falla_con_rutas_o_cuerpos_raros():
    assert falso.responder("/otra/cosa", b"{}")[0] == 404
    assert falso.responder(f"/{NUMBER_ID}/messages", b"no es json")[0] == 400


def test_los_ids_de_los_mensajes_del_kapso_falso_no_se_repiten():
    cuerpo = json.dumps({"to": "1", "type": "text", "text": {"body": "x"}}).encode()
    ids = {falso.responder(f"/{NUMBER_ID}/messages", cuerpo)[1]["messages"][0]["id"] for _ in range(5)}
    assert len(ids) == 5
