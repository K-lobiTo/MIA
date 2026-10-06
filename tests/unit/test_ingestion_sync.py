from unittest.mock import patch

from fastapi.testclient import TestClient

from mia.api.main import app
from mia.api.routes import domains as domain_routes
from mia.storage.db import SessionLocal
from mia.storage.models import Document


def _marcar_listo(document_id: str) -> None:
    with SessionLocal() as session:
        session.get(Document, document_id).status = "done"
        session.commit()


def test_con_ingesta_sincrona_la_respuesta_trae_el_estado_final():
    client = TestClient(app)
    domain = client.post("/domains", json={"name": "Dominio ingesta síncrona"}).json()

    with (
        patch.object(domain_routes.settings, "ingestion_sync", True),
        patch.object(domain_routes, "ingest_document", side_effect=_marcar_listo) as ingest,
    ):
        response = client.post(
            f"/domains/{domain['id']}/documents",
            files={"file": ("acta-sincrona.txt", b"contenido sincrono", "text/plain")},
        )

    assert response.status_code == 200
    assert response.json()["status"] == "done"
    ingest.assert_called_once_with(response.json()["id"])
