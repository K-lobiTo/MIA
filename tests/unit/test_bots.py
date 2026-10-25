"""Rutas de administración de bots de WhatsApp (feature 011): GET, POST y PATCH /bots, solo con alcance global."""

import json

import pytest

from mia.bots.usage import add_messages, current_month
from mia.config import settings
from mia.storage.models import Artifact, ArtifactDomain, Bot, Domain

COORD = "coord.comp@itcr.ac.cr"
OPERADOR = "operador@itcr.ac.cr"


@pytest.fixture
def mundo(db, units, make_admin, make_artifact):
    with db() as session:
        session.add_all([
            Domain(id="d-adm", unit_id=units.comp, name="Admisión"),
            Domain(id="d-plan", unit_id=units.comp, name="Plan de estudios"),
            Domain(id="d-costos", unit_id=units.adm, name="Costos"),
        ])
        session.commit()
    make_admin(COORD, units=["Computación"])
    make_admin(OPERADOR, global_=True)
    return {
        "units": units,
        "comp": make_artifact("Bot de Computación", units=[units.comp]),
        "adm": make_artifact("Bot de Analítica", units=[units.adm]),
    }


def _crear(client, headers, mundo, name="Atracción de estudiantes", number="647015955153740", artifact="comp"):
    return client.post(
        "/bots",
        json={"name": name, "kapso_number_id": number, "artifact_id": mundo[artifact].id},
        headers=headers,
    )


def _lineas(capsys):
    return [json.loads(linea) for linea in capsys.readouterr().out.splitlines() if linea.startswith("{")]


# --- Listado ---------------------------------------------------------------------------------------------------


def test_sin_bots_el_listado_trae_el_tope_el_mes_y_si_el_servicio_esta_configurado(client, mundo, admin, monkeypatch):
    monkeypatch.setattr(settings, "bot_service_key", "")
    body = client.get("/bots", headers=admin).json()
    assert body == {
        "monthly_cap": settings.bot_monthly_message_cap,
        "service_configured": False,
        "month": current_month(),
        "bots": [],
    }
    monkeypatch.setattr(settings, "bot_service_key", "clave")
    assert client.get("/bots", headers=admin).json()["service_configured"] is True


def test_un_bot_se_lista_con_la_forma_del_contrato(client, mundo, admin):
    creado = _crear(client, admin, mundo).json()

    bots = client.get("/bots", headers=admin).json()["bots"]

    assert len(bots) == 1
    bot = bots[0]
    assert set(bot) == {
        "id", "name", "kapso_number_id", "active", "artifact", "domains", "available", "unavailable_reason", "usage",
        "created_at",
    }
    assert bot == creado
    assert bot["name"] == "Atracción de estudiantes" and bot["kapso_number_id"] == "647015955153740"
    assert bot["active"] is True and bot["available"] is True and bot["unavailable_reason"] is None
    assert bot["artifact"] == {"id": mundo["comp"].id, "name": "Bot de Computación", "active": True}
    assert bot["domains"] == [
        "Computación / Admisión", "Computación / Plan de estudios",
    ]
    assert bot["usage"] == {"received": 0, "sent": 0, "total": 0, "cap_reached": False}
    assert bot["created_at"].endswith("Z")


def test_el_listado_va_ordenado_por_nombre(client, mundo, admin):
    _crear(client, admin, mundo, name="Zeta", number="2")
    _crear(client, admin, mundo, name="Alfa", number="1")
    assert [b["name"] for b in client.get("/bots", headers=admin).json()["bots"]] == ["Alfa", "Zeta"]


def test_el_consumo_del_mes_y_el_tope_se_ven_en_el_bot(client, db, mundo, admin, monkeypatch):
    monkeypatch.setattr(settings, "bot_monthly_message_cap", 10)
    bot_id = _crear(client, admin, mundo).json()["id"]
    with db() as session:
        add_messages(session, bot_id, current_month(), 4, 3)
    bot = client.get("/bots", headers=admin).json()["bots"][0]
    assert bot["usage"] == {"received": 4, "sent": 3, "total": 7, "cap_reached": False}
    assert bot["available"] is True

    with db() as session:
        add_messages(session, bot_id, current_month(), 3, 0)
    bot = client.get("/bots", headers=admin).json()["bots"][0]
    assert bot["usage"]["cap_reached"] is True
    assert bot["available"] is False and bot["unavailable_reason"] == "Se alcanzó el tope mensual de mensajes."


# --- Registro --------------------------------------------------------------------------------------------------


def test_registrar_un_bot_responde_201_y_deja_una_linea_de_auditoria(client, mundo, as_user, capsys):
    respuesta = _crear(client, as_user(OPERADOR), mundo)

    assert respuesta.status_code == 201
    linea = [l for l in _lineas(capsys) if l["action"] == "bot.create"]
    assert len(linea) == 1
    assert linea[0]["actor"] == OPERADOR and linea[0]["result"] == "ok" and linea[0]["target"] == respuesta.json()["id"]


