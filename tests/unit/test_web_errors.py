"""Catálogo de rechazos de la lectura de una página web (feature 022)."""

from pathlib import Path

import pytest

from mia.config import settings
from mia.ingestion.web.errors import CATALOGO, WebRejection, rechazo

CODIGOS = {
    "invalid_url", "private_address", "ingestion_disabled", "already_added", "login_required", "bot_blocked",
    "forbidden", "rate_limited", "robots_disallowed", "not_found", "server_error", "unreachable", "tls_error",
    "too_many_redirects", "not_html", "too_large", "no_content", "text_too_large",
}


def test_el_catalogo_tiene_los_18_codigos():
    assert set(CATALOGO) == CODIGOS and len(CATALOGO) == 18


@pytest.mark.parametrize("codigo", sorted(CODIGOS))
def test_cada_codigo_tiene_estado_y_mensaje(codigo):
    exc = rechazo(codigo)

    assert isinstance(exc, WebRejection) and exc.code == codigo
    assert exc.status in {400, 409, 413, 422, 503}
    assert exc.message.strip() and "{" not in exc.message
    assert "\u2014" not in exc.message  # sin guion largo


def test_los_estados_son_los_del_catalogo():
    assert {c: rechazo(c).status for c in CODIGOS} == {
        "invalid_url": 400, "private_address": 400, "ingestion_disabled": 503, "already_added": 409,
        "login_required": 422, "bot_blocked": 422, "forbidden": 422, "rate_limited": 422, "robots_disallowed": 422,
        "not_found": 422, "server_error": 422, "unreachable": 422, "tls_error": 422, "too_many_redirects": 422,
        "not_html": 422, "too_large": 422, "no_content": 422, "text_too_large": 413,
    }


def test_un_estado_de_la_pagina_nunca_se_devuelve_como_estado_de_la_api():
    # Un 401 o un 403 del sitio no pueden ser un 401 o un 403 de MIA: el panel los toma por un problema de sesión.
    assert {401, 403} & {estado for estado, _ in CATALOGO.values()} == set()


def test_los_mensajes_con_datos():
    assert "503" in rechazo("server_error", codigo=503).message
    assert "1 MB" in rechazo("text_too_large", mb=1).message
    assert f"{settings.max_upload_mb} MB" in rechazo("text_too_large").message
    assert "512 KB" in rechazo("too_large", kb=512).message


def test_already_added_conserva_el_documento_en_extra():
    exc = rechazo("already_added", fecha="20 de noviembre de 2026", document_id="doc1", read_at="2026-11-20T10:00:00")

    assert exc.status == 409 and exc.extra == {"document_id": "doc1", "read_at": "2026-11-20T10:00:00"}
    assert "20 de noviembre de 2026" in exc.message
    assert "elimina el documento" in exc.message


def test_el_mensaje_de_ingesta_desactivada_es_el_de_la_subida_de_archivos():
    from mia.api.routes import domains

    fuente = Path(domains.__file__).read_text(encoding="utf-8")

    assert rechazo("ingestion_disabled").message.split(". ")[0] in fuente
