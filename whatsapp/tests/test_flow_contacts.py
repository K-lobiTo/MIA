# ruff: noqa: RUF059
"""El flujo con datos de contacto (feature 017, contracts/servicio-contactos.md): invitación aparte tras la primera respuesta,
datos, negativa, borrado, reapertura, apagado, fallas y privacidad."""

import asyncio
import json
import logging

import pytest
from support import FakeClock, make_deps, make_message

from mia_whatsapp.config import (
    DEFAULT_TEXT_CONTACT_DECLINED,
    DEFAULT_TEXT_CONTACT_ERASED,
    DEFAULT_TEXT_CONTACT_INVITE,
    DEFAULT_TEXT_CONTACT_NO_DATA,
    DEFAULT_TEXT_CONTACT_WHY,
    DEFAULT_TEXT_GREETING,
)
from mia_whatsapp.flow import handle_message
from mia_whatsapp.kapso import SendResult

TEL = "16315551181"
TEL_NORMAL = "+16315551181"
INVITE = DEFAULT_TEXT_CONTACT_INVITE
RESPUESTA = "La matrícula es del 3 al 7 de agosto."
PREGUNTA = "¿Cuándo es la matrícula?"
DATOS = "Ana Pérez ana@correo.com"
PERSONALES = ("Ana Pérez", "ana@correo.com", TEL, "6315551181")


def run(deps, message):
    asyncio.run(handle_message(message, deps))


def lineas(capsys):
    return [json.loads(l) for l in capsys.readouterr().out.splitlines() if l.startswith("{")]


def sin_informacion():
    return {
        "id": "q", "answer": "No encontré información suficiente", "sources": [], "mode": "literal", "latency_ms": 10,
        "no_info": True, "images": [], "clarify": [], "programs": [],
    }


@pytest.fixture
def mundo(fake_mia, fake_kapso):
    deps = make_deps(fake_mia, fake_kapso, FakeClock(), bot_contact="on")
    return fake_mia, fake_kapso, deps


def escribir(deps, texto, persona="persona-1", phone=TEL, message_id=None, **extra):
    run(deps, make_message(text=texto, person_key=persona, phone=phone, message_id=message_id or f"w.{persona}.{texto}", **extra))


def preguntas(fake_mia):
    return [r["json"]["question"] for r in fake_mia.recorded.to("/bot/query")]


def contacto(fake_mia, phone=TEL):
    return fake_mia.contact(phone)


# --- US1: la invitación y los datos ---


def test_la_primera_pregunta_se_responde_y_aparte_llega_la_invitacion(mundo):
    fake_mia, fake_kapso, deps = mundo

    escribir(deps, PREGUNTA)

    assert len(fake_kapso.texts) == 2
    assert RESPUESTA in fake_kapso.texts[0] and DEFAULT_TEXT_GREETING in fake_kapso.texts[0]
    # La invitación va aparte, sin saludo, y dice que es opcional.
    assert fake_kapso.texts[1] == INVITE and "opcional" in INVITE.lower()
    assert contacto(fake_mia)["status"] == "invitada"
    assert fake_mia.recorded.to("/bot/messages")[0]["json"]["phone"] == TEL
    # La cuota cuenta la respuesta y la invitación.
    assert sum(r["json"]["sent"] for r in fake_mia.recorded.to("/bot/messages")) == 2


def test_el_orden_es_la_respuesta_y_despues_la_invitacion(mundo):
    fake_mia, fake_kapso, deps = mundo
    escribir(deps, PREGUNTA)
    assert fake_kapso.texts.index(INVITE) == 1 and RESPUESTA in fake_kapso.texts[0]


def test_nombre_y_correo_se_guardan_se_confirman_y_no_llegan_a_la_consulta(mundo, capsys):
    fake_mia, fake_kapso, deps = mundo
    escribir(deps, PREGUNTA)
    capsys.readouterr()

    escribir(deps, DATOS)

    assert fake_kapso.texts[-1].startswith("Listo, guardé tu nombre (Ana Pérez) y tu correo (a**@correo.com)")
    assert "ana@correo.com" not in fake_kapso.texts[-1]
    c = contacto(fake_mia)
    assert (c["status"], c["name"], c["email"]) == ("entrego", "Ana Pérez", "ana@correo.com")
    assert preguntas(fake_mia) == [PREGUNTA]  # el mensaje con los datos no se consultó
    [linea] = lineas(capsys)
    assert linea["resultado"] == "contacto_entregado" and linea["contacto"] == "entregado"
    assert len(fake_kapso.texts) == 3  # respuesta, invitación y confirmación


