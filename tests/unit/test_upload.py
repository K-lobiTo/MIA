from unittest.mock import MagicMock

import pytest

from mia.api.routes import domains as domain_routes
from mia.config import settings
from mia.storage.models import Document, Domain, Folder, Unit


@pytest.fixture
def base(db, tmp_path, monkeypatch):
    with db() as session:
        session.add(Unit(id="u1", name="Computación", description=""))
        session.add_all(
            [
                Domain(id="d1", unit_id="u1", name="Currículum", description=""),
                Domain(id="d2", unit_id="u1", name="Docentes", description=""),
            ]
        )
        session.flush()
        session.add_all(
            [
                Folder(id="f1", domain_id="d1", parent_id=None, name="Programas"),
                Folder(id="f2", domain_id="d1", parent_id=None, name="Reglamentos"),
                Folder(id="f-otro", domain_id="d2", parent_id=None, name="Ajena"),
            ]
        )
        session.commit()
    # Sin ingesta real: solo interesa lo que hace la ruta antes de procesar.
    ingesta = MagicMock()
    monkeypatch.setattr(domain_routes, "ingest_document", ingesta)
    monkeypatch.setattr(domain_routes, "UPLOAD_DIR", tmp_path / "uploads")
    monkeypatch.setattr(settings, "ingestion_enabled", True)
    return ingesta


def _subir(client, admin, nombre="acta.pdf", contenido=b"contenido", dominio="d1", carpeta=None):
    datos = {"folder_id": carpeta} if carpeta else None
    return client.post(
        f"/domains/{dominio}/documents", files={"file": (nombre, contenido)}, data=datos, headers=admin
    )


def test_subir_documento_exige_clave(client, admin, base):
    response = client.post("/domains/d1/documents", files={"file": ("a.pdf", b"x")})
    assert response.status_code == 401


def test_subir_documento_nuevo_responde_201_y_lo_deja_en_cola(client, admin, base):
    response = _subir(client, admin)

    assert response.status_code == 201
    body = response.json()
    assert body["filename"] == "acta.pdf" and body["source_type"] == "pdf"
    assert body["status"] == "pending" and body["already_existed"] is False and body["folder_id"] is None
    base.assert_called_once_with(body["id"])


def test_subir_a_una_carpeta(client, admin, base):
    response = _subir(client, admin, carpeta="f1")

    assert response.status_code == 201 and response.json()["folder_id"] == "f1"


def test_carpeta_inexistente_o_de_otro_dominio(client, admin, base):
    assert _subir(client, admin, carpeta="no-existe").status_code == 404
    assert _subir(client, admin, carpeta="f-otro").status_code == 422


def test_dominio_inexistente_responde_404(client, admin, base):
    assert _subir(client, admin, dominio="no-existe").status_code == 404


def test_tipo_no_soportado_responde_400(client, admin, base):
    response = _subir(client, admin, nombre="foto.png")

    assert response.status_code == 400
    assert "png" in response.json()["detail"]


def test_archivo_mayor_al_limite_responde_413(client, admin, base, monkeypatch):
    monkeypatch.setattr(settings, "max_upload_mb", 1)

    grande = _subir(client, admin, contenido=b"x" * (1024 * 1024 + 1))
    justo = _subir(client, admin, nombre="otro.pdf", contenido=b"x" * (1024 * 1024))

    assert grande.status_code == 413
    assert "1 MB" in grande.json()["detail"]
    assert justo.status_code == 201


def test_mismo_contenido_en_otra_carpeta_del_dominio_ya_existia(client, admin, base):
    primero = _subir(client, admin, carpeta="f1")
    segundo = _subir(client, admin, nombre="copia.pdf", carpeta="f2")

    assert primero.status_code == 201
    assert segundo.status_code == 200
    body = segundo.json()
    assert body["already_existed"] is True and body["id"] == primero.json()["id"]
    assert body["folder_id"] == "f1"  # se devuelve el documento existente, sin moverlo
    assert base.call_count == 1  # no se vuelve a procesar


def test_el_mismo_contenido_en_otro_dominio_es_un_documento_nuevo(client, admin, base, db):
    _subir(client, admin, dominio="d1")
    otro = _subir(client, admin, dominio="d2")

    assert otro.status_code == 201 and otro.json()["already_existed"] is False
    with db() as session:
        assert session.query(Document).count() == 2


def test_con_la_ingesta_desactivada_responde_503(client, admin, base, monkeypatch):
    monkeypatch.setattr(settings, "ingestion_enabled", False)

    assert _subir(client, admin).status_code == 503


def test_la_lista_de_documentos_incluye_la_carpeta(client, admin, base):
    _subir(client, admin, carpeta="f1")

    documentos = client.get("/domains/d1/documents").json()

    assert documentos[0]["folder_id"] == "f1" and documentos[0]["status"] == "pending"
