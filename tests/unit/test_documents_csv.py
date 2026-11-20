"""Carga y procesamiento de CSV por la API (feature 021). Los archivos se generan con `csv_de_prueba.py`: datos inventados."""

from unittest.mock import MagicMock

import pytest

from mia.api.routes import documents as documents_routes
from mia.api.routes import domains as domain_routes
from mia.config import settings
from mia.ingestion import pipeline
from mia.storage.models import Domain, Unit
from tests.unit.almacen_falso import AlmacenFalso
from tests.unit.csv_de_prueba import csv_bytes, tabla_inventada


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


def _cursos() -> bytes:
    return csv_bytes(tabla_inventada(3), separador=",", codificacion="utf-8")


def test_subir_un_csv_lo_guarda_y_lo_deja_listo(client, admin, mundo):
    respuesta = _subir(client, admin, "cursos.csv", _cursos())

    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert cuerpo["source_type"] == "csv" and cuerpo["filename"] == "cursos.csv"
    assert cuerpo["status"] == "done" and cuerpo["status_note"] is None
    assert (mundo.subidas / f"{cuerpo['id']}.csv").exists()
    assert mundo.count_chunks(cuerpo["id"]) >= 1


def test_la_extension_en_mayusculas_tambien_se_acepta(client, admin, mundo):
    cuerpo = _subir(client, admin, "CURSOS.CSV", _cursos()).json()

    assert cuerpo["source_type"] == "csv" and cuerpo["status"] == "done"


def test_los_fragmentos_llevan_el_documento_y_la_fila_con_sus_encabezados(client, admin, mundo):
    cuerpo = _subir(client, admin, "cursos.csv", _cursos()).json()

    # El id del documento es el que resuelve la fuente citada (nombre de archivo y dominio): FR-014.
    textos = " ".join(mundo.textos[cuerpo["id"]])
    assert "Código: MC4001" in textos and "Créditos: 4" in textos and "Profesor: Persona 01" in textos


def test_subir_el_mismo_csv_dos_veces_devuelve_el_existente(client, admin, mundo):
    primera = _subir(client, admin, "a.csv", _cursos())
    segunda = _subir(client, admin, "b.csv", _cursos())

    assert primera.status_code == 201
    assert segunda.status_code == 200 and segunda.json()["already_existed"] is True


def test_eliminar_un_csv_borra_su_archivo_y_sus_fragmentos(client, admin, mundo):
    cuerpo = _subir(client, admin, "cursos.csv", _cursos()).json()
    archivo = mundo.subidas / f"{cuerpo['id']}.csv"
    assert archivo.exists() and mundo.count_chunks(cuerpo["id"]) >= 1

    respuesta = client.delete(f"/domains/d1/documents/{cuerpo['id']}", headers=admin)

    assert respuesta.status_code in (200, 204)
    assert not archivo.exists()
    assert mundo.count_chunks(cuerpo["id"]) == 0


def test_un_csv_mayor_que_el_tope_responde_413_y_no_deja_archivo(client, admin, mundo, monkeypatch):
    monkeypatch.setattr(settings, "max_upload_mb", 1)
    contenido = _cursos() + b"x" * (1024 * 1024)

    respuesta = _subir(client, admin, "grande.csv", contenido)

    assert respuesta.status_code == 413
    assert list(mundo.subidas.iterdir()) == []


def test_un_csv_vacio_queda_en_error_con_su_nota_y_no_afecta_a_otro_documento(client, admin, mundo):
    vacio = _subir(client, admin, "vacio.csv", b"")
    bueno = _subir(client, admin, "cursos.csv", _cursos())

    assert vacio.status_code == 201
    assert vacio.json()["status"] == "error" and vacio.json()["status_note"] == "El archivo CSV no tiene contenido."
    assert bueno.json()["status"] == "done"


def test_con_la_ingesta_desactivada_responde_503(client, admin, mundo, monkeypatch):
    monkeypatch.setattr(settings, "ingestion_enabled", False)

    assert _subir(client, admin, "cursos.csv", _cursos()).status_code == 503


# --- Variantes reales por la API (US2) ---


def test_un_csv_de_excel_en_espanol_windows1252_con_punto_y_coma_queda_listo_con_las_tildes_bien(client, admin, mundo):
    from tests.unit.csv_de_prueba import csv_como_el_real

    cuerpo = _subir(client, admin, "Proceso.csv", csv_como_el_real()).json()

    assert cuerpo["status"] == "done" and cuerpo["status_note"] is None
    textos = " ".join(mundo.textos[cuerpo["id"]])
    assert "Título: Ingeniería en Computación" in textos and "Ã" not in textos


@pytest.mark.parametrize(
    "contenido",
    ["Nombre;Edad\r\nAna;31\r\n".encode("utf-16"), b"PK\x03\x04\x00\x00\x00\x00 un xlsx renombrado a csv"],
    ids=["utf16", "xlsx_renombrado"],
)
def test_un_archivo_ilegible_queda_en_error_con_la_sugerencia_sin_afectar_a_otro_documento(client, admin, mundo, contenido):
    malo = _subir(client, admin, "malo.csv", contenido)
    bueno = _subir(client, admin, "cursos.csv", _cursos())

    assert malo.status_code == 201 and malo.json()["status"] == "error"
    assert "no es un CSV de texto en UTF-8 ni en Windows-1252" in malo.json()["status_note"]
    assert "«CSV UTF-8»" in malo.json()["status_note"]
    assert bueno.json()["status"] == "done"


# --- Límites por la API (US4) ---


def test_un_csv_recortado_queda_listo_con_la_nota_y_el_aviso_indexado(client, admin, mundo, monkeypatch):
    monkeypatch.setattr(settings, "max_excel_rows", 100)
    registros = [["Código", "Nombre"], *[[f"A{i}", f"Persona {i:03d}"] for i in range(1, 301)]]

    cuerpo = _subir(client, admin, "largo.csv", csv_bytes(registros, codificacion="utf-8")).json()

    assert cuerpo["status"] == "done"
    assert cuerpo["status_note"] == "El archivo se recortó en la fila 102 por superar el tope de 100 filas."
    assert len(cuerpo["status_note"]) <= 500
    assert "[Aviso: el archivo se recortó en la fila 102" in " ".join(mundo.textos[cuerpo["id"]])
    listado = client.get("/domains/d1/documents", headers=admin).json()
    assert [d["status_note"] for d in listado if d["id"] == cuerpo["id"]] == [cuerpo["status_note"]]


def test_un_csv_con_comillas_sin_cerrar_queda_listo_con_su_nota(client, admin, mundo):
    from tests.unit.csv_de_prueba import csv_con_comilla_sin_cerrar

    cuerpo = _subir(client, admin, "comillas.csv", csv_con_comilla_sin_cerrar()).json()

    assert cuerpo["status"] == "done"
    assert cuerpo["status_note"] == "El archivo tiene comillas sin cerrar: se leyó sin interpretarlas."