def test_el_mensaje_de_datos_no_entra_al_contexto_de_la_aclaracion(mundo):
    fake_mia, fake_kapso, deps = mundo
    escribir(deps, PREGUNTA)
    escribir(deps, DATOS)
    turnos = deps.state.conversations.turns("persona-1")
    assert all("ana@correo.com" not in t.text for t in turnos)


@pytest.mark.parametrize(("texto", "nombre", "correo"), [("ana@correo.com", None, "ana@correo.com"), ("Soy Ana Solís", "Ana Solís", None)])
def test_solo_un_dato_tambien_se_guarda_y_no_se_insiste(mundo, texto, nombre, correo):
    fake_mia, fake_kapso, deps = mundo
    escribir(deps, PREGUNTA)

    escribir(deps, texto)

    c = contacto(fake_mia)
    assert (c["status"], c["name"], c["email"]) == ("entrego", nombre, correo)
    assert len(fake_kapso.texts) == 3
    escribir(deps, "¿Y los requisitos?")
    assert len(fake_kapso.texts) == 4  # solo la respuesta, sin volver a pedir


def test_la_segunda_pregunta_no_vuelve_a_invitar(mundo):
    fake_mia, fake_kapso, deps = mundo
    escribir(deps, PREGUNTA)
    escribir(deps, DATOS)
    antes = len(fake_kapso.texts)

    escribir(deps, "¿Y los requisitos?")

    assert len(fake_kapso.texts) == antes + 1 and INVITE not in fake_kapso.texts[antes:]


def test_tras_reiniciar_el_servicio_no_se_repite_la_invitacion(fake_mia, fake_kapso):
    deps = make_deps(fake_mia, fake_kapso, FakeClock(), bot_contact="on")
    escribir(deps, PREGUNTA)
    nuevo = make_deps(fake_mia, fake_kapso, FakeClock(), bot_contact="on")  # estado en memoria nuevo
    antes = len(fake_kapso.texts)

    escribir(nuevo, "¿Y los requisitos?", message_id="otro")

    assert fake_kapso.texts[antes:].count(INVITE) == 0


@pytest.mark.parametrize(
    "preparar",
    [
        pytest.param(lambda fm, fk: setattr(fm, "query_body", {**sin_informacion(), "clarify": ["Maestría A", "Maestría B"]}), id="aclaracion"),
    ],
)
def test_no_se_invita_tras_una_aclaracion_y_se_invita_tras_la_siguiente_respuesta(mundo, preparar):
    fake_mia, fake_kapso, deps = mundo
    preparar(fake_mia, fake_kapso)

    escribir(deps, "¿Cuándo empiezan las lecciones?")

    assert INVITE not in fake_kapso.texts and contacto(fake_mia)["status"] == "pendiente"
    assert fake_mia.events("claim_invite") == []
    # La persona nombra un programa: la respuesta sale y entonces sí se invita.
    fake_mia.query_body = {
        "id": "q", "answer": RESPUESTA, "sources": [], "mode": "literal", "latency_ms": 1, "no_info": False,
        "images": [], "clarify": [], "programs": ["Maestría A"],
    }
    escribir(deps, "Maestría A", message_id="w.aclara")
    assert fake_kapso.texts[-1] == INVITE


def test_se_invita_tras_una_respuesta_sin_informacion(mundo):
    fake_mia, fake_kapso, deps = mundo
    fake_mia.query_body = sin_informacion()

    escribir(deps, "¿Hay becas para extranjeros?")

    assert fake_kapso.texts[-1] == INVITE


def test_no_se_invita_tras_no_texto_muy_largo_limite_ni_no_disponible(fake_mia, fake_kapso):
    deps = make_deps(fake_mia, fake_kapso, FakeClock(), bot_contact="on", bot_max_messages_per_hour=3, bot_max_question_chars=20)
    escribir(deps, None, type="image", message_id="a")  # no_texto
    escribir(deps, "una pregunta demasiado larga para el límite", message_id="b")  # muy_largo
    escribir(deps, "otra pregunta demasiado larga", message_id="c")  # tercera: aún entra
    escribir(deps, "d", message_id="d")  # supera el límite por persona: se avisa
    assert INVITE not in fake_kapso.texts and fake_mia.events() == []
    assert contacto(fake_mia)["status"] == "pendiente"


