"""Memoria del bot de WhatsApp (feature 014, US8): `context_turns` en las rutas de bots y en `POST /bot/messages`."""

import json

import pytest

from mia.config import settings
from mia.storage.models import Domain

COORD = "coord.comp@itcr.ac.cr"
OPERADOR = "operador@itcr.ac.cr"
NUMERO = "647015955153740"
CLAVE = "clave-del-servicio-de-prueba"


@pytest.fixture
def mundo(db, units, make_admin, make_artifact):
    with db() as session:
        session.add(Domain(id="d-adm", unit_id=units.comp, name="Admisión"))
        session.commit()
    make_admin(COORD, units=["Computación"])
    make_admin(OPERADOR, global_=True)
    return {"comp": make_artifact("Bot de Computación", units=[units.comp])}


def _crear(client, headers, mundo, **extra):
    cuerpo = {
        "name": "Atracción",
        "kapso_number_id": NUMERO,
        "artifact_id": mundo["comp"].id,
        **extra,
    }
    return client.post("/bots", json=cuerpo, headers=headers)


def _lineas(capsys, accion):
    salida = [
        json.loads(linea) for linea in capsys.readouterr().out.splitlines() if linea.startswith("{")
    ]
    return [linea for linea in salida if linea["action"] == accion]


def test_un_bot_sin_memoria_propia_usa_dos_vueltas(client, mundo, admin):
    bot = _crear(client, admin, mundo).json()

    assert bot["context_turns"] is None and bot["context_turns_effective"] == 2
    listado = client.get("/bots", headers=admin).json()["bots"][0]
    assert listado["context_turns"] is None and listado["context_turns_effective"] == 2


def test_un_bot_con_memoria_propia_la_guarda_y_es_la_efectiva(client, mundo, admin):
    bot = _crear(client, admin, mundo, context_turns=5).json()

    assert bot["context_turns"] == 5 and bot["context_turns_effective"] == 5


def test_patch_cambia_la_memoria_y_null_vuelve_al_valor_por_defecto(client, mundo, admin):
    bot = _crear(client, admin, mundo).json()

    cambiado = client.patch(f"/bots/{bot['id']}", json={"context_turns": 7}, headers=admin).json()
    assert (cambiado["context_turns"], cambiado["context_turns_effective"]) == (7, 7)
    # Otro cambio que no la menciona no la toca.
    otro = client.patch(f"/bots/{bot['id']}", json={"active": False}, headers=admin).json()
    assert otro["context_turns"] == 7
    vuelto = client.patch(f"/bots/{bot['id']}", json={"context_turns": None}, headers=admin).json()
    assert (vuelto["context_turns"], vuelto["context_turns_effective"]) == (None, 2)


@pytest.mark.parametrize("valor", [0, 11, 2.5, "dos", -1])
def test_un_valor_invalido_es_422_al_crear_y_al_cambiar(client, mundo, admin, valor):
    assert _crear(client, admin, mundo, context_turns=valor).status_code == 422
    bot = _crear(client, admin, mundo).json()
    assert (
        client.patch(f"/bots/{bot['id']}", json={"context_turns": valor}, headers=admin).status_code
        == 422
    )


def test_un_administrador_de_un_programa_no_puede_cambiarla(client, mundo, admin, as_user):
    bot = _crear(client, admin, mundo).json()

    respuesta = client.patch(
        f"/bots/{bot['id']}", json={"context_turns": 4}, headers=as_user(COORD)
    )

    assert respuesta.status_code == 403 and respuesta.json()["code"] == "global_only"


def test_un_cambio_deja_la_linea_de_auditoria_con_el_anterior_y_el_nuevo(
    client, mundo, as_user, capsys
):
    bot = _crear(client, as_user(OPERADOR), mundo).json()
    capsys.readouterr()

    client.patch(f"/bots/{bot['id']}", json={"context_turns": 6}, headers=as_user(OPERADOR))
    client.patch(f"/bots/{bot['id']}", json={"context_turns": None}, headers=as_user(OPERADOR))
    client.patch(
        f"/bots/{bot['id']}", json={"context_turns": None}, headers=as_user(OPERADOR)
    )  # sin cambio

    lineas = _lineas(capsys, "bot.context_turns")
    assert [l["detail"] for l in lineas] == [
        "Atracción: por defecto -> 6",
        "Atracción: 6 -> por defecto",
    ]
    assert all(l["target"] == bot["id"] and l["actor"] == OPERADOR for l in lineas)


@pytest.fixture
def servicio(monkeypatch):
    monkeypatch.setattr(settings, "bot_service_key", CLAVE)
    return {"X-Bot-Service-Key": CLAVE}


def _mensajes(client, servicio, number=NUMERO):
    return client.post(
        "/bot/messages", json={"number_id": number, "received": 1, "sent": 0}, headers=servicio
    ).json()


def test_bot_messages_devuelve_la_memoria_efectiva_y_un_cambio_rige_en_la_llamada_siguiente(
    client, mundo, admin, servicio
):
    bot = _crear(client, admin, mundo).json()

    assert _mensajes(client, servicio)["context_turns"] == 2
    client.patch(f"/bots/{bot['id']}", json={"context_turns": 4}, headers=admin)
    cuerpo = _mensajes(client, servicio)

    assert cuerpo["context_turns"] == 4
    assert {"status", "month", "month_messages", "month_cap"} <= set(cuerpo)
    assert cuerpo["status"] == "ok" and cuerpo["month_messages"] == 2


def test_un_numero_sin_bot_devuelve_context_turns_nulo(client, mundo, servicio):
    cuerpo = _mensajes(client, servicio, number="000")

    assert cuerpo["status"] == "unknown_bot" and cuerpo["context_turns"] is None
