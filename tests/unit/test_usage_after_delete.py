"""Eliminar un documento no cambia el historial, los otros documentos ni los artefactos (feature 012, historia 8)."""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from mia.api.routes import documents as documents_routes
from mia.storage.models import Artifact, Document, Domain, Folder, QueryLog, Unit
from tests.unit.almacen_falso import AlmacenFalso


@pytest.fixture
def almacen(monkeypatch, tmp_path):
    falso = AlmacenFalso()
    monkeypatch.setattr(documents_routes, "get_vector_store", lambda: falso)
    monkeypatch.setattr(documents_routes, "UPLOAD_DIR", tmp_path)
    return falso


@pytest.fixture
def datos(db, admin, almacen):
    with db() as session:
        session.add(Unit(id="u1", name="Computación"))
        session.flush()
        session.add(Domain(id="d1", unit_id="u1", name="Currículum"))
        session.flush()
        session.add(Folder(id="f1", domain_id="d1", name="Vacía tras eliminar"))
        session.flush()
        session.add_all(
            [
                Document(id="citado", domain_id="d1", folder_id="f1", filename="plan.pdf", source_type="pdf", file_hash="h1", status="done"),
                Document(id="otro", domain_id="d1", filename="otro.pdf", source_type="pdf", file_hash="h2", status="done"),
            ]
        )
        session.add(
            Artifact(id="a1", name="Consulta Computación", key_hash="h", key_prefix="mia_aaaa", daily_cap_usd=Decimal("1.5"))
        )
        session.flush()
        session.add(
            QueryLog(
                id="q1", artifact_id="a1", created_at=datetime.now(UTC).replace(tzinfo=None), mode="literal",
                outcome="answered", cost_usd=Decimal("0.002"), question="¿Cuándo es la matrícula?",
                domain_ids='["d1"]', sources='[{"domain": "Currículum", "document": "plan.pdf"}]',
            )
        )
        session.commit()
    almacen.fragmentos.update({"citado": 3, "otro": 3})


def _historial(client, admin):
    listado = client.get("/usage/queries", params={"period": "today"}, headers=admin)
    detalle = client.get("/usage/queries/q1", headers=admin)
    csv = client.get("/usage/queries", params={"period": "today", "format": "csv", "include_questions": "true"}, headers=admin)
    assert listado.status_code == detalle.status_code == csv.status_code == 200
    return listado.json(), detalle.json(), csv.text


def test_el_historial_de_uso_queda_igual_con_el_nombre_del_documento_citado(client, datos, admin):
    antes = _historial(client, admin)
    assert "plan.pdf" in antes[1]["sources"][0]["document"]

    assert client.delete("/domains/d1/documents/citado", headers=admin).status_code == 204

    assert _historial(client, admin) == antes


def test_los_otros_documentos_y_los_artefactos_no_cambian(client, db, datos, admin, almacen):
    with db() as session:
        artefacto = session.get(Artifact, "a1")
        antes = (artefacto.key_hash, artefacto.key_prefix, artefacto.daily_cap_usd, artefacto.active)

    client.delete("/domains/d1/documents/citado", headers=admin)

    with db() as session:
        otro = session.get(Document, "otro")
        assert otro.status == "done" and otro.domain_id == "d1"
        artefacto = session.get(Artifact, "a1")
        assert (artefacto.key_hash, artefacto.key_prefix, artefacto.daily_cap_usd, artefacto.active) == antes
        assert session.get(Domain, "d1") is not None
    assert almacen.count_chunks("otro") == 3


def test_el_dominio_y_la_carpeta_quedan_vacios_y_la_carpeta_se_puede_borrar_con_la_accion_de_siempre(client, datos, admin):
    # Con el documento dentro, la carpeta no se puede borrar.
    assert client.delete("/folders/f1", headers=admin).status_code == 409

    client.delete("/domains/d1/documents/citado", headers=admin)

    assert client.delete("/folders/f1", headers=admin).status_code == 204
    inventario = client.get("/inventory", headers=admin).json()
    assert any(d["id"] == "d1" for u in inventario["units"] for d in u["domains"])