def test_no_se_invita_con_el_bot_no_disponible(fake_mia, fake_kapso):
    fake_mia.status = "disabled"
    deps = make_deps(fake_mia, fake_kapso, FakeClock(), bot_contact="on")
    escribir(deps, PREGUNTA)
    assert INVITE not in fake_kapso.texts and fake_mia.events() == []

    fake_mia.status = "ok"
    fake_mia.query_status = 503
    escribir(deps, PREGUNTA, message_id="otro")  # la consulta falla: "no disponible"
    assert INVITE not in fake_kapso.texts and fake_mia.events() == []


def test_si_la_respuesta_no_sale_no_hay_invitacion_y_queda_para_la_siguiente(mundo):
    fake_mia, fake_kapso, deps = mundo
    fake_kapso.status = 500

    escribir(deps, PREGUNTA)

    assert contacto(fake_mia)["status"] == "pendiente" and fake_mia.events("claim_invite") == []
    fake_kapso.status = 200
    escribir(deps, PREGUNTA, message_id="otro")
    assert fake_kapso.texts[-1] == INVITE


def test_si_la_invitacion_no_sale_se_libera_y_vuelve_a_pendiente(mundo):
    fake_mia, fake_kapso, deps = mundo
    original = deps.kapso.send_text

    async def falla_la_invitacion(number_id, destination, text):
        if text == INVITE:
            return SendResult(ok=False)
        return await original(number_id, destination, text)

    deps.kapso.send_text = falla_la_invitacion

    escribir(deps, PREGUNTA)

    assert fake_mia.events() == ["claim_invite", "release_invite"]
    assert contacto(fake_mia)["status"] == "pendiente"


def test_si_otro_mensaje_gano_el_reclamo_no_se_envia_la_invitacion(mundo):
    fake_mia, fake_kapso, deps = mundo
    fake_mia.lose_next_claim = True

    escribir(deps, PREGUNTA)

    assert INVITE not in fake_kapso.texts and len(fake_kapso.texts) == 1


def test_con_una_aclaracion_pendiente_la_respuesta_no_se_toma_como_dato(mundo):
    from mia_whatsapp.state import Turn

    fake_mia, fake_kapso, deps = mundo
    escribir(deps, PREGUNTA)  # invitada
    # El bot acaba de preguntar a qué programa se refiere (013): el contexto tiene la aclaración pendiente.
    deps.state.conversations.add_person("persona-1", "¿Cuándo empiezan las lecciones?")
    deps.state.conversations.add("persona-1", Turn(role="bot", kind="clarify", candidates=("Ana Pérez", "Luis Mora")))
    antes = len(preguntas(fake_mia))

    escribir(deps, "Ana Pérez", message_id="resp")  # parece un nombre, pero es la respuesta a la aclaración

    assert len(preguntas(fake_mia)) == antes + 1  # se consultó (con el programa elegido), no se guardó como dato
    c = contacto(fake_mia)
    assert c["name"] is None and c["status"] == "invitada"  # y la invitación sigue abierta


def test_una_pregunta_de_para_que_se_explica_y_la_invitacion_sigue_abierta(mundo, capsys):
    fake_mia, fake_kapso, deps = mundo
    escribir(deps, PREGUNTA)
    capsys.readouterr()

    escribir(deps, "¿para qué piden mi correo?")

    assert fake_kapso.texts[-1] == DEFAULT_TEXT_CONTACT_WHY
    assert contacto(fake_mia)["status"] == "invitada" and len(preguntas(fake_mia)) == 1
    assert lineas(capsys)[-1]["contacto"] == "explicado"


def test_un_reintento_del_mismo_aviso_no_duplica_la_invitacion(mundo):
    fake_mia, fake_kapso, deps = mundo
    escribir(deps, PREGUNTA, message_id="mismo")
    escribir(deps, PREGUNTA, message_id="mismo")
    assert fake_kapso.texts.count(INVITE) == 1


def test_dos_mensajes_simultaneos_de_una_persona_nueva_dan_una_sola_invitacion(mundo):
    fake_mia, fake_kapso, deps = mundo

    async def dos():
        await asyncio.gather(
            handle_message(make_message(text="uno", message_id="a", person_key="p"), deps),
            handle_message(make_message(text="dos", message_id="b", person_key="p"), deps),
        )

    asyncio.run(dos())

    assert fake_kapso.texts.count(INVITE) == 1


