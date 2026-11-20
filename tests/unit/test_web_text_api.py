"""Ver el texto extraído de un documento web (feature 022)."""

import json
from unittest.mock import MagicMock

import pytest
from sqlalchemy import event

from mia.api.routes import documents as documents_routes
from mia.api.routes import domains as domain_routes
from mia.api.routes import web_pages as web_pages_routes
from mia.config import settings
from mia.ingestion import pipeline
from mia.storage.models import Domain, Folder
from tests.unit.almacen_falso import AlmacenFalso
from tests.unit.web_de_prueba import FetcherFalso, pagina, pagina_leida

URL = "https://ejemplo.test/programa"
COORD = "coord.comp@itcr.ac.cr"


@pytest.fixture
def mundo(db, units, make_admin, tmp_path, monkeypatch):
    with db() as session:
        session.add_all(
            [
                Domain(id="d1", unit_id=units.comp, name="Currículum"),
                Domain(id="d2", unit_id=units.adm, name="Otro"),
            ]
        )
        session.flush()
        session.add(Folder(id="f2", domain_id="d2", name="Ajena"))
        session.commit()
    make_admin(COORD, units=["Computación"])
    subidas = tmp_path / "uploads"
    subidas.mkdir()
    almacen = AlmacenFalso()
    embeddings = MagicMock()
    embeddings.embed.side_effect = lambda textos, is_query=False: [[0.1, 0.2, 0.3] for _ in textos]
    for modulo in (domain_routes, documents_routes, web_pages_routes, pipeline):
        monkeypatch.setattr(modulo, "UPLOAD_DIR", subidas)
    monkeypatch.setattr(pipeline, "get_vector_store", lambda: almacen)
    monkeypatch.setattr(pipeline, "get_embedding_provider", lambda nombre: embeddings)
    monkeypatch.setattr(pipeline, "SessionLocal", db)
    monkeypatch.setattr(settings, "ingestion_enabled", True)
    monkeypatch.setattr(settings, "ingestion_sync", True)
    falso = FetcherFalso({URL: pagina_leida(pagina("programa.html"), url=URL)})
    monkeypatch.setattr(web_pages_routes, "get_page_fetcher", lambda *a, **k: falso)
    return almacen


def _agregar(client, admin, dominio="d1"):
    return client.post(f"/domains/{dominio}/web-pages", json={"url": URL}, headers=admin)


def test_el_texto_de_un_documento_web_se_devuelve_con_su_direccion_y_su_fecha(client, admin, mundo):
    documento = _agregar(client, admin).json()

    respuesta = client.get(f"/domains/d1/documents/{documento['id']}/text", headers=admin)

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert set(cuerpo) == {"text", "source_url", "read_at", "filename"}
    assert cuerpo["text"].splitlines()[0].startswith(f"Fuente: {URL} (consultada el ")
    assert "cuatro semestres" in cuerpo["text"]
    assert cuerpo["source_url"] == URL and cuerpo["filename"] == "Maestría de Ejemplo"
    assert cuerpo["read_at"] == documento["uploaded_at"]


def test_un_documento_que_no_es_web_responde_404(client, admin, mundo):
    subida = client.post("/domains/d1/documents", files={"file": ("nota.txt", b"Hola mundo")}, headers=admin).json()

    respuesta = client.get(f"/domains/d1/documents/{subida['id']}/text", headers=admin)

    assert respuesta.status_code == 404 and respuesta.json() == {"detail": "Documento no encontrado."}


def test_un_documento_de_otro_dominio_o_inexistente_responde_404(client, admin, mundo):
    documento = _agregar(client, admin).json()

    assert client.get(f"/domains/d2/documents/{documento['id']}/text", headers=admin).status_code == 404
    assert client.get("/domains/d1/documents/no-existe/text", headers=admin).status_code == 404
    assert client.get("/domains/no-existe/documents/x/text", headers=admin).status_code == 404


def test_quien_no_tiene_alcance_sobre_el_dominio_recibe_el_error_de_siempre(client, admin, mundo, as_user):
    documento = _agregar(client, admin, dominio="d2").json()

    respuesta = client.get(f"/domains/d2/documents/{documento['id']}/text", headers=as_user(COORD))

    assert respuesta.status_code in (403, 404)


def test_ver_el_texto_no_escribe_en_la_auditoria(client, admin, mundo, capsys):
    documento = _agregar(client, admin).json()
    capsys.readouterr()

    client.get(f"/domains/d1/documents/{documento['id']}/text", headers=admin)

    assert [x for x in capsys.readouterr().out.splitlines() if x.startswith("{")] == []


def test_listar_el_inventario_y_los_documentos_no_lee_el_texto_extraido(client, admin, mundo, db):
    _agregar(client, admin)
    sentencias = []
    motor = db.kw["bind"]

    def registrar(conexion, cursor, statement, parameters, contexto, executemany):
        sentencias.append(statement)

    event.listen(motor, "before_cursor_execute", registrar)
    try:
        inventario = client.get("/inventory", headers=admin)
        listado = client.get("/domains/d1/documents", headers=admin)
    finally:
        event.remove(motor, "before_cursor_execute", registrar)

    assert inventario.status_code == 200 and listado.status_code == 200
    assert "source_text" not in json.dumps(inventario.json()) and "source_text" not in json.dumps(listado.json())
    assert [s for s in sentencias if "source_text" in s and s.lstrip().upper().startswith("SELECT")] == []


def test_quien_no_tiene_alcance_no_puede_agregar_una_pagina_y_no_se_lee_nada(client, mundo, as_user, capsys, monkeypatch):
    falso = FetcherFalso({URL: pagina_leida(pagina("programa.html"), url=URL)})
    monkeypatch.setattr(web_pages_routes, "get_page_fetcher", lambda *a, **k: falso)
    persona = as_user(COORD)

    ajena = client.post("/domains/d2/web-pages", json={"url": URL}, headers=persona)
    propia = client.post("/domains/d1/web-pages", json={"url": URL}, headers=persona)
    subida = client.post("/domains/d2/documents", files={"file": ("a.txt", b"hola")}, headers=persona)

    assert ajena.status_code == subida.status_code  # el mismo error que subir un archivo a ese dominio
    assert ajena.json() == subida.json()
    assert propia.status_code == 201
    assert falso.pedidas == [URL]  # solo la del dominio con alcance
    lineas = [json.loads(x) for x in capsys.readouterr().out.splitlines() if x.startswith("{")]
    rechazo_de_alcance = [x for x in lineas if x["action"] == "document.add_web" and x["result"] == "rechazado"]
    assert len(rechazo_de_alcance) == 1 and rechazo_de_alcance[0]["target"] == "d2"
    assert rechazo_de_alcance[0]["actor"] == COORD
