"""Servicio de plantillas (feature 020): nombres, contenido, visibilidad, resolución y lectura de archivos."""

import io
import uuid

import pytest
from docx import Document
from fastapi import HTTPException, UploadFile

from mia.config import settings
from mia.storage.models import Artifact, ConsultaUser, ResponseTemplate
from mia.templates import service
from tests.unit.chat_de_prueba import crear_usuario


def test_normalize_name_quita_tildes_y_pasa_a_minusculas():
    assert service.normalize_name("Informe Técnico") == service.normalize_name("informe tecnico")
    assert service.normalize_name("  Ficha   corta ") == "ficha corta"


def test_validate_name():
    assert service.validate_name("  Informe  ") == "Informe"
    for malo in ("", "   ", "a" * 81, "dos\nlíneas"):
        with pytest.raises(HTTPException) as error:
            service.validate_name(malo)
        assert error.value.status_code == 422
    assert "80" in _detalle(lambda: service.validate_name("a" * 81))
    assert service.validate_name("a" * 80) == "a" * 80


def _detalle(accion) -> str:
    with pytest.raises(HTTPException) as error:
        accion()
    return error.value.detail


def test_validate_content(monkeypatch):
    monkeypatch.setattr(settings, "template_max_chars", 200)

    assert service.validate_content("  # Resumen  ") == "# Resumen"
    for malo in ("", "   \n "):
        assert "vacío" in _detalle(lambda m=malo: service.validate_content(m))
    assert "200" in _detalle(lambda: service.validate_content("x" * 201))
    assert service.validate_content("x" * 200) == "x" * 200


def _artefacto(db, nombre="a1") -> Artifact:
    with db() as session:
        artefacto = Artifact(id=nombre, name=nombre, key_hash=f"h{nombre}", key_prefix="mia_xxxx")
        session.add(artefacto)
        session.commit()
        session.refresh(artefacto)
        return artefacto


def _plantilla(session, *, nombre, scope, artifact_id=None, user_id=None) -> ResponseTemplate:
    owner = f"a:{artifact_id}" if scope == "artifact" else f"u:{user_id}"
    plantilla = ResponseTemplate(
        id=str(uuid.uuid4()), scope=scope, owner_key=owner, artifact_id=artifact_id, user_id=user_id,
        name=nombre, name_key=service.normalize_name(nombre), content="# Resumen", created_by="x",
    )
    session.add(plantilla)
    session.commit()
    return plantilla


def test_visible_templates_separa_las_del_artefacto_y_las_personales(db):
    a1, a2 = _artefacto(db, "a1"), _artefacto(db, "a2")
    ana, beto = crear_usuario(db, "ana"), crear_usuario(db, "beto")
    with db() as session:
        _plantilla(session, nombre="Oficial a1", scope="artifact", artifact_id="a1")
        _plantilla(session, nombre="Oficial a2", scope="artifact", artifact_id="a2")
        _plantilla(session, nombre="Ana todos", scope="personal", user_id=ana)
        _plantilla(session, nombre="Ana en a1", scope="personal", artifact_id="a1", user_id=ana)
        _plantilla(session, nombre="Ana en a2", scope="personal", artifact_id="a2", user_id=ana)
        _plantilla(session, nombre="Beto todos", scope="personal", user_id=beto)
        usuario_ana = session.get(ConsultaUser, ana)

        del_artefacto, mias = service.visible_templates(session, a1, usuario_ana)
        assert [t.name for t in del_artefacto] == ["Oficial a1"]
        assert sorted(t.name for t in mias) == ["Ana en a1", "Ana todos"]

        # En el otro artefacto, las limitadas a a1 no aparecen.
        _, mias_a2 = service.visible_templates(session, a2, usuario_ana)
        assert sorted(t.name for t in mias_a2) == ["Ana en a2", "Ana todos"]

        # Sin sesión solo se ven las del artefacto.
        assert service.visible_templates(session, a1, None) == (del_artefacto, [])


def test_resolve_template(db):
    a1 = _artefacto(db, "a1")
    _artefacto(db, "a2")
    ana, beto = crear_usuario(db, "ana"), crear_usuario(db, "beto")
    with db() as session:
        oficial = _plantilla(session, nombre="Oficial", scope="artifact", artifact_id="a1")
        propia = _plantilla(session, nombre="Mía", scope="personal", user_id=ana)
        de_beto = _plantilla(session, nombre="De Beto", scope="personal", user_id=beto)
        solo_a2 = _plantilla(session, nombre="Solo a2", scope="personal", artifact_id="a2", user_id=ana)
        usuario = session.get(ConsultaUser, ana)

        assert service.resolve_template(session, a1, usuario, oficial.id).id == oficial.id
        assert service.resolve_template(session, a1, None, oficial.id).id == oficial.id
        assert service.resolve_template(session, a1, usuario, propia.id).id == propia.id
        # Inexistente, ajena, de otro artefacto o personal sin sesión: el mismo 404 y el mismo mensaje.
        for pedido in (str(uuid.uuid4()), de_beto.id, solo_a2.id, propia.id):
            usuario_pedido = None if pedido == propia.id else usuario
            with pytest.raises(HTTPException) as error:
                service.resolve_template(session, a1, usuario_pedido, pedido)
            assert error.value.status_code == 404 and error.value.detail == "La plantilla ya no está disponible."