# --- US2: declinar no estorba ---


def test_una_negativa_se_acepta_y_no_se_vuelve_a_pedir(mundo):
    fake_mia, fake_kapso, deps = mundo
    escribir(deps, PREGUNTA)

    escribir(deps, "no")

    assert fake_kapso.texts[-1] == DEFAULT_TEXT_CONTACT_DECLINED
    c = contacto(fake_mia)
    assert (c["status"], c["name"], c["email"]) == ("declino", None, None)
    assert preguntas(fake_mia) == [PREGUNTA]
    escribir(deps, "¿Y los requisitos?")
    assert INVITE not in fake_kapso.texts[2:]


def test_hacer_una_pregunta_en_lugar_de_contestar_declina_despues_de_responder(mundo):
    fake_mia, fake_kapso, deps = mundo
    escribir(deps, PREGUNTA)

    escribir(deps, "¿Y los requisitos?")

    assert RESPUESTA in fake_kapso.texts[-1] and len(fake_kapso.texts) == 3  # sin una segunda invitación
    assert contacto(fake_mia)["status"] == "declino"
    assert fake_mia.events() == ["claim_invite", "declined"]


def test_quien_declina_recibe_lo_mismo_que_quien_entrega(fake_mia, fake_kapso):
    deps = make_deps(fake_mia, fake_kapso, FakeClock(), bot_contact="on")
    escribir(deps, PREGUNTA, persona="a", phone="50611110001")
    escribir(deps, "no", persona="a", phone="50611110001")
    escribir(deps, PREGUNTA, persona="b", phone="50611110002")
    escribir(deps, DATOS, persona="b", phone="50611110002")
    kapso_antes = len(fake_kapso.texts)
    preguntas_antes = len(preguntas(fake_mia))

    escribir(deps, "¿Y los requisitos?", persona="a", phone="50611110001", message_id="a2")
    escribir(deps, "¿Y los requisitos?", persona="b", phone="50611110002", message_id="b2")

    a, b = fake_kapso.texts[kapso_antes:]
    assert a == b and len(preguntas(fake_mia)) == preguntas_antes + 2


def test_un_mensaje_que_no_es_texto_declina_y_se_responde_como_siempre(mundo):
    fake_mia, fake_kapso, deps = mundo
    escribir(deps, PREGUNTA)

    escribir(deps, None, type="image", message_id="img")

    assert "texto" in fake_kapso.texts[-1].lower() and contacto(fake_mia)["status"] == "declino"


def test_si_la_respuesta_no_sale_la_invitacion_sigue_abierta(mundo):
    fake_mia, fake_kapso, deps = mundo
    escribir(deps, PREGUNTA)
    fake_kapso.status = 500

    escribir(deps, "¿Y los requisitos?")

    assert contacto(fake_mia)["status"] == "invitada" and "declined" not in fake_mia.events()


def test_una_aclaracion_tambien_cierra_la_invitacion_si_salio_bien(mundo):
    fake_mia, fake_kapso, deps = mundo
    escribir(deps, PREGUNTA)
    fake_mia.query_body = {**sin_informacion(), "clarify": ["Maestría A", "Maestría B"]}

    escribir(deps, "¿Cuándo empiezan las lecciones?")

    assert contacto(fake_mia)["status"] == "declino"


def test_correo_invalido_se_pide_una_vez_y_a_la_segunda_se_cierra(mundo):
    fake_mia, fake_kapso, deps = mundo
    escribir(deps, PREGUNTA)

    escribir(deps, "Ana Pérez ana@")
    assert "No pude leer tu correo" in fake_kapso.texts[-1] and "ana@correo.com" in fake_kapso.texts[-1]
    c = contacto(fake_mia)
    assert (c["status"], c["name"], c["email_retried"]) == ("invitada", "Ana Pérez", True)

    escribir(deps, "ana arroba correo")
    assert fake_kapso.texts[-1] == DEFAULT_TEXT_CONTACT_DECLINED
    c = contacto(fake_mia)
    assert (c["status"], c["name"], c["email"]) == ("entrego", "Ana Pérez", None)  # quedó el nombre
    assert preguntas(fake_mia) == [PREGUNTA]


