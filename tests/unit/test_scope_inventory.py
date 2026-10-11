"""Alcance por unidad en el inventario, dominios, carpetas y documentos (specs/004-acceso-panel-tec, US1)."""

from unittest.mock import MagicMock

import pytest

from mia.api.routes import domains as domain_routes
from mia.config import settings
from mia.storage.models import Document, Domain, Folder

COORD = "coord.comp@itcr.ac.cr"
ADMIN_EMP = "coord.adm@itcr.ac.cr"
OPERADOR = "operador@itcr.ac.cr"


@pytest.fixture
def mundo(db, units, make_admin, make_artifact, tmp_path, monkeypatch):
    """Dos unidades con un dominio, una carpeta y un documento cada una, un dominio sin unidad, y tres personas."""
    with db() as session:
        session.add_all(
            [
                Domain(id="dc", unit_id=units.comp, name="Currículum"),
                Domain(id="da", unit_id=units.adm, name="Currículum"),
                Domain(id="dx", unit_id=None, name="Antiguo"),
            ]
        )
        session.flush()
        session.add_all(
            [Folder(id="fc", domain_id="dc", name="Programas"), Folder(id="fa", domain_id="da", name="Planes")]
        )
        session.flush()
        session.add_all(
            [
                Document(id="docc", domain_id="dc", folder_id="fc", filename="comp.pdf", source_type="pdf",
                         file_hash="h1", status="done"),
                Document(id="doca", domain_id="da", folder_id="fa", filename="adm.pdf", source_type="pdf",
                         file_hash="h2", status="done"),
            ]
        )
        session.commit()
    make_admin(COORD, units=["Computación"])
    make_admin(ADMIN_EMP, units=["Administración de Empresas"])
    make_admin(OPERADOR, global_=True)
    monkeypatch.setattr(domain_routes, "ingest_document", MagicMock())
    monkeypatch.setattr(domain_routes, "UPLOAD_DIR", tmp_path / "uploads")
    monkeypatch.setattr(settings, "ingestion_enabled", True)
    return units


def _nombres_de_unidades(body):
    return [u["name"] for u in body["units"]]


def test_las_lecturas_exigen_credencial(client, mundo):
    for ruta in ("/inventory", "/units", "/domains", "/domains/dc/documents"):
        response = client.get(ruta)
        assert response.status_code == 401, ruta
        assert response.json()["code"] == "unauthenticated"


def test_inventario_de_unidad_solo_trae_su_unidad(client, mundo, as_user):
    body = client.get("/inventory", headers=as_user(COORD)).json()
    assert _nombres_de_unidades(body) == ["Computación"]
    [unidad] = body["units"]
    assert [d["id"] for d in unidad["domains"]] == ["dc"]
    assert unidad["domains"][0]["folders"][0]["documents"][0]["filename"] == "comp.pdf"
    assert body["unassigned_domains"] == []
    assert "adm.pdf" not in str(body)


def test_inventario_global_y_automatizacion_traen_todo(client, mundo, as_user, admin):
    for headers in (as_user(OPERADOR), admin):
        body = client.get("/inventory", headers=headers).json()
        assert sorted(_nombres_de_unidades(body)) == ["Administración de Empresas", "Computación"]
        assert [d["id"] for d in body["unassigned_domains"]] == ["dx"]


def test_unidades_de_la_persona(client, mundo, as_user):
    assert [u["name"] for u in client.get("/units", headers=as_user(ADMIN_EMP)).json()] == [
        "Administración de Empresas"
    ]
    assert len(client.get("/units", headers=as_user(OPERADOR)).json()) == 2


def test_crear_unidad_es_solo_global(client, mundo, as_user):
    response = client.post("/units", json={"name": "Nueva"}, headers=as_user(COORD))
    assert response.status_code == 403 and response.json()["code"] == "global_only"
    assert client.post("/units", json={"name": "Nueva"}, headers=as_user(OPERADOR)).status_code == 201