def test_contadores_y_nombre_repetido(db):
    _artefacto(db, "a1")
    ana = crear_usuario(db, "ana")
    with db() as session:
        _plantilla(session, nombre="Informe", scope="artifact", artifact_id="a1")
        _plantilla(session, nombre="Informe", scope="personal", user_id=ana)
        otra = _plantilla(session, nombre="Otra", scope="personal", user_id=ana)

        assert service.count_for_artifact(session, "a1") == 1
        assert service.count_for_user(session, ana) == 2
        assert service.name_taken(session, "u:" + ana, "informe") is True
        assert service.name_taken(session, "u:" + ana, "informe", exclude_id=otra.id) is True
        assert service.name_taken(session, "u:" + ana, "otra", exclude_id=otra.id) is False
        assert service.name_taken(session, "a:a1", "otra") is False


# --- extract_text ---


def _docx(tmp_path, nombre="plantilla.docx") -> bytes:
    doc = Document()
    doc.add_heading("Informe de programa", level=1)
    doc.add_paragraph("Resumen", style="List Bullet")
    doc.add_paragraph("Requisitos", style="List Bullet")
    tabla = doc.add_table(rows=1, cols=2)
    tabla.rows[0].cells[0].text = "Sección"
    tabla.rows[0].cells[1].text = "Qué va"
    ruta = tmp_path / nombre
    doc.save(ruta)
    return ruta.read_bytes()


def _subida(nombre, contenido: bytes) -> UploadFile:
    return UploadFile(file=io.BytesIO(contenido), filename=nombre)


def test_extract_text_de_un_docx_conserva_titulos_listas_y_tablas(tmp_path):
    texto = service.extract_text(_subida("p.docx", _docx(tmp_path)), 4000, 1)

    lineas = texto.splitlines()
    assert lineas[0] == "Informe de programa"
    assert lineas.index("Resumen") < lineas.index("Requisitos")
    assert "Sección | Qué va" in lineas


def test_extract_text_de_un_txt_utf8():
    assert service.extract_text(_subida("p.txt", b"# Resumen\r\n- Costos\r\n"), 4000, 1) == "# Resumen\n- Costos"


def test_extract_text_rechaza_el_tipo_el_tamano_el_dano_el_vacio_y_el_exceso(tmp_path):
    assert _detalle(lambda: service.extract_text(_subida("p.pdf", b"%PDF"), 4000, 1)) == "Solo se aceptan archivos .docx o .txt."

    grande = _subida("p.txt", b"x" * (1024 * 1024 + 1))
    with pytest.raises(HTTPException) as error:
        service.extract_text(grande, 4000, 1)
    assert error.value.status_code == 413 and error.value.detail == "El archivo supera el tamaño máximo de 1 MB."

    mensaje = "No se pudo leer el archivo: está dañado o protegido con contraseña."
    assert _detalle(lambda: service.extract_text(_subida("p.docx", b"esto no es un zip"), 4000, 1)) == mensaje
    assert _detalle(lambda: service.extract_text(_subida("p.docx", _docx(tmp_path)[:60]), 4000, 1)) == mensaje
    assert _detalle(lambda: service.extract_text(_subida("p.txt", b"\xff\xfe\x00\xd8"), 4000, 1)) == mensaje

    assert _detalle(lambda: service.extract_text(_subida("p.txt", b"  \n \n"), 4000, 1)) == "El archivo no tiene texto."
    assert (
        _detalle(lambda: service.extract_text(_subida("p.txt", b"x" * 301), 300, 1))
        == "El texto del archivo supera el máximo de 300 caracteres."
    )
    # Justo en el máximo se acepta, sin recortar.
    assert len(service.extract_text(_subida("p.txt", b"x" * 300), 300, 1)) == 300


def test_extract_text_no_deja_archivos_ni_filtra_la_excepcion(tmp_path, monkeypatch):
    temporales = []
    original = service.tempfile.TemporaryDirectory

    class Registrado(original):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            temporales.append(self.name)

    monkeypatch.setattr(service.tempfile, "TemporaryDirectory", Registrado)
    service.extract_text(_subida("p.txt", b"hola"), 4000, 1)
    with pytest.raises(HTTPException) as error:
        service.extract_text(_subida("p.docx", b"basura secreta"), 4000, 1)

    import os

    assert temporales and not any(os.path.exists(t) for t in temporales)
    assert "basura" not in error.value.detail and "Traceback" not in error.value.detail