def test_correo_invalido_sin_nombre_dos_veces_deja_declino(mundo):
    fake_mia, fake_kapso, deps = mundo
    escribir(deps, PREGUNTA)
    escribir(deps, "ana@")
    escribir(deps, "ana@correo")
    assert contacto(fake_mia)["status"] == "declino"


@pytest.mark.parametrize("texto", ["no encuentro la matrícula", "paso a paso para inscribirme", "Requisitos de Admisión"])
def test_lo_que_parece_dato_o_negativa_pero_es_una_pregunta_se_responde(mundo, texto):
    fake_mia, fake_kapso, deps = mundo
    escribir(deps, PREGUNTA)

    escribir(deps, texto)

    assert texto in preguntas(fake_mia)
    c = contacto(fake_mia)
    assert (c["name"], c["email"]) == (None, None) and c["status"] == "declino"
    assert DEFAULT_TEXT_CONTACT_DECLINED not in fake_kapso.texts


# --- US4: borrar y volver a dejar los datos ---


def test_borrar_mis_datos_borra_confirma_y_no_consulta(mundo, capsys):
    fake_mia, fake_kapso, deps = mundo
    escribir(deps, PREGUNTA)
    escribir(deps, DATOS)
    capsys.readouterr()

    escribir(deps, "Borrar mis datos")

    assert fake_kapso.texts[-1] == DEFAULT_TEXT_CONTACT_ERASED
    c = contacto(fake_mia)
    assert (c["status"], c["name"], c["email"]) == ("declino", None, None)
    assert preguntas(fake_mia) == [PREGUNTA]
    assert lineas(capsys)[-1]["contacto"] == "borrado"
    assert all("borrar" not in t.text.lower() for t in deps.state.conversations.turns("persona-1"))
    escribir(deps, "¿Y los requisitos?")
    assert fake_kapso.texts.count(INVITE) == 1  # no se vuelve a invitar


def test_borrar_sin_datos_lo_dice_sin_error(mundo):
    fake_mia, fake_kapso, deps = mundo
    escribir(deps, PREGUNTA)
    escribir(deps, "no")

    escribir(deps, "borrar mis datos")

    assert fake_kapso.texts[-1] == DEFAULT_TEXT_CONTACT_NO_DATA


@pytest.mark.parametrize("primero", ["pregunta", "nada"])
def test_la_frase_de_borrado_funciona_en_cualquier_estado(mundo, primero):
    fake_mia, fake_kapso, deps = mundo
    if primero == "pregunta":
        escribir(deps, PREGUNTA)  # invitada

    escribir(deps, "ELIMINA MI CORREO", message_id="borrar")

    assert fake_kapso.texts[-1] == DEFAULT_TEXT_CONTACT_NO_DATA
    assert contacto(fake_mia)["status"] == "declino" and preguntas(fake_mia) == ([PREGUNTA] if primero == "pregunta" else [])


def test_quiero_dejar_mis_datos_reabre_y_el_dato_nuevo_reemplaza(mundo):
    fake_mia, fake_kapso, deps = mundo
    escribir(deps, PREGUNTA)
    escribir(deps, DATOS)

    escribir(deps, "quiero dejar mis datos")
    assert fake_kapso.texts[-1] == INVITE and contacto(fake_mia)["status"] == "invitada"

    escribir(deps, "otro@correo.com")
    c = contacto(fake_mia)
    assert (c["status"], c["name"], c["email"]) == ("entrego", "Ana Pérez", "otro@correo.com")
    assert len(preguntas(fake_mia)) == 1


def test_reabrir_funciona_tambien_sin_haber_sido_invitada(mundo):
    fake_mia, fake_kapso, deps = mundo

    escribir(deps, "quiero dejar mis datos")

    assert fake_kapso.texts == [INVITE] and preguntas(fake_mia) == []
    assert contacto(fake_mia)["status"] == "invitada"


def test_con_la_funcion_apagada_las_frases_son_preguntas_normales(fake_mia, fake_kapso):
    deps = make_deps(fake_mia, fake_kapso, FakeClock(), bot_contact="off")

    escribir(deps, "borrar mis datos")
    escribir(deps, "quiero dejar mis datos", message_id="otro")

    assert preguntas(fake_mia) == ["borrar mis datos", "quiero dejar mis datos"] and fake_mia.events() == []


# --- US5: apagado y resiliencia ---


