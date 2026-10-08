from unittest.mock import patch

from mia.api.routes import domains as domain_routes
from mia.storage.models import Document, Unit


def test_con_ingesta_sincrona_la_respuesta_trae_el_estado_final(client, admin, db, tmp_path):
    with db() as session:
        session.add(Unit(id="u1", name="Computación", description=""))
        session.commit()
    domain = client.post(
        "/domains", json={"unit_id": "u1", "name": "Dominio ingesta síncrona"}, headers=admin
    ).json()

    def _marcar_listo(document_id: str) -> None:
        with db() as session:
            session.get(Document, document_id).status = "done"
            session.commit()

    with (
        patch.object(domain_routes.settings, "ingestion_sync", True),
        patch.object(domain_routes, "UPLOAD_DIR", tmp_path / "uploads"),
        patch.object(domain_routes, "ingest_document", side_effect=_marcar_listo) as ingest,
    ):
        response = client.post(
            f"/domains/{domain['id']}/documents",
            files={"file": ("acta-sincrona.txt", b"contenido sincrono", "text/plain")},
            headers=admin,
        )

    assert response.status_code == 201
    assert response.json()["status"] == "done"
    ingest.assert_called_once_with(response.json()["id"])
