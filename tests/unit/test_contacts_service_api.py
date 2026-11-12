"""Rutas del servicio del bot para los contactos (feature 017): POST /bot/messages con `phone` y PUT /bot/contacts."""

import uuid

import pytest
from sqlalchemy import func, select

from mia.config import settings
from mia.contacts import store
from mia.storage.models import Bot, WhatsAppContact

CLAVE = "clave-del-servicio-de-prueba"
NUMERO = "647015955153740"
TEL = "50688887777"
TEL_NORMAL = "+50688887777"


@pytest.fixture
def servicio(monkeypatch):
    monkeypatch.setattr(settings, "bot_service_key", CLAVE)
    return {"X-Bot-Service-Key": CLAVE}


@pytest.fixture
def bot(db):
    bot_id = str(uuid.uuid4())
    with db() as session:
        session.add(Bot(id=bot_id, name="Bot", kapso_number_id=NUMERO, artifact_id=None, active=True))
        session.commit()
    return bot_id


def _mensaje(client, servicio, **extra):
    return client.post("/bot/messages", json={"number_id": NUMERO, "received": 1, **extra}, headers=servicio)


def _evento(client, servicio, event, number=NUMERO, phone=TEL, **extra):
    return client.put("/bot/contacts", json={"number_id": number, "phone": phone, "event": event, **extra}, headers=servicio)


def _filas(db):
    with db() as session:
        return session.scalar(select(func.count()).select_from(WhatsAppContact))


def _contacto(db, phone=TEL_NORMAL):
    with db() as session:
        return session.scalar(select(WhatsAppContact).where(WhatsAppContact.phone == phone))


# --- credencial ---


@pytest.mark.parametrize("headers", [{}, {"X-Bot-Service-Key": "otra"}])
def test_sin_la_credencial_correcta_las_rutas_responden_401(client, db, bot, servicio, headers):
    assert client.post("/bot/messages", json={"number_id": NUMERO, "phone": TEL}, headers=headers).status_code == 401
    cuerpo = {"number_id": NUMERO, "phone": TEL, "event": "claim_invite"}
    assert client.put("/bot/contacts", json=cuerpo, headers=headers).status_code == 401
    assert _filas(db) == 0


# --- POST /bot/messages ---


def test_sin_phone_la_ruta_es_la_de_siempre_y_contact_es_nulo(client, db, bot, servicio):
    respuesta = _mensaje(client, servicio)

    assert respuesta.status_code == 200
    # Sin phone la respuesta es exactamente la de antes: el campo ni aparece.
    assert "contact" not in respuesta.json()
    assert _filas(db) == 0


def test_con_phone_crea_el_contacto_pendiente_sin_revelar_datos(client, db, bot, servicio):
    cuerpo = _mensaje(client, servicio, phone=TEL).json()

    assert cuerpo["contact"] == {"status": "pendiente", "email_retried": False, "has_name": False, "has_email": False}
    assert _contacto(db).status == "pendiente"
    # La respuesta nunca trae el teléfono ni valores de nombre o correo.
    assert TEL not in str(cuerpo)


def test_el_mismo_telefono_escrito_distinto_es_un_solo_contacto(client, db, bot, servicio):
    _mensaje(client, servicio, phone="50688887777")
    _mensaje(client, servicio, phone="+506 8888-7777")

    assert _filas(db) == 1


@pytest.mark.parametrize("phone", ["abc", "123", "1" * 20, "   "])
def test_un_phone_invalido_deja_contact_nulo_sin_fallar(client, db, bot, servicio, phone):
    respuesta = _mensaje(client, servicio, phone=phone)

    assert respuesta.status_code == 200 and respuesta.json().get("contact") is None
    assert respuesta.json()["status"] in ("ok", "disabled")
    assert _filas(db) == 0


def test_un_numero_sin_bot_devuelve_unknown_bot_y_no_crea_contacto(client, db, servicio):
    respuesta = client.post("/bot/messages", json={"number_id": "999", "received": 1, "phone": TEL}, headers=servicio)

    assert respuesta.json()["status"] == "unknown_bot" and respuesta.json().get("contact") is None
    assert _filas(db) == 0


def test_un_fallo_de_contactos_no_cambia_el_estado_ni_hace_fallar_la_ruta(client, db, bot, servicio, monkeypatch, caplog):
    def _boom(*args, **kwargs):
        raise RuntimeError(f"falla con {TEL} y ana@correo.com")

    sano = _mensaje(client, servicio).json()
    monkeypatch.setattr(store, "get_or_create", _boom)

    with caplog.at_level("DEBUG"):
        respuesta = _mensaje(client, servicio, phone=TEL)

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo.get("contact") is None and cuerpo["status"] == sano["status"]
    # El mensaje se contó y nada del teléfono ni del correo llegó a los registros.
    assert cuerpo["month_messages"] == sano["month_messages"] + 1
    assert TEL not in caplog.text and "ana@correo.com" not in caplog.text


