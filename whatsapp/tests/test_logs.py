"""Registro del servicio: una línea JSON por mensaje, sin datos de la persona."""

import json

from mia_whatsapp.logs import log_result


def _lineas(capsys):
    return [json.loads(l) for l in capsys.readouterr().out.splitlines() if l.startswith("{")]


def test_una_linea_json_por_mensaje_con_el_resultado_y_los_tiempos(capsys):
    log_result("respondido", 2310, mensajes_enviados=2, imagenes=1)

    [linea] = _lineas(capsys)
    assert linea == {"evento": "mensaje", "resultado": "respondido", "ms": 2310, "mensajes_enviados": 2, "imagenes": 1}


def test_el_identificador_de_mensaje_se_trunca_a_doce_caracteres(capsys):
    log_result("duplicado", 1, message_id="wamid.HBgLMTYzMTU1NTExODEVAgASGBQz")

    [linea] = _lineas(capsys)
    assert linea["message_id"] == "wamid.HBgLMT" and len(linea["message_id"]) == 12


def test_el_numero_de_la_institucion_solo_aparece_si_se_pide(capsys):
    log_result("bot_desconocido", 3, number_id="647015955153740")
    log_result("respondido", 3)

    con, sin = _lineas(capsys)
    assert con["number_id"] == "647015955153740"
    assert "number_id" not in sin and "message_id" not in sin


def test_la_linea_no_acepta_telefonos_ni_texto_de_la_pregunta(capsys):
    # La función no tiene parámetros para eso: pasarlos es un error de programación, no un dato que se registre.
    import inspect

    nombres = set(inspect.signature(log_result).parameters)
    assert nombres == {"resultado", "ms", "mensajes_enviados", "imagenes", "number_id", "message_id"}
