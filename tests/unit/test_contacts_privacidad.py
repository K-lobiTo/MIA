"""Privacidad de los contactos de WhatsApp (feature 017, SC-005 y SC-008): el teléfono, el nombre y el correo viven solo en
`whatsapp_contacts`; no aparecen en Uso, en los registros, en la auditoría ni en los errores, y la tabla no guarda texto de
conversaciones. Vaciar la tabla no afecta nada más."""

import logging
import uuid

import pytest
from sqlalchemy import func, inspect, select, text

from mia.config import settings
from mia.storage.models import (
    Bot,
    BotMessageCount,
    Conversation,
    Document,
    Domain,
    QueryLog,
    Unit,
    WhatsAppContact,
)

CLAVE = "clave-del-servicio-de-prueba"
NUMERO = "647015955153740"
OTRO_NUMERO = "999000111222333"
TEL = "50688887777"
NOMBRE = "Ana Pérez"
CORREO = "ana@correo.com"
PERSONALES = (TEL, "+" + TEL, "88887777", NOMBRE, CORREO)


@pytest.fixture
def servicio(monkeypatch):
    monkeypatch.setattr(settings, "bot_service_key", CLAVE)
    return {"X-Bot-Service-Key": CLAVE}


@pytest.fixture
def bots(db, make_artifact):
    artefacto = make_artifact("Bot", units=[])
    ids = []
    with db() as session:
        session.add_all([Unit(id="u1", name="Computación"), Domain(id="dom-1", unit_id="u1", name="Admisión")])
        session.flush()
        session.add(Document(id="doc-1", domain_id="dom-1", filename="doc.pdf", source_type="pdf", file_hash="h", status="done"))
        for numero in (NUMERO, OTRO_NUMERO):
            bot_id = str(uuid.uuid4())
            ids.append(bot_id)
            session.add(Bot(id=bot_id, name=f"Bot {numero}", kapso_number_id=numero, artifact_id=artefacto.id))
        session.add(QueryLog(id="q1", artifact_id=artefacto.id, question="¿Cuándo es la matrícula?", domain_ids="[]", mode="literal", outcome="answered"))
        session.commit()
    return ids


def _recorrido(client, servicio, numero=NUMERO, phone=TEL):
    def evento(nombre, **extra):
        return client.put("/bot/contacts", json={"number_id": numero, "phone": phone, "event": nombre, **extra}, headers=servicio)

    client.post("/bot/messages", json={"number_id": numero, "received": 1, "phone": phone}, headers=servicio)
    evento("claim_invite")
    evento("provided", name=NOMBRE, email=CORREO)
    evento("provided", name=NOMBRE)  # 409: ya entregó
    evento("erase")
    evento("reopen")
    evento("provided", name="x" * 200)  # 422


def test_un_registro_por_persona_y_bot_con_solo_los_campos_del_modelo(client, db, bots, servicio):
    _recorrido(client, servicio)
    _recorrido(client, servicio)

    columnas = {c["name"] for c in inspect(db().get_bind()).get_columns("whatsapp_contacts")}
    assert columnas == {
        "id", "bot_id", "phone", "name", "email", "status", "email_retried", "created_at", "last_seen_at", "updated_at",
    }
    with db() as session:
        assert session.scalar(select(func.count()).select_from(WhatsAppContact)) == 1
        contacto = session.scalar(select(WhatsAppContact))
        # Ningún campo guarda el texto de una pregunta ni de una respuesta.
        valores = " ".join(str(v) for v in (contacto.phone, contacto.name, contacto.email, contacto.status))
        assert "matrícula" not in valores and "¿" not in valores


def test_ni_uso_ni_la_auditoria_ni_los_registros_traen_datos_personales(client, db, bots, servicio, capsys, caplog):
    with caplog.at_level(logging.DEBUG):
        _recorrido(client, servicio)

    salida = capsys.readouterr().out + caplog.text
    assert not any(dato in salida for dato in PERSONALES)
    with db() as session:
        for fila in session.execute(text("SELECT question FROM queries")).all():
            assert not any(dato in " ".join(map(str, fila)) for dato in PERSONALES)


def test_un_fallo_del_almacen_no_deja_datos_personales_en_los_registros(client, db, bots, servicio, monkeypatch, caplog):
    from mia.contacts import store

    def boom(*args, **kwargs):
        raise RuntimeError(f"falla con {TEL}, {NOMBRE} y {CORREO}")

    monkeypatch.setattr(store, "get_or_create", boom)
    with caplog.at_level(logging.DEBUG):
        respuesta = client.post("/bot/messages", json={"number_id": NUMERO, "received": 1, "phone": TEL}, headers=servicio)

    assert respuesta.status_code == 200 and not any(dato in caplog.text for dato in PERSONALES)


