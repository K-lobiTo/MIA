"""Verificación de la firma y lectura del aviso de Kapso (whatsapp.message.received)."""

import json

import pytest
from support import NUMBER_ID, SECRET, batch_payload, kapso_payload, sign

from mia_whatsapp.webhook import EVENT, parse_event, verify_signature

HEADERS = {"x-webhook-event": EVENT, "x-idempotency-key": "k1"}


def _body(payload) -> bytes:
    return json.dumps(payload, ensure_ascii=False).encode()


# --- verify_signature ------------------------------------------------------------------------------------------


def test_la_firma_correcta_es_el_hmac_sha256_hexadecimal_del_cuerpo_crudo():
    body = _body(kapso_payload())
    assert verify_signature(body, sign(body), SECRET) is True


def test_firma_ausente_vacia_de_otra_longitud_o_invalida_es_falsa():
    body = _body(kapso_payload())
    assert verify_signature(body, None, SECRET) is False
    assert verify_signature(body, "", SECRET) is False
    assert verify_signature(body, "abc123", SECRET) is False
    assert verify_signature(body, sign(body, "otro-secreto"), SECRET) is False
    assert verify_signature(body, sign(body)[:-1] + "0", SECRET) is False


def test_la_firma_es_sobre_el_cuerpo_crudo_y_no_sobre_el_json_reserializado():
    # Mismo JSON pero con otros espacios: la firma del primero no vale para el segundo.
    compacto = json.dumps(kapso_payload(), separators=(",", ":"), ensure_ascii=False).encode()
    con_espacios = json.dumps(kapso_payload(), ensure_ascii=False).encode()
    assert compacto != con_espacios
    assert verify_signature(compacto, sign(compacto), SECRET) is True
    assert verify_signature(con_espacios, sign(compacto), SECRET) is False


def test_un_secreto_vacio_nunca_verifica():
    body = _body(kapso_payload())
    assert verify_signature(body, sign(body, ""), "") is False


# --- parse_event -----------------------------------------------------------------------------------------------


def test_un_aviso_de_texto_se_interpreta():
    resultado = parse_event(HEADERS, _body(kapso_payload("¿Cuándo es la matrícula?")))

    assert not resultado.unreadable and resultado.ignored_event is None
    [mensaje] = resultado.messages
    assert mensaje.message_id == "wamid.123" and mensaje.type == "text"
    assert mensaje.text == "¿Cuándo es la matrícula?"
    assert mensaje.number_id == NUMBER_ID
    assert mensaje.idempotency_key == "k1"
    assert mensaje.destination == ("to", "16315551181")


def test_la_clave_de_persona_es_un_hash_y_no_contiene_el_telefono_ni_el_identificador():
    [mensaje] = parse_event(HEADERS, _body(kapso_payload())).messages
    assert mensaje.person_key and len(mensaje.person_key) == 32
    assert "16315551181" not in mensaje.person_key and "US.1349" not in mensaje.person_key
    # La misma persona da la misma clave; otra persona, otra.
    [igual] = parse_event(HEADERS, _body(kapso_payload("otra pregunta", message_id="wamid.999"))).messages
    [otra] = parse_event(HEADERS, _body(kapso_payload(user_id="US.0000", phone="506111"))).messages
    assert igual.person_key == mensaje.person_key and otra.person_key != mensaje.person_key


def test_el_numero_de_la_institucion_se_toma_de_phone_number_id_o_de_la_conversacion():
    solo_conversacion = kapso_payload()
    del solo_conversacion["phone_number_id"]
    [mensaje] = parse_event(HEADERS, _body(solo_conversacion)).messages
    assert mensaje.number_id == NUMBER_ID


def test_el_destino_es_el_telefono_del_mensaje_y_si_falta_el_de_la_conversacion():
    [a] = parse_event(HEADERS, _body(kapso_payload(phone="111", conversation_phone="222"))).messages
    assert a.destination == ("to", "111")
    [b] = parse_event(HEADERS, _body(kapso_payload(phone=None, conversation_phone="222"))).messages
    assert b.destination == ("to", "222")


