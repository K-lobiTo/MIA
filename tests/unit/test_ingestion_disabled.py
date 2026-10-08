from unittest.mock import patch

from mia.api.routes import domains as domain_routes


def test_subir_documento_con_ingesta_desactivada_responde_503(client, admin):
    with patch.object(domain_routes.settings, "ingestion_enabled", False):
        response = client.post(
            "/domains/dom-1/documents",
            files={"file": ("acta.txt", b"contenido", "text/plain")},
            headers=admin,
        )

    assert response.status_code == 503
    assert "OPERACION.md" in response.json()["detail"]