def test_con_la_funcion_apagada_el_bot_es_el_de_siempre(fake_mia, fake_kapso):
    deps = make_deps(fake_mia, fake_kapso, FakeClock())  # BOT_CONTACT por defecto: off

    escribir(deps, PREGUNTA)
    escribir(deps, DATOS, message_id="dos")

    assert all("phone" not in r["json"] for r in fake_mia.recorded.to("/bot/messages"))
    assert fake_mia.events() == [] and fake_mia.contacts == {}
    assert INVITE not in fake_kapso.texts and len(fake_kapso.texts) == 2
    assert preguntas(fake_mia) == [PREGUNTA, DATOS]  # los datos son una pregunta más


def test_un_fallo_de_contactos_no_impide_responder(mundo, caplog):
    fake_mia, fake_kapso, deps = mundo
    fake_mia.contacts_error = 500

    with caplog.at_level(logging.DEBUG):
        escribir(deps, PREGUNTA)
        escribir(deps, "¿Y los requisitos?", message_id="dos")

    assert len(fake_kapso.texts) == 2 and all(RESPUESTA in t for t in fake_kapso.texts)
    assert INVITE not in fake_kapso.texts
    assert not any(dato in caplog.text for dato in PERSONALES)


def test_si_falla_guardar_el_dato_el_mensaje_sigue_como_pregunta(mundo):
    fake_mia, fake_kapso, deps = mundo
    escribir(deps, PREGUNTA)
    fake_mia.contacts_error = 500

    escribir(deps, DATOS)

    assert DATOS in preguntas(fake_mia)  # no se consumió: se trató como el bot lo hacía antes
    assert not fake_kapso.texts[-1].startswith("Listo, guardé")


def test_sin_telefono_real_no_hay_contacto_ni_invitacion(mundo):
    fake_mia, fake_kapso, deps = mundo

    escribir(deps, PREGUNTA, phone=None, destination=("recipient", "US.1"))

    assert all("phone" not in r["json"] for r in fake_mia.recorded.to("/bot/messages"))
    assert fake_mia.contacts == {} and len(fake_kapso.texts) == 1


def test_con_el_tope_mensual_alcanzado_no_hay_llamadas_de_contacto_ni_respuesta(mundo):
    fake_mia, fake_kapso, deps = mundo
    fake_mia.status = "cap_reached"

    escribir(deps, PREGUNTA)
    escribir(deps, "borrar mis datos", message_id="b")  # limite conocido: tampoco se atiende

    assert fake_kapso.texts == [] and fake_mia.events() == []


def test_apagar_la_funcion_no_borra_lo_guardado(fake_mia, fake_kapso):
    encendido = make_deps(fake_mia, fake_kapso, FakeClock(), bot_contact="on")
    escribir(encendido, PREGUNTA)
    escribir(encendido, DATOS)
    apagado = make_deps(fake_mia, fake_kapso, FakeClock(), bot_contact="off")

    escribir(apagado, "¿Y los requisitos?", message_id="x")

    assert contacto(fake_mia)["email"] == "ana@correo.com"


# --- US3: nada de datos personales en los registros ni en la consulta ---


def test_ninguna_linea_del_registro_ni_de_la_consulta_trae_datos_personales(mundo, capsys, caplog):
    fake_mia, fake_kapso, deps = mundo

    with caplog.at_level(logging.DEBUG):
        escribir(deps, PREGUNTA)
        escribir(deps, "¿para qué piden mi correo?", message_id="why")
        escribir(deps, DATOS)
        escribir(deps, "borrar mis datos", message_id="del")
        escribir(deps, "quiero dejar mis datos", message_id="re")
        escribir(deps, "Ana Pérez ana@", message_id="mal")

    salida = capsys.readouterr().out + caplog.text
    assert not any(dato in salida for dato in PERSONALES)
    # POST /bot/query nunca lleva el teléfono ni el texto de un mensaje de contacto.
    for peticion in fake_mia.recorded.to("/bot/query"):
        assert set(peticion["json"]) == {"number_id", "question"}
    assert preguntas(fake_mia) == [PREGUNTA]


# Constancia (T026): las pruebas de apagado y de fallo de contactos (arriba) no revelaron ningún camino que lance, ningún `phone`
# enviado con la función apagada ni una falla de contactos que cambie el estado del bot: no hizo falta corregir nada.