@pytest.mark.parametrize(
    "cuerpo",
    [
        {"number_id": NUMERO, "phone": TEL, "name": NOMBRE, "email": CORREO},  # falta event
        {"number_id": NUMERO, "phone": TEL, "event": "inventado", "name": NOMBRE},
        {"number_id": NUMERO, "phone": 12345678901, "event": "provided"},  # tipo equivocado
        {"number_id": NUMERO, "phone": "12", "event": "provided", "name": NOMBRE, "email": CORREO},
    ],
)
def test_los_errores_de_validacion_no_repiten_el_dato_recibido(client, db, bots, servicio, cuerpo):
    respuesta = client.put("/bot/contacts", json=cuerpo, headers=servicio)

    assert respuesta.status_code == 422
    assert not any(dato in respuesta.text for dato in (TEL, NOMBRE, CORREO, "12345678901"))


def test_el_error_de_validacion_de_bot_messages_tampoco_repite_el_telefono(client, db, bots, servicio):
    respuesta = client.post(
        "/bot/messages", json={"number_id": NUMERO, "received": "no es un número", "phone": TEL}, headers=servicio
    )
    assert respuesta.status_code == 422 and TEL not in respuesta.text


def test_los_errores_409_y_422_del_almacen_no_traen_datos(client, db, bots, servicio):
    client.post("/bot/messages", json={"number_id": NUMERO, "received": 1, "phone": TEL}, headers=servicio)
    conflicto = client.put(
        "/bot/contacts", json={"number_id": NUMERO, "phone": TEL, "event": "provided", "name": NOMBRE}, headers=servicio
    )
    invalido = client.put(
        "/bot/contacts",
        json={"number_id": NUMERO, "phone": TEL, "event": "provided", "email": "no-es-correo"},
        headers=servicio,
    )
    assert conflicto.status_code == 409 and invalido.status_code in (409, 422)
    for respuesta in (conflicto, invalido):
        assert not any(dato in respuesta.text for dato in PERSONALES) and "no-es-correo" not in respuesta.text


def test_vaciar_la_tabla_no_afecta_a_nada_mas_y_el_bot_sigue_respondiendo(client, db, bots, servicio):
    _recorrido(client, servicio)
    with db() as session:
        antes = {
            tabla: session.scalar(select(func.count()).select_from(modelo))
            for tabla, modelo in (("queries", QueryLog), ("bots", Bot), ("conteos", BotMessageCount), ("documentos", Document), ("conversaciones", Conversation))
        }
        session.execute(text("DELETE FROM whatsapp_contacts"))
        session.commit()
        despues = {
            tabla: session.scalar(select(func.count()).select_from(modelo))
            for tabla, modelo in (("queries", QueryLog), ("bots", Bot), ("conteos", BotMessageCount), ("documentos", Document), ("conversaciones", Conversation))
        }
    assert antes == despues and antes["conteos"] == 1

    respuesta = client.post("/bot/messages", json={"number_id": NUMERO, "received": 1, "phone": TEL}, headers=servicio)
    # El bot sigue funcionando, y a esa persona se le trata como nueva (pendiente).
    assert respuesta.status_code == 200 and respuesta.json()["contact"]["status"] == "pendiente"


def test_la_misma_persona_en_dos_bots_tiene_dos_registros_independientes(client, db, bots, servicio):
    _recorrido(client, servicio, numero=NUMERO)
    client.post("/bot/messages", json={"number_id": OTRO_NUMERO, "received": 1, "phone": TEL}, headers=servicio)

    otro = client.put(
        "/bot/contacts", json={"number_id": OTRO_NUMERO, "phone": TEL, "event": "provided", "name": "Otro"}, headers=servicio
    )
    # En el segundo bot no hay invitación abierta: los datos del primero no se ven ni se mezclan.
    assert otro.status_code == 409 and otro.json()["status"] == "pendiente"
    with db() as session:
        filas = session.scalars(select(WhatsAppContact).order_by(WhatsAppContact.bot_id)).all()
        assert len(filas) == 2 and {f.bot_id for f in filas} == set(bots)
        assert {f.name for f in filas} == {None}  # el recorrido terminó con un borrado y una reapertura


def test_las_rutas_de_contactos_no_son_accesibles_con_otras_credenciales(client, db, bots, admin, make_artifact):
    cuerpo = {"number_id": NUMERO, "phone": TEL, "event": "claim_invite"}
    assert client.put("/bot/contacts", json=cuerpo, headers=admin).status_code == 401
    assert client.put("/bot/contacts", json=cuerpo, headers=make_artifact("A").headers).status_code == 401
    assert client.put("/bot/contacts", json=cuerpo).status_code == 401


# Constancia (T022): estas pruebas revelaron un fallo real, que ya está corregido: el 422 por defecto de FastAPI repetía lo
# recibido (`input`), incluido el teléfono, el nombre o el correo. Se quitó en `api/main.py` (`validation_error_handler`) solo para
# `/bot/contacts` y `/bot/messages`; ver specs/017-datos-contacto-whatsapp/research.md R14.
