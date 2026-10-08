from datetime import UTC, datetime

from mia.config import settings
from mia.storage.models import Document, Domain, Folder, Unit


def _sembrar(db):
    with db() as session:
        session.add_all(
            [
                Unit(id="u1", name="Computación", description="Posgrados en Computación"),
                Unit(id="u2", name="Administración de Empresas", description=""),
                Domain(id="d1", unit_id="u1", name="Memoria del Consejo", description="Actas"),
                Domain(id="d2", unit_id="u1", name="Currículum", description=""),
                Domain(id="d3", unit_id="u2", name="Currículum", description=""),
                Domain(id="d4", unit_id=None, name="Suelto", description=""),
                Folder(id="f1", domain_id="d1", parent_id=None, name="Actas"),
                Folder(id="f2", domain_id="d1", parent_id="f1", name="2025"),
            ]
        )
        session.flush()
        session.add_all(
            [
                Document(id="doc1", domain_id="d1", folder_id="f2", filename="acta-1.pdf", source_type="pdf",
                         file_hash="h1", status="done", uploaded_at=datetime(2026, 10, 7, 12, 0, tzinfo=UTC)),
                Document(id="doc2", domain_id="d1", folder_id="f2", filename="acta-2.pdf", source_type="pdf",
                         file_hash="h2", status="processing"),
                Document(id="doc3", domain_id="d1", folder_id=None, filename="suelto.txt", source_type="txt",
                         file_hash="h3", status="done"),
                Document(id="doc4", domain_id="d3", folder_id=None, filename="plan.docx", source_type="docx",
                         file_hash="h4", status="pending"),
                Document(id="doc5", domain_id="d4", folder_id=None, filename="huerfano.pdf", source_type="pdf",
                         file_hash="h5", status="done"),
            ]
        )
        session.commit()


def test_inventario_devuelve_el_arbol_completo_sin_clave(client, db):
    _sembrar(db)

    response = client.get("/inventory")

    assert response.status_code == 200
    body = response.json()
    assert [u["name"] for u in body["units"]] == ["Administración de Empresas", "Computación"]
    computacion = body["units"][1]
    assert computacion["description"] == "Posgrados en Computación"
    assert [d["name"] for d in computacion["domains"]] == ["Currículum", "Memoria del Consejo"]
    consejo = computacion["domains"][1]
    assert [d["filename"] for d in consejo["documents"]] == ["suelto.txt"]
    actas = consejo["folders"][0]
    assert actas["name"] == "Actas" and actas["parent_id"] is None
    anio = actas["folders"][0]
    assert anio["name"] == "2025" and anio["parent_id"] == "f1"
    assert {d["filename"] for d in anio["documents"]} == {"acta-1.pdf", "acta-2.pdf"}
    primero = next(d for d in anio["documents"] if d["filename"] == "acta-1.pdf")
    assert primero["source_type"] == "pdf" and primero["status"] == "done"
    assert primero["folder_id"] == "f2" and primero["uploaded_at"].startswith("2026-10-07")


def test_cantidad_de_documentos_incluye_las_carpetas_internas(client, db):
    _sembrar(db)

    body = client.get("/inventory").json()

    computacion = next(u for u in body["units"] if u["name"] == "Computación")
    consejo = next(d for d in computacion["domains"] if d["name"] == "Memoria del Consejo")
    assert consejo["document_count"] == 3  # 2 en 2025 (dentro de Actas) y 1 en la raíz
    assert consejo["folders"][0]["document_count"] == 2
    assert consejo["folders"][0]["folders"][0]["document_count"] == 2
    assert computacion["document_count"] == 3
    administracion = next(u for u in body["units"] if u["name"] == "Administración de Empresas")
    assert administracion["document_count"] == 1


def test_dominios_sin_unidad_salen_aparte(client, db):
    _sembrar(db)

    body = client.get("/inventory").json()

    assert [d["name"] for d in body["unassigned_domains"]] == ["Suelto"]
    assert body["unassigned_domains"][0]["document_count"] == 1


def test_inventario_indica_si_la_ingesta_esta_activa(client, db, monkeypatch):
    monkeypatch.setattr(settings, "ingestion_enabled", False)
    assert client.get("/inventory").json()["ingestion_enabled"] is False
    monkeypatch.setattr(settings, "ingestion_enabled", True)
    assert client.get("/inventory").json()["ingestion_enabled"] is True


def test_inventario_vacio(client, db):
    body = client.get("/inventory").json()
    assert body["units"] == [] and body["unassigned_domains"] == []


def test_lista_de_unidades(client, db):
    _sembrar(db)

    response = client.get("/units")

    assert response.status_code == 200
    assert [u["name"] for u in response.json()] == ["Administración de Empresas", "Computación"]
    assert set(response.json()[0]) == {"id", "name", "description"}