def test_sin_telefono_el_destino_es_el_identificador_de_usuario():
    [mensaje] = parse_event(HEADERS, _body(kapso_payload(phone=None, conversation_phone=None))).messages
    assert mensaje.destination == ("recipient", "US.13491208655302741918")


def test_sin_ningun_dato_de_destino_no_falla_y_no_hay_destino():
    [mensaje] = parse_event(
        HEADERS, _body(kapso_payload(phone=None, conversation_phone=None, user_id=None, conversation_id="c1"))
    ).messages
    assert mensaje.destination is None and mensaje.person_key  # la conversación identifica a la persona


def test_sin_ningun_identificador_no_hay_clave_de_persona():
    [mensaje] = parse_event(
        HEADERS, _body(kapso_payload(phone=None, conversation_phone=None, user_id=None, conversation_id=None))
    ).messages
    assert mensaje.person_key is None and mensaje.destination is None


@pytest.mark.parametrize("tipo", ["audio", "image", "sticker", "document", "location"])
def test_un_mensaje_que_no_es_texto_se_lee_con_su_tipo_y_sin_texto(tipo):
    [mensaje] = parse_event(HEADERS, _body(kapso_payload(None, type=tipo))).messages
    assert mensaje.type == tipo and mensaje.text is None


def test_un_lote_produce_un_mensaje_por_elemento_y_no_hereda_la_clave_de_idempotencia():
    lote = batch_payload(
        kapso_payload("uno", message_id="wamid.1"),
        kapso_payload("dos", message_id="wamid.2", phone="999", user_id="US.2", conversation_phone="999"),
    )

    resultado = parse_event(HEADERS, _body(lote))

    assert [m.message_id for m in resultado.messages] == ["wamid.1", "wamid.2"]
    assert [m.text for m in resultado.messages] == ["uno", "dos"]
    assert all(m.idempotency_key is None for m in resultado.messages)
    assert resultado.messages[0].person_key != resultado.messages[1].person_key


def test_un_evento_que_no_es_de_mensaje_recibido_se_ignora():
    resultado = parse_event({"x-webhook-event": "whatsapp.message.sent"}, _body(kapso_payload()))
    assert resultado.messages == [] and resultado.ignored_event == "whatsapp.message.sent"
    sin_evento = parse_event({}, _body(kapso_payload()))
    assert sin_evento.messages == [] and sin_evento.ignored_event == ""


def test_un_cuerpo_ilegible_no_lanza_y_se_marca_como_ilegible():
    for cuerpo in (b"no es json", b"", b"\xff\xfe", b"[1, 2]", b'"texto"'):
        resultado = parse_event(HEADERS, cuerpo)
        assert resultado.messages == [] and resultado.unreadable is True


def test_un_aviso_sin_mensaje_o_sin_numero_de_institucion_se_descarta_sin_fallar():
    assert parse_event(HEADERS, _body({"conversation": {}})).messages == []
    assert parse_event(HEADERS, _body(kapso_payload(number_id=None))).messages == []
    sin_id = kapso_payload()
    del sin_id["message"]["id"]
    assert parse_event(HEADERS, _body(sin_id)).messages == []
    mal_formado = {"message": "no es un objeto", "phone_number_id": NUMBER_ID}
    assert parse_event(HEADERS, _body(mal_formado)).messages == []


def test_un_mensaje_saliente_no_se_procesa():
    saliente = kapso_payload()
    saliente["message"]["kapso"] = {"direction": "outbound"}
    assert parse_event(HEADERS, _body(saliente)).messages == []


def test_los_encabezados_se_leen_sin_importar_las_mayusculas():
    [mensaje] = parse_event(
        {"X-Webhook-Event": EVENT, "X-Idempotency-Key": "K9"}, _body(kapso_payload())
    ).messages
    assert mensaje.idempotency_key == "K9"