# --- PUT /bot/contacts ---


def test_el_flujo_completo_de_eventos(client, db, bot, servicio):
    _mensaje(client, servicio, phone=TEL)

    claim = _evento(client, servicio, "claim_invite").json()
    assert claim["claimed"] is True and claim["contact"]["status"] == "invitada"

    entregado = _evento(client, servicio, "provided", name="Ana Pérez", email="Ana@Correo.com").json()
    assert entregado["contact"] == {"status": "entrego", "email_retried": False, "has_name": True, "has_email": True}
    fila = _contacto(db)
    assert (fila.name, fila.email) == ("Ana Pérez", "ana@correo.com")

    borrado = _evento(client, servicio, "erase").json()
    assert borrado["had_data"] is True and borrado["contact"]["status"] == "declino"
    assert _contacto(db).name is None

    reabierto = _evento(client, servicio, "reopen").json()
    assert reabierto["claimed"] is True and reabierto["contact"]["status"] == "invitada"


def test_repetir_claim_invite_devuelve_claimed_falso(client, db, bot, servicio):
    _mensaje(client, servicio, phone=TEL)
    assert _evento(client, servicio, "claim_invite").json()["claimed"] is True

    segunda = _evento(client, servicio, "claim_invite")

    assert segunda.status_code == 200 and segunda.json()["claimed"] is False


def test_release_email_retry_y_declined(client, db, bot, servicio):
    _mensaje(client, servicio, phone=TEL)
    _evento(client, servicio, "claim_invite")
    assert _evento(client, servicio, "release_invite").json()["contact"]["status"] == "pendiente"

    _evento(client, servicio, "claim_invite")
    retry = _evento(client, servicio, "email_retry", name="Ana Pérez").json()
    assert retry["contact"]["email_retried"] is True and retry["contact"]["has_name"] is True
    assert _evento(client, servicio, "email_retry").status_code == 409

    assert _evento(client, servicio, "declined").json()["contact"]["status"] == "entrego"
    # Repetir declined no falla.
    assert _evento(client, servicio, "declined").status_code == 200


def test_un_evento_fuera_de_orden_responde_409_con_el_estado_actual(client, db, bot, servicio):
    _mensaje(client, servicio, phone=TEL)

    respuesta = _evento(client, servicio, "provided", name="Ana Pérez")

    assert respuesta.status_code == 409 and respuesta.json()["status"] == "pendiente"
    assert "Ana" not in respuesta.text and TEL not in respuesta.text


@pytest.mark.parametrize(
    "extra",
    [
        {"phone": "12"},
        {"phone": "letras"},
        {"event": "provided", "email": "ana@"},
        {"event": "provided", "email": "x" * 300},
        {"event": "provided", "name": "x" * 81},
        {"event": "provided", "name": "  "},
        {"event": "provided"},
    ],
)
def test_datos_invalidos_responden_422_sin_repetir_el_valor(client, db, bot, servicio, extra):
    _mensaje(client, servicio, phone=TEL)
    _evento(client, servicio, "claim_invite")
    cuerpo = {"phone": TEL, "event": "claim_invite", **extra}

    respuesta = client.put("/bot/contacts", json={"number_id": NUMERO, **cuerpo}, headers=servicio)

    assert respuesta.status_code == 422
    for valor in extra.values():
        assert len(valor) < 4 or valor not in respuesta.text


def test_un_evento_desconocido_responde_422(client, db, bot, servicio):
    assert _evento(client, servicio, "inventado").status_code == 422


def test_un_numero_sin_bot_responde_404(client, db, servicio):
    assert _evento(client, servicio, "claim_invite", number="999").status_code == 404
    assert _filas(db) == 0


def test_los_eventos_que_exigen_contacto_responden_404_si_no_existe(client, db, bot, servicio):
    for evento in ("release_invite", "email_retry", "declined"):
        assert _evento(client, servicio, evento).status_code == 404
    assert _evento(client, servicio, "provided", name="Ana Pérez").status_code == 404


@pytest.mark.parametrize("evento", ["claim_invite", "erase", "reopen"])
def test_claim_invite_erase_y_reopen_crean_el_contacto_si_falta(client, db, bot, servicio, evento):
    assert _evento(client, servicio, evento).status_code == 200
    assert _filas(db) == 1


def test_las_rutas_de_contactos_solo_tocan_su_tabla(client, db, bot, servicio):
    from mia.storage.models import Conversation, QueryLog

    _mensaje(client, servicio, phone=TEL)
    _evento(client, servicio, "claim_invite")
    with db() as session:
        assert session.scalar(select(func.count()).select_from(QueryLog)) == 0
        assert session.scalar(select(func.count()).select_from(Conversation)) == 0
