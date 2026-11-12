"""Rutas de administración de contactos (feature 017): GET /contacts (JSON y CSV), DELETE /contacts/{id} y DELETE /contacts,
solo con alcance global, con auditoría sin datos personales."""

import csv
import io
import json
from datetime import timedelta

import pytest
from sqlalchemy import func, select

from mia.storage.models import Bot, WhatsAppContact, _now

COORD = "coord.comp@itcr.ac.cr"
OPERADOR = "operador@itcr.ac.cr"
PERSONALES = ("+50610000002", "beto@correo.com", "Beto Mora", "+50610000003")


@pytest.fixture
def mundo(db, units, make_admin):
    make_admin(COORD, units=["Computación"])
    make_admin(OPERADOR, global_=True)
    ahora = _now()
    with db() as session:
        session.add_all([Bot(id="b1", name="Posgrados computación", kapso_number_id="111"), Bot(id="b2", name="Analítica", kapso_number_id="222")])
        session.flush()
        filas = [
            ("c0", "b1", "+50610000001", None, None, "pendiente", 0),
            ("c1", "b1", "+50610000002", "Beto Mora", "beto@correo.com", "entrego", 1),
            ("c2", "b1", "+50610000003", None, None, "declino", 2),
            ("c3", "b2", "+50610000004", "Dani", None, "entrego", 3),
            ("c4", "b2", "+50610000005", "=1+1", "x@y.cr", "entrego", 4),
        ]
        for id_, bot, tel, nombre, correo, estado, minutos in filas:
            session.add(
                WhatsAppContact(
                    id=id_, bot_id=bot, phone=tel, name=nombre, email=correo, status=estado,
                    created_at=ahora + timedelta(minutes=minutos), last_seen_at=ahora, updated_at=ahora,
                )
            )
        session.commit()


def _lineas(capsys):
    return [json.loads(linea) for linea in capsys.readouterr().out.splitlines() if linea.startswith("{")]


def _total(db):
    with db() as session:
        return session.scalar(select(func.count()).select_from(WhatsAppContact))


# --- permisos ---


def test_una_cuenta_de_programa_recibe_403_en_las_tres_rutas_y_queda_rechazado(client, db, mundo, as_user, capsys):
    capsys.readouterr()
    cabeceras = as_user(COORD)

    respuestas = [
        client.get("/contacts", headers=cabeceras),
        client.get("/contacts", params={"format": "csv"}, headers=cabeceras),
        client.delete("/contacts/c0", headers=cabeceras),
        client.delete("/contacts", params={"expected": 5}, headers=cabeceras),
    ]

    assert [r.status_code for r in respuestas] == [403, 403, 403, 403]
    assert all(r.json()["code"] == "global_only" for r in respuestas)
    assert _total(db) == 5
    rechazos = [l for l in _lineas(capsys) if l["result"] == "rechazado"]
    assert len(rechazos) >= 3 and all(l["action"].startswith("contact.") for l in rechazos)


def test_sin_credencial_responde_401_y_una_cuenta_global_puede(client, db, mundo, as_user, admin):
    assert client.get("/contacts").status_code == 401
    assert client.get("/contacts", headers=as_user(OPERADOR)).status_code == 200
    assert client.get("/contacts", headers=admin).status_code == 200


# --- lista ---


def test_la_lista_va_de_la_mas_reciente_a_la_mas_antigua_con_total_y_resumen(client, mundo, admin):
    cuerpo = client.get("/contacts", params={"page_size": 3}, headers=admin).json()

    assert (cuerpo["total"], cuerpo["page"], cuerpo["page_size"]) == (5, 1, 3)
    assert [c["id"] for c in cuerpo["items"]] == ["c4", "c3", "c2"]
    assert cuerpo["summary"] == {"pendiente": 1, "invitada": 0, "entrego": 3, "declino": 1}
    primero = cuerpo["items"][1]
    assert primero["bot"] == {"id": "b2", "name": "Analítica"} and primero["phone"] == "+50610000004"
    assert set(primero) == {"id", "phone", "bot", "name", "email", "status", "created_at", "last_seen_at", "updated_at"}
    siguiente = client.get("/contacts", params={"page_size": 3, "page": 2}, headers=admin).json()
    assert [c["id"] for c in siguiente["items"]] == ["c1", "c0"]


@pytest.mark.parametrize("params", [{"page": 0}, {"page_size": 0}, {"page_size": 201}, {"status": "inventado"}, {"format": "xml"}])
def test_parametros_invalidos_responden_422(client, mundo, admin, params):
    assert client.get("/contacts", params=params, headers=admin).status_code == 422


def test_los_filtros_combinan_y_el_resumen_ignora_el_de_estado(client, mundo, admin):
    def ids(**params):
        return sorted(c["id"] for c in client.get("/contacts", params=params, headers=admin).json()["items"])

    assert ids(bot_id="b2") == ["c3", "c4"]
    assert ids(status=["pendiente", "declino"]) == ["c0", "c2"]
    assert ids(has_email="true") == ["c1", "c4"]
    assert ids(bot_id="b1", status="entrego", has_email="true") == ["c1"]
    resumen = client.get("/contacts", params={"status": "declino", "bot_id": "b2"}, headers=admin).json()["summary"]
    assert resumen == {"pendiente": 0, "invitada": 0, "entrego": 2, "declino": 0}


# --- CSV ---