def test_el_nombre_y_el_numero_se_recortan(client, mundo, admin):
    respuesta = client.post(
        "/bots",
        json={"name": "  Mi bot  ", "kapso_number_id": "  555  ", "artifact_id": mundo["comp"].id},
        headers=admin,
    )
    assert respuesta.status_code == 201
    assert respuesta.json()["name"] == "Mi bot" and respuesta.json()["kapso_number_id"] == "555"


@pytest.mark.parametrize(
    "cambios",
    [
        {"name": "   "},
        {"name": ""},
        {"kapso_number_id": ""},
        {"kapso_number_id": "   "},
        {"kapso_number_id": "12 34"},
        {"kapso_number_id": "1" * 65},
    ],
)
def test_un_cuerpo_invalido_responde_422(client, mundo, admin, cambios):
    cuerpo = {"name": "Bot", "kapso_number_id": "123", "artifact_id": mundo["comp"].id, **cambios}
    assert client.post("/bots", json=cuerpo, headers=admin).status_code == 422


def test_un_numero_de_64_caracteres_es_valido(client, mundo, admin):
    assert _crear(client, admin, mundo, number="1" * 64).status_code == 201


def test_registrar_con_un_artefacto_inexistente_responde_404(client, mundo, admin):
    respuesta = client.post(
        "/bots", json={"name": "Bot", "kapso_number_id": "1", "artifact_id": "no-existe"}, headers=admin
    )
    assert respuesta.status_code == 404 and respuesta.json()["detail"] == "Artefacto no encontrado."


def test_el_nombre_repetido_responde_409(client, mundo, admin):
    _crear(client, admin, mundo, name="Uno", number="1")
    respuesta = _crear(client, admin, mundo, name="Uno", number="2")
    assert respuesta.status_code == 409 and respuesta.json()["detail"] == "Ya existe un bot llamado 'Uno'."


def test_el_numero_repetido_responde_409(client, mundo, admin):
    _crear(client, admin, mundo, name="Uno", number="1")
    respuesta = _crear(client, admin, mundo, name="Dos", number="1")
    assert respuesta.status_code == 409
    assert respuesta.json()["detail"] == "Ya hay un bot registrado para ese número de Kapso."


# --- Cambios ---------------------------------------------------------------------------------------------------


def test_cambiar_el_artefacto_asignado_cambia_los_dominios_en_la_lectura_siguiente(client, mundo, admin):
    bot = _crear(client, admin, mundo).json()
    assert bot["domains"] == ["Computación / Admisión", "Computación / Plan de estudios"]

    respuesta = client.patch(f"/bots/{bot['id']}", json={"artifact_id": mundo["adm"].id}, headers=admin)

    assert respuesta.status_code == 200
    assert respuesta.json()["artifact"]["name"] == "Bot de Analítica"
    assert respuesta.json()["domains"] == ["Administración de Empresas / Costos"]
    assert client.get("/bots", headers=admin).json()["bots"][0]["domains"] == ["Administración de Empresas / Costos"]


def test_cambiar_los_accesos_del_artefacto_asignado_cambia_los_dominios_del_bot_sin_tocar_el_bot(client, db, mundo, admin):
    bot = _crear(client, admin, mundo).json()

    with db() as session:
        session.add(ArtifactDomain(artifact_id=mundo["comp"].id, domain_id="d-costos"))
        session.commit()

    assert client.get("/bots", headers=admin).json()["bots"][0]["domains"] == [
        "Administración de Empresas / Costos", "Computación / Admisión", "Computación / Plan de estudios",
    ]
    assert bot["id"] == client.get("/bots", headers=admin).json()["bots"][0]["id"]


def test_patch_cambia_lo_enviado_y_deja_lo_demas(client, mundo, admin):
    bot = _crear(client, admin, mundo).json()

    respuesta = client.patch(f"/bots/{bot['id']}", json={"name": "Nuevo nombre"}, headers=admin)

    cambiado = respuesta.json()
    assert cambiado["name"] == "Nuevo nombre"
    assert cambiado["kapso_number_id"] == bot["kapso_number_id"] and cambiado["artifact"] == bot["artifact"]
    assert cambiado["active"] is True

    respuesta = client.patch(f"/bots/{bot['id']}", json={"kapso_number_id": "999"}, headers=admin)
    assert respuesta.json()["kapso_number_id"] == "999" and respuesta.json()["name"] == "Nuevo nombre"


def test_desactivar_y_reactivar_un_bot(client, mundo, admin):
    bot = _crear(client, admin, mundo).json()

    apagado = client.patch(f"/bots/{bot['id']}", json={"active": False}, headers=admin).json()

    assert apagado["active"] is False and apagado["available"] is False
    assert apagado["unavailable_reason"] == "El bot está desactivado."
    # El artefacto sigue activo: se puede seguir usando en otros lugares.
    assert apagado["artifact"]["active"] is True

    encendido = client.patch(f"/bots/{bot['id']}", json={"active": True}, headers=admin).json()
    assert encendido["active"] is True and encendido["available"] is True