def test_crear_dominio_en_la_propia_unidad_y_no_en_la_ajena(client, mundo, as_user):
    headers = as_user(COORD)
    propio = client.post("/domains", json={"unit_id": mundo.comp, "name": "Docentes"}, headers=headers)
    assert propio.status_code == 201
    ajeno = client.post("/domains", json={"unit_id": mundo.adm, "name": "Docentes"}, headers=headers)
    assert ajeno.status_code == 403 and ajeno.json()["code"] == "out_of_scope"


def test_visible_to_solo_menciona_artefactos_del_alcance(client, mundo, as_user, make_artifact):
    make_artifact("Consulta Computación", units=[mundo.comp])
    make_artifact("Consulta Administración", units=[mundo.adm])
    make_artifact("Consulta general", all_domains=True)
    body = client.post(
        "/domains", json={"unit_id": mundo.comp, "name": "Tesis"}, headers=as_user(COORD)
    ).json()
    mencionados = set(body["visible_to"]["now"]) | set(body["visible_to"]["needs_enabling"])
    assert mencionados == {"Consulta Computación"}
    global_body = client.post(
        "/domains", json={"unit_id": mundo.comp, "name": "Tesis 2"}, headers=as_user(OPERADOR)
    ).json()
    assert set(global_body["visible_to"]["now"]) == {"Consulta Computación", "Consulta general"}


def test_dominios_sin_clave_de_artefacto_se_filtran_por_alcance(client, mundo, as_user, make_artifact):
    assert [d["id"] for d in client.get("/domains", headers=as_user(COORD)).json()] == ["dc"]
    assert sorted(d["id"] for d in client.get("/domains", headers=as_user(OPERADOR)).json()) == ["da", "dc", "dx"]
    # Con la clave de un artefacto, igual que antes y sin credencial de administración.
    artefacto = make_artifact("Consulta Administración", units=[mundo.adm])
    assert [d["id"] for d in client.get("/domains", headers=artefacto.headers).json()] == ["da"]


def test_documentos_de_un_dominio_ajeno_son_404(client, mundo, as_user):
    propio = client.get("/domains/dc/documents", headers=as_user(COORD))
    assert propio.status_code == 200 and [d["id"] for d in propio.json()] == ["docc"]
    assert client.get("/domains/da/documents", headers=as_user(COORD)).status_code == 404
    assert client.get("/domains/dx/documents", headers=as_user(COORD)).status_code == 404
    assert client.get("/domains/da/documents", headers=as_user(OPERADOR)).status_code == 200


def test_carpetas_en_dominio_propio_y_ajeno(client, mundo, as_user):
    headers = as_user(COORD)
    creada = client.post("/domains/dc/folders", json={"name": "Reglamentos"}, headers=headers)
    assert creada.status_code == 201
    carpeta = creada.json()["id"]
    assert client.patch(f"/folders/{carpeta}", json={"name": "Normas"}, headers=headers).status_code == 200
    assert client.delete(f"/folders/{carpeta}", headers=headers).status_code == 204

    for respuesta in (
        client.post("/domains/da/folders", json={"name": "X"}, headers=headers),
        client.patch("/folders/fa", json={"name": "X"}, headers=headers),
        client.delete("/folders/fa", headers=headers),
    ):
        assert respuesta.status_code == 403 and respuesta.json()["code"] == "out_of_scope"


def test_subir_documentos_en_dominio_propio_y_ajeno(client, mundo, as_user):
    headers = as_user(COORD)
    propio = client.post("/domains/dc/documents", files={"file": ("nuevo.pdf", b"contenido")}, headers=headers)
    assert propio.status_code == 201
    ajeno = client.post("/domains/da/documents", files={"file": ("nuevo.pdf", b"contenido")}, headers=headers)
    assert ajeno.status_code == 403 and ajeno.json()["code"] == "out_of_scope"
    sin_unidad = client.post("/domains/dx/documents", files={"file": ("n.pdf", b"c")}, headers=headers)
    assert sin_unidad.status_code == 403
