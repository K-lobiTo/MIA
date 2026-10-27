"""Servicio de eliminación de documentos (feature 012): orden, restos y fallas, con un almacén de vectores simulado."""

import uuid

import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from mia.ingestion import removal
from mia.ingestion.removal import DocumentNotFound, StoreUnavailable, remove_document
from mia.storage.models import Base, Document, DocumentImage, Domain
from tests.unit.almacen_falso import AlmacenFalso


@pytest.fixture
def fabrica(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


@pytest.fixture
def subidas(tmp_path):
    carpeta = tmp_path / "uploads"
    carpeta.mkdir()
    return carpeta


def _documento(fabrica, subidas, almacen, *, dominio=None, nombre="Admision.txt", imagenes=1, hash_="h", archivo=True):
    with fabrica() as session:
        if dominio is None:
            dominio = str(uuid.uuid4())
            session.add(Domain(id=dominio, name=f"Dominio {dominio[:4]}", description=""))
            session.commit()
        documento = str(uuid.uuid4())
        session.add(
            Document(
                id=documento, domain_id=dominio, filename=nombre, source_type="txt", file_hash=hash_, status="done"
            )
        )
        session.commit()
        for posicion in range(imagenes):
            session.add(
                DocumentImage(
                    id=str(uuid.uuid4()), document_id=documento, public_id=uuid.uuid4().hex + "ab",
                    content_type="image/png", content=b"png", size_bytes=3, position=posicion, created_by="x",
                )
            )
        session.commit()
    if archivo:
        (subidas / f"{documento}.txt").write_text("contenido", encoding="utf-8")
    almacen.fragmentos[documento] = 4
    return dominio, documento


def _eliminar(fabrica, subidas, almacen, documento_id, espera=1):
    with fabrica() as session:
        documento = session.get(Document, documento_id)
        remove_document(session, almacen, documento, subidas, espera)


def _existe(fabrica, documento_id):
    with fabrica() as session:
        return session.get(Document, documento_id) is not None


def _imagenes(fabrica, documento_id):
    with fabrica() as session:
        return session.scalar(
            select(func.count()).select_from(DocumentImage).where(DocumentImage.document_id == documento_id)
        )


def test_elimina_la_fila_las_imagenes_los_fragmentos_y_el_archivo(fabrica, subidas):
    almacen = AlmacenFalso()
    _, documento = _documento(fabrica, subidas, almacen, imagenes=2)

    _eliminar(fabrica, subidas, almacen, documento)

    assert not _existe(fabrica, documento)
    assert _imagenes(fabrica, documento) == 0
    assert almacen.count_chunks(documento) == 0
    assert not (subidas / f"{documento}.txt").exists()


def test_un_documento_que_no_existe_lanza_not_found(fabrica, subidas):
    with fabrica() as session:
        documento = Document(id="x", domain_id="d", filename="a.txt", source_type="txt", file_hash="h")
        # No está en la base: remove_document debe notarlo al intentar borrarlo.
        with pytest.raises(DocumentNotFound):
            remove_document(session, AlmacenFalso(), documento, subidas, 1)


def test_los_fragmentos_se_borran_con_la_fila_ya_borrada_pero_sin_confirmar(fabrica, subidas):
    almacen = AlmacenFalso()
    _, documento = _documento(fabrica, subidas, almacen)
    visto = {}

    def al_borrar(document_id):
        # Otra sesión todavía ve el documento y sus imágenes: la transacción no se confirmó.
        visto["documento"] = _existe(fabrica, document_id)
        visto["imagenes"] = _imagenes(fabrica, document_id)

    almacen.al_borrar = al_borrar

    _eliminar(fabrica, subidas, almacen, documento)

    assert visto == {"documento": True, "imagenes": 1}
    assert not _existe(fabrica, documento)


@pytest.mark.parametrize("modo", ["falla", "deja_fragmentos"])
def test_si_falla_el_almacen_el_documento_y_sus_imagenes_siguen_y_el_reintento_funciona(fabrica, subidas, modo):
    almacen = AlmacenFalso()
    _, documento = _documento(fabrica, subidas, almacen, imagenes=2)
    almacen.falla_al_borrar = modo == "falla"
    almacen.no_borra = modo == "deja_fragmentos"

    with pytest.raises(StoreUnavailable):
        _eliminar(fabrica, subidas, almacen, documento)

    assert _existe(fabrica, documento)
    assert _imagenes(fabrica, documento) == 2
    assert (subidas / f"{documento}.txt").exists()

    almacen.falla_al_borrar = almacen.no_borra = False
    _eliminar(fabrica, subidas, almacen, documento)

    assert not _existe(fabrica, documento)
    assert _imagenes(fabrica, documento) == 0
    assert almacen.count_chunks(documento) == 0


def test_un_almacen_que_no_sabe_eliminar_responde_store_unavailable_sin_tocar_la_base(fabrica, subidas):
    class Viejo:
        def count_chunks(self, document_id):
            return 4

        def delete_document(self, document_id):
            raise NotImplementedError

    almacen = AlmacenFalso()
    _, documento = _documento(fabrica, subidas, almacen)

    with pytest.raises(StoreUnavailable):
        _eliminar(fabrica, subidas, Viejo(), documento)

    assert _existe(fabrica, documento)


def test_si_falla_el_commit_tras_borrar_los_fragmentos_el_documento_queda_sin_fragmentos_y_reintentar_lo_completa(
    fabrica, subidas, monkeypatch
):
    almacen = AlmacenFalso()
    _, documento = _documento(fabrica, subidas, almacen)

    with fabrica() as session:
        original = session.commit

        def commit_que_falla():
            raise RuntimeError("la base no responde")

        monkeypatch.setattr(session, "commit", commit_que_falla)
        with pytest.raises(RuntimeError):
            remove_document(session, almacen, session.get(Document, documento), subidas, 1)
        monkeypatch.setattr(session, "commit", original)
        session.rollback()

    assert almacen.count_chunks(documento) == 0
    assert _existe(fabrica, documento)
    assert (subidas / f"{documento}.txt").exists()

    _eliminar(fabrica, subidas, almacen, documento)

    assert not _existe(fabrica, documento)


def test_sin_archivo_original_la_eliminacion_no_falla(fabrica, subidas):
    almacen = AlmacenFalso()
    _, documento = _documento(fabrica, subidas, almacen, archivo=False)

    _eliminar(fabrica, subidas, almacen, documento)

    assert not _existe(fabrica, documento)


def test_si_no_se_puede_borrar_el_archivo_la_eliminacion_no_falla(fabrica, subidas, monkeypatch):
    almacen = AlmacenFalso()
    _, documento = _documento(fabrica, subidas, almacen)

    def sin_permiso(self, missing_ok=False):
        raise PermissionError("denegado")

    monkeypatch.setattr(removal.Path, "unlink", sin_permiso)

    _eliminar(fabrica, subidas, almacen, documento)

    assert not _existe(fabrica, documento)


def test_no_toca_otros_documentos_ni_uno_con_el_mismo_nombre_en_otro_dominio(fabrica, subidas):
    almacen = AlmacenFalso()
    dominio, elegido = _documento(fabrica, subidas, almacen, nombre="Mismo.txt")
    _, hermano = _documento(fabrica, subidas, almacen, dominio=dominio, nombre="Otro.txt", hash_="h2")
    _, homonimo = _documento(fabrica, subidas, almacen, nombre="Mismo.txt")

    _eliminar(fabrica, subidas, almacen, elegido)

    for conservado in (hermano, homonimo):
        assert _existe(fabrica, conservado)
        assert _imagenes(fabrica, conservado) == 1
        assert almacen.count_chunks(conservado) == 4
        assert (subidas / f"{conservado}.txt").exists()