def test_un_artefacto_desactivado_deja_al_bot_no_disponible(client, db, mundo, admin):
    bot = _crear(client, admin, mundo).json()
    with db() as session:
        session.get(Artifact, mundo["comp"].id).active = False
        session.commit()

    listado = client.get("/bots", headers=admin).json()["bots"][0]

    assert listado["available"] is False and listado["unavailable_reason"] == "El artefacto asignado está desactivado."
    assert listado["active"] is True and listado["artifact"]["active"] is False
    # Un artefacto desactivado ya no da acceso: los dominios que muestra el bot son los configurados.
    assert bot["id"] == listado["id"]


def test_patch_de_un_bot_inexistente_o_de_un_artefacto_inexistente_responde_404(client, mundo, admin):
    assert client.patch("/bots/no-existe", json={"active": False}, headers=admin).status_code == 404
    bot = _crear(client, admin, mundo).json()
    respuesta = client.patch(f"/bots/{bot['id']}", json={"artifact_id": "no-existe"}, headers=admin)
    assert respuesta.status_code == 404 and respuesta.json()["detail"] == "Artefacto no encontrado."
    assert client.patch("/bots/no-existe", json={"active": False}, headers=admin).json()["detail"] == "Bot no encontrado."


def test_patch_con_un_nombre_o_un_numero_de_otro_bot_responde_409(client, mundo, admin):
    uno = _crear(client, admin, mundo, name="Uno", number="1").json()
    _crear(client, admin, mundo, name="Dos", number="2")
    assert client.patch(f"/bots/{uno['id']}", json={"name": "Dos"}, headers=admin).status_code == 409
    assert client.patch(f"/bots/{uno['id']}", json={"kapso_number_id": "2"}, headers=admin).status_code == 409
    # Conservar el propio nombre y número no es un conflicto.
    assert client.patch(f"/bots/{uno['id']}", json={"name": "Uno", "kapso_number_id": "1"}, headers=admin).status_code == 200


def test_los_cambios_dejan_una_linea_con_el_detalle_y_sin_claves(client, mundo, as_user, capsys):
    headers = as_user(OPERADOR)
    bot = _crear(client, headers, mundo).json()
    capsys.readouterr()

    client.patch(f"/bots/{bot['id']}", json={"artifact_id": mundo["adm"].id}, headers=headers)
    client.patch(f"/bots/{bot['id']}", json={"active": False}, headers=headers)

    lineas = [l for l in _lineas(capsys) if l["action"] == "bot.update"]
    assert [l["detail"] for l in lineas] == ["artefacto: Bot de Computación -> Bot de Analítica", "activo: false"]
    assert all(l["actor"] == OPERADOR and l["result"] == "ok" and l["target"] == bot["id"] for l in lineas)
    assert "mia_" not in json.dumps(lineas)


# --- Alcance y credenciales ------------------------------------------------------------------------------------


def test_sin_credenciales_responde_401(client, mundo):
    assert client.get("/bots").status_code == 401
    assert client.post("/bots", json={"name": "x", "kapso_number_id": "1", "artifact_id": "a"}).status_code == 401
    assert client.patch("/bots/x", json={"active": False}).status_code == 401


def test_un_administrador_de_un_programa_recibe_403_global_only_en_las_cuatro_rutas(client, mundo, as_user, admin):
    bot = _crear(client, admin, mundo).json()
    headers = as_user(COORD)

    respuestas = [
        client.get("/bots", headers=headers),
        client.post("/bots", json={"name": "N", "kapso_number_id": "7", "artifact_id": mundo["comp"].id}, headers=headers),
        client.patch(f"/bots/{bot['id']}", json={"active": False}, headers=headers),
    ]

    for respuesta in respuestas:
        assert respuesta.status_code == 403
        assert respuesta.json()["code"] == "global_only"
    # No se creó ni se cambió nada.
    assert [b["name"] for b in client.get("/bots", headers=admin).json()["bots"]] == ["Atracción de estudiantes"]
    assert client.get("/bots", headers=admin).json()["bots"][0]["active"] is True


def test_el_rechazo_por_alcance_deja_la_linea_rechazado_en_las_escrituras(client, mundo, as_user, admin, capsys):
    bot = _crear(client, admin, mundo).json()
    capsys.readouterr()
    headers = as_user(COORD)

    client.post("/bots", json={"name": "N", "kapso_number_id": "7", "artifact_id": mundo["comp"].id}, headers=headers)
    client.patch(f"/bots/{bot['id']}", json={"active": False}, headers=headers)

    lineas = [l for l in _lineas(capsys) if l["actor"] == COORD]
    assert [(l["action"], l["result"]) for l in lineas] == [("bot.create", "rechazado"), ("bot.update", "rechazado")]


def test_la_clave_de_automatizacion_es_alcance_global(client, mundo, admin):
    assert client.get("/bots", headers=admin).status_code == 200
    assert _crear(client, admin, mundo).status_code == 201


def test_una_clave_de_artefacto_no_administra_bots(client, mundo):
    assert client.get("/bots", headers=mundo["comp"].headers).status_code == 401


def test_no_hay_ruta_para_borrar_un_bot(client, db, mundo, admin):
    bot = _crear(client, admin, mundo).json()
    assert client.delete(f"/bots/{bot['id']}", headers=admin).status_code == 405
    with db() as session:
        assert session.get(Bot, bot["id"]) is not None
