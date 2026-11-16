"""Carga y procesamiento de libros de Excel por la API (feature 018)."""

from unittest.mock import MagicMock

import pytest

from mia.api.routes import documents as documents_routes
from mia.api.routes import domains as domain_routes
from mia.config import settings
from mia.ingestion import pipeline
from mia.storage.models import Domain, Unit
from tests.unit.almacen_falso import AlmacenFalso
from tests.unit.libros_de_prueba import hacer_libro, libro_de_cursos


@pytest.fixture
def mundo(db, tmp_path, monkeypatch):
    with db() as session:
        session.add(Unit(id="u1", name="Computación", description=""))
        session.add(Domain(id="d1", unit_id="u1", name="Currículum", description=""))
        session.commit()
    subidas = tmp_path / "uploads"
    subidas.mkdir()
    almacen = AlmacenFalso()
    embeddings = MagicMock()
    embeddings.embed.side_effect = lambda textos, is_query=False: [[0.1, 0.2, 0.3] for _ in textos]
    for modulo in (domain_routes, documents_routes, pipeline):
        monkeypatch.setattr(modulo, "UPLOAD_DIR", subidas)
    monkeypatch.setattr(documents_routes, "get_vector_store", lambda: almacen)
    monkeypatch.setattr(pipeline, "get_vector_store", lambda: almacen)
    monkeypatch.setattr(pipeline, "get_embedding_provider", lambda nombre: embeddings)
    monkeypatch.setattr(pipeline, "SessionLocal", db)
    monkeypatch.setattr(settings, "ingestion_enabled", True)
    monkeypatch.setattr(settings, "ingestion_sync", True)
    almacen.subidas = subidas
    return almacen


def _subir(client, admin, nombre, contenido):
    return client.post("/domains/d1/documents", files={"file": (nombre, contenido)}, headers=admin)


def _bytes(ruta) -> bytes:
    return ruta.read_bytes()


def test_subir_un_xlsx_lo_guarda_y_lo_deja_listo(client, admin, mundo, tmp_path):
    contenido = _bytes(libro_de_cursos(tmp_path / "cursos.xlsx"))

    respuesta = _subir(client, admin, "horarios.xlsx", contenido)

    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert cuerpo["source_type"] == "xlsx" and cuerpo["filename"] == "horarios.xlsx"
    assert cuerpo["status"] == "done" and cuerpo["status_note"] is None
    assert (mundo.subidas / f"{cuerpo['id']}.xlsx").exists()
    assert mundo.count_chunks(cuerpo["id"]) >= 1


@pytest.mark.parametrize("nombre", ["datos.csv", "datos.xls", "datos.xlsm"])
def test_los_demas_formatos_de_hoja_se_rechazan_con_los_tipos_aceptados(client, admin, mundo, nombre):
    respuesta = _subir(client, admin, nombre, b"x")

    assert respuesta.status_code == 400
    extension = nombre.rsplit(".", 1)[1]
    assert respuesta.json()["detail"] == (
        f"Tipo de fuente no soportado: {extension}. Tipos aceptados: pdf, docx, txt, xlsx."
    )


def test_subir_el_mismo_libro_dos_veces_devuelve_el_existente(client, admin, mundo, tmp_path):
    contenido = _bytes(libro_de_cursos(tmp_path / "cursos.xlsx"))

    primera = _subir(client, admin, "a.xlsx", contenido)
    segunda = _subir(client, admin, "b.xlsx", contenido)

    assert primera.status_code == 201
    assert segunda.status_code == 200 and segunda.json()["already_existed"] is True


def test_un_libro_danado_queda_en_error_con_su_nota(client, admin, mundo):
    respuesta = _subir(client, admin, "roto.xlsx", b"no es un libro")

    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert cuerpo["status"] == "error"
    assert "dañado o protegido con contraseña" in cuerpo["status_note"]


def test_un_libro_sin_contenido_queda_en_error_con_su_nota(client, admin, mundo, tmp_path):
    contenido = _bytes(hacer_libro(tmp_path / "vacio.xlsx", {"H": [[None]]}))

    cuerpo = _subir(client, admin, "vacio.xlsx", contenido).json()

    assert cuerpo["status"] == "error"
    assert "no tiene hojas visibles con contenido" in cuerpo["status_note"]


def test_un_xlsx_mayor_que_el_tope_responde_413_y_no_deja_archivo(client, admin, mundo, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "max_upload_mb", 1)
    contenido = _bytes(libro_de_cursos(tmp_path / "cursos.xlsx")) + b"\0" * (1024 * 1024)  # supera 1 MB

    respuesta = _subir(client, admin, "grande.xlsx", contenido)

    assert respuesta.status_code == 413
    assert list(mundo.subidas.iterdir()) == []


def test_eliminar_un_xlsx_borra_su_archivo_y_sus_fragmentos(client, admin, mundo, tmp_path):
    contenido = _bytes(libro_de_cursos(tmp_path / "cursos.xlsx"))
    cuerpo = _subir(client, admin, "cursos.xlsx", contenido).json()
    archivo = mundo.subidas / f"{cuerpo['id']}.xlsx"
    assert archivo.exists() and mundo.count_chunks(cuerpo["id"]) >= 1

    respuesta = client.delete(f"/domains/d1/documents/{cuerpo['id']}", headers=admin)

    assert respuesta.status_code in (200, 204)
    assert not archivo.exists()
    assert mundo.count_chunks(cuerpo["id"]) == 0


def test_el_cargador_no_ejecuta_macros_y_xlsm_no_es_un_tipo_aceptado():
    # `read_only=True` solo lee los valores de las celdas: no hay ejecución de macros ni de vínculos (FR-011).
    from pathlib import Path

    from mia.ingestion.loaders import xlsx_loader

    assert "read_only=True" in Path(xlsx_loader.__file__).read_text(encoding="utf-8")


def test_un_libro_recortado_queda_listo_con_la_nota_y_el_aviso_indexado(client, admin, mundo, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "max_excel_rows", 100)
    ruta = hacer_libro(tmp_path / "largo.xlsx", {"H": [["nombre", "valor"], *[[f"fila-{i}", i] for i in range(1, 301)]]})

    cuerpo = _subir(client, admin, "largo.xlsx", _bytes(ruta)).json()

    assert cuerpo["status"] == "done"
    assert cuerpo["status_note"].startswith("El libro se recortó en la fila")
    assert mundo.count_chunks(cuerpo["id"]) >= 1
