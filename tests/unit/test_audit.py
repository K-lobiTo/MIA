"""Registro de quién hizo cada escritura de administración (líneas JSON del logger mia.admin)."""

import json
from unittest.mock import MagicMock

import pytest

from mia.api.routes import domains as domain_routes
from mia.config import settings
from mia.storage.models import Domain, Folder

COORD = "coord.comp@itcr.ac.cr"
OPERADOR = "operador@itcr.ac.cr"


@pytest.fixture
def mundo(db, units, make_admin, tmp_path, monkeypatch):
    with db() as session:
        session.add_all([Domain(id="dc", unit_id=units.comp, name="Currículum"), Domain(id="da", unit_id=units.adm, name="Otro")])
        session.flush()
        session.add(Folder(id="fa", domain_id="da", name="Ajena"))
        session.commit()
    make_admin(COORD, units=["Computación"])
    make_admin(OPERADOR, global_=True)
    monkeypatch.setattr(domain_routes, "ingest_document", MagicMock())
    monkeypatch.setattr(domain_routes, "UPLOAD_DIR", tmp_path / "uploads")
    monkeypatch.setattr(settings, "ingestion_enabled", True)
    return units


def lineas(capsys):
    return [json.loads(linea) for linea in capsys.readouterr().out.splitlines() if linea.startswith("{")]


def test_cada_escritura_deja_una_linea_con_el_correo(client, mundo, as_user, capsys):
    headers = as_user(COORD)
    client.post("/domains", json={"unit_id": mundo.comp, "name": "Tesis"}, headers=headers)
    carpeta = client.post("/domains/dc/folders", json={"name": "Actas"}, headers=headers).json()["id"]
    client.patch(f"/folders/{carpeta}", json={"name": "Actas 2026"}, headers=headers)
    client.post("/domains/dc/documents", files={"file": ("a.pdf", b"x")}, headers=headers)
    client.delete(f"/folders/{carpeta}", headers=headers)
    acciones = [(l["action"], l["actor"], l["result"]) for l in lineas(capsys)]
    assert acciones == [
        ("domain.create", COORD, "ok"),
        ("folder.create", COORD, "ok"),
        ("folder.rename", COORD, "ok"),
        ("document.upload", COORD, "ok"),
        ("folder.delete", COORD, "ok"),
    ]


def test_las_lineas_tienen_fecha_objeto_y_detalle(client, mundo, as_user, capsys):
    client.post("/domains", json={"unit_id": mundo.comp, "name": "Tesis"}, headers=as_user(COORD))
    [linea] = lineas(capsys)
    assert set(linea) == {"ts", "actor", "action", "target", "detail", "result"}
    assert linea["detail"] == "Tesis" and linea["target"] and linea["ts"].endswith("Z")


def test_unidades_artefactos_y_claves(client, mundo, as_user, capsys):
    headers = as_user(OPERADOR)
    unidad = client.post("/units", json={"name": "Nueva"}, headers=headers).json()["id"]
    creado = client.post(
        "/artifacts", json={"name": "Consulta", "modes": ["literal"], "access": {"unit_ids": [unidad]}}, headers=headers
    ).json()
    client.patch(f"/artifacts/{creado['id']}", json={"active": False}, headers=headers)
    nueva_clave = client.post(f"/artifacts/{creado['id']}/key", headers=headers).json()["key"]
    registro = lineas(capsys)
    assert [l["action"] for l in registro] == ["unit.create", "artifact.create", "artifact.update", "artifact.key_regenerate"]
    texto = json.dumps(registro)
    assert creado["key"] not in texto and nueva_clave not in texto


def test_la_clave_de_automatizacion_figura_como_tal(client, mundo, admin, capsys):
    client.post("/domains", json={"unit_id": mundo.comp, "name": "Tesis"}, headers=admin)
    [linea] = lineas(capsys)
    assert linea["actor"] == "automatizacion"


def test_los_rechazos_por_alcance_quedan_anotados(client, mundo, as_user, capsys):
    headers = as_user(COORD)
    client.post("/domains", json={"unit_id": mundo.adm, "name": "X"}, headers=headers)
    client.post("/domains/da/folders", json={"name": "X"}, headers=headers)
    client.post("/units", json={"name": "Otra"}, headers=headers)
    registro = lineas(capsys)
    assert [(l["action"], l["result"], l["actor"]) for l in registro] == [
        ("domain.create", "rechazado", COORD),
        ("folder.create", "rechazado", COORD),
        ("unit.create", "rechazado", COORD),
    ]


def test_ni_las_lecturas_ni_los_tokens_se_registran(client, mundo, as_user, capsys, token_factory):
    headers = as_user(COORD)
    client.get("/inventory", headers=headers)
    client.get("/artifacts", headers=headers)
    client.post("/domains", json={"unit_id": mundo.comp, "name": "Tesis"}, headers=headers)
    salida = capsys.readouterr().out
    assert len([l for l in salida.splitlines() if l.startswith("{")]) == 1
    assert headers["Authorization"].split()[1] not in salida