def test_el_csv_trae_todo_lo_filtrado_con_bom_columnas_y_nombre_de_archivo(client, mundo, admin, capsys):
    capsys.readouterr()

    respuesta = client.get("/contacts", params={"format": "csv", "page_size": 1, "status": "entrego"}, headers=admin)

    assert respuesta.status_code == 200
    assert respuesta.headers["content-type"].startswith("text/csv")
    assert respuesta.headers["content-disposition"].startswith('attachment; filename="mia-contactos-')
    assert respuesta.headers["content-disposition"].endswith('.csv"')
    assert respuesta.content.startswith("﻿".encode())
    filas = list(csv.reader(io.StringIO(respuesta.text.lstrip("﻿"))))
    assert filas[0] == ["telefono", "bot", "nombre", "correo", "estado", "creado", "ultimo_mensaje", "actualizado"]
    assert len(filas) == 1 + 3  # todas las de "entrego", no una página
    assert filas[1][1:5] == ["Analítica", "'=1+1", "x@y.cr", "entrego"]


def test_el_csv_neutraliza_formulas_incluido_el_telefono(client, mundo, admin):
    filas = list(csv.reader(io.StringIO(client.get("/contacts", params={"format": "csv"}, headers=admin).text.lstrip("﻿"))))

    assert all(fila[0].startswith("'+") for fila in filas[1:])  # el teléfono empieza con "+"
    assert "'=1+1" in [fila[2] for fila in filas]


def test_el_csv_se_audita_sin_los_datos(client, mundo, admin, capsys):
    capsys.readouterr()
    client.get("/contacts", params={"format": "csv", "bot_id": "b1", "status": "entrego", "has_email": "true"}, headers=admin)

    [linea] = [l for l in _lineas(capsys) if l["action"] == "contact.export"]
    assert linea["result"] == "ok" and linea["actor"] == "automatizacion" and linea["target"] == ""
    assert linea["detail"].startswith("filas=1;") and "bot:b1" in linea["detail"] and "estado:entrego" in linea["detail"]
    assert not any(dato in json.dumps(linea) for dato in PERSONALES)


def test_mas_de_50000_filas_pide_filtrar(client, mundo, admin, monkeypatch):
    from mia.api.routes import contacts

    monkeypatch.setattr(contacts, "MAX_CSV_ROWS", 3)

    respuesta = client.get("/contacts", params={"format": "csv"}, headers=admin)

    assert respuesta.status_code == 422 and "filtr" in respuesta.json()["detail"].lower()
    assert client.get("/contacts", params={"format": "csv", "bot_id": "b1"}, headers=admin).status_code == 200


def test_la_lista_en_json_no_se_audita_fila_por_fila(client, mundo, admin, capsys):
    capsys.readouterr()
    client.get("/contacts", headers=admin)
    assert [l for l in _lineas(capsys) if l["action"].startswith("contact.")] == []


# --- borrado ---


def test_borrar_un_contacto_responde_204_audita_el_id_y_la_persona_vuelve_a_ser_nueva(client, db, mundo, admin, capsys, monkeypatch):
    from mia.config import settings

    capsys.readouterr()

    assert client.delete("/contacts/c1", headers=admin).status_code == 204

    assert _total(db) == 4
    [linea] = [l for l in _lineas(capsys) if l["action"] == "contact.delete"]
    assert linea["target"] == "c1" and not any(dato in json.dumps(linea) for dato in PERSONALES)
    assert client.delete("/contacts/c1", headers=admin).status_code == 404
    # Si esa persona escribe de nuevo, es una persona nueva (pendiente).
    monkeypatch.setattr(settings, "bot_service_key", "k")
    respuesta = client.post("/bot/messages", json={"number_id": "111", "received": 1, "phone": "+50610000002"}, headers={"X-Bot-Service-Key": "k"})
    assert respuesta.json()["contact"]["status"] == "pendiente"


def test_el_borrado_masivo_exige_expected_y_el_conteo_exacto(client, db, mundo, admin):
    assert client.delete("/contacts", params={"status": "entrego"}, headers=admin).status_code == 422

    desactualizado = client.delete("/contacts", params={"status": "entrego", "expected": 2}, headers=admin)
    assert desactualizado.status_code == 409 and desactualizado.json()["count"] == 3
    assert _total(db) == 5  # no borró nada

    hecho = client.delete("/contacts", params={"status": "entrego", "expected": 3}, headers=admin)
    assert hecho.status_code == 200 and hecho.json() == {"deleted": 3}
    assert _total(db) == 2


def test_el_borrado_masivo_respeta_los_filtros_y_sin_filtros_borra_todo(client, db, mundo, admin, capsys):
    capsys.readouterr()
    assert client.delete("/contacts", params={"bot_id": "b2", "expected": 2}, headers=admin).json() == {"deleted": 2}
    with db() as session:
        assert {c.id for c in session.scalars(select(WhatsAppContact))} == {"c0", "c1", "c2"}

    assert client.delete("/contacts", params={"expected": 3}, headers=admin).json() == {"deleted": 3}
    assert _total(db) == 0
    lineas = [l for l in _lineas(capsys) if l["action"] == "contact.delete_filtered"]
    assert [l["detail"].split(";")[0] for l in lineas] == ["borrados=2", "borrados=3"]
    assert not any(dato in json.dumps(lineas) for dato in PERSONALES)


def test_el_borrado_masivo_con_el_conteo_cambiado_no_audita_un_borrado(client, mundo, admin, capsys):
    capsys.readouterr()
    client.delete("/contacts", params={"expected": 1}, headers=admin)
    assert [l for l in _lineas(capsys) if l["action"] == "contact.delete_filtered"] == []
