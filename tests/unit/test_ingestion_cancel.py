"""Eliminar un documento mientras está en cola o procesándose (feature 012): no reaparece ni deja fragmentos, y la
ingesta de los demás sigue. Almacén de vectores y embeddings simulados."""

import threading
import uuid
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine, delete
from sqlalchemy.orm import sessionmaker

from mia.ingestion import pipeline
from mia.ingestion.removal import DocumentBusy, remove_document
from mia.storage.models import Base, Document, Domain
from tests.unit.almacen_falso import AlmacenFalso

TIMEOUT = 10


@pytest.fixture
def entorno(tmp_path, monkeypatch):
    engine = create_engine(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)
    fabrica = sessionmaker(bind=engine)
    subidas = tmp_path / "uploads"
    subidas.mkdir()
    monkeypatch.setattr(pipeline, "SessionLocal", fabrica)
    monkeypatch.setattr(pipeline, "UPLOAD_DIR", subidas)
    almacen = AlmacenFalso()
    embeddings = MagicMock()
    embeddings.embed.side_effect = lambda textos, is_query=False: [[0.1, 0.2]] * len(textos)
    monkeypatch.setattr(pipeline, "chunk_text", lambda texto: [f"fragmento {i}" for i in range(200)])
    with (
        patch.object(pipeline, "get_vector_store", return_value=almacen),
        patch.object(pipeline, "get_embedding_provider", return_value=embeddings),
    ):
        yield type("Entorno", (), {"fabrica": fabrica, "subidas": subidas, "almacen": almacen, "embeddings": embeddings})


def _documento(entorno, estado="pending", dominio=None):
    with entorno.fabrica() as session:
        if dominio is None:
            dominio = str(uuid.uuid4())
            session.add(Domain(id=dominio, name="Dominio", description=""))
            session.commit()
        documento = str(uuid.uuid4())
        session.add(
            Document(id=documento, domain_id=dominio, filename=f"{documento[:4]}.txt", source_type="txt", file_hash=documento, status=estado)
        )
        session.commit()
    (entorno.subidas / f"{documento}.txt").write_text("texto", encoding="utf-8")
    return documento


def _estado(entorno, documento):
    with entorno.fabrica() as session:
        d = session.get(Document, documento)
        return None if d is None else d.status


def _eliminar(entorno, documento, espera=TIMEOUT):
    with entorno.fabrica() as session:
        remove_document(session, entorno.almacen, session.get(Document, documento), entorno.subidas, espera)


def test_un_documento_en_cola_eliminado_nunca_se_procesa_ni_deja_fragmentos(entorno):
    documento = _documento(entorno, "pending")

    _eliminar(entorno, documento)
    pipeline.ingest_document(documento)  # la tarea de fondo corre después y no encuentra la fila

    assert _estado(entorno, documento) is None
    assert entorno.almacen.count_chunks(documento) == 0
    entorno.embeddings.embed.assert_not_called()


def test_la_ingesta_de_los_demas_documentos_en_cola_sigue_con_normalidad(entorno):
    eliminado, conservado = _documento(entorno), _documento(entorno)

    _eliminar(entorno, eliminado)
    pipeline.ingest_document(eliminado)
    pipeline.ingest_document(conservado)

    assert _estado(entorno, conservado) == "done"
    assert entorno.almacen.count_chunks(conservado) == 200
    assert entorno.almacen.count_chunks(eliminado) == 0


@pytest.mark.parametrize("estado", ["done", "error"])
def test_los_documentos_listos_o_con_error_se_eliminan_sin_esperar_al_cerrojo(entorno, estado):
    documento = _documento(entorno, estado)
    entorno.almacen.fragmentos[documento] = 5

    assert pipeline.acquire_ingest_lock(1)  # otra ingesta ocupa el cerrojo
    try:
        _eliminar(entorno, documento, espera=0.1)
    finally:
        pipeline.release_ingest_lock()

    assert _estado(entorno, documento) is None and entorno.almacen.count_chunks(documento) == 0


def test_un_documento_procesandose_se_elimina_cuando_la_ingesta_se_detiene_sin_dejar_fragmentos(entorno):
    documento = _documento(entorno, "pending")
    en_el_lote_2, seguir = threading.Event(), threading.Event()
    llamadas = []

    def embed(textos, is_query=False):
        llamadas.append(len(textos))
        if len(llamadas) == 2:
            en_el_lote_2.set()
            assert seguir.wait(TIMEOUT)
        return [[0.1, 0.2]] * len(textos)

    entorno.embeddings.embed.side_effect = embed
    errores = []

    def correr(funcion):
        try:
            funcion()
        except Exception as exc:  # noqa: BLE001
            errores.append(exc)

    ingesta = threading.Thread(target=correr, args=(lambda: pipeline.ingest_document(documento),))
    ingesta.start()
    assert en_el_lote_2.wait(TIMEOUT)
    assert entorno.almacen.count_chunks(documento) == 64  # el primer lote ya se escribió
    assert _estado(entorno, documento) == "processing"

    eliminacion = threading.Thread(target=correr, args=(lambda: _eliminar(entorno, documento),))
    eliminacion.start()
    # La ingesta sigue recién cuando la eliminación ya pidió la cancelación (queda esperando el cerrojo).
    for _ in range(TIMEOUT * 100):
        if pipeline.is_cancelled(documento):
            break
        threading.Event().wait(0.01)
    assert pipeline.is_cancelled(documento)
    seguir.set()
    ingesta.join(TIMEOUT)
    eliminacion.join(TIMEOUT)

    assert not ingesta.is_alive() and not eliminacion.is_alive() and errores == []
    assert _estado(entorno, documento) is None
    assert entorno.almacen.count_chunks(documento) == 0
    assert len(llamadas) == 2  # no siguió con los lotes restantes
    assert not (entorno.subidas / f"{documento}.txt").exists()
    assert not pipeline.is_cancelled(documento)


def test_si_la_fila_desaparece_antes_de_terminar_la_ingesta_limpia_sus_fragmentos_sin_fallar(entorno):
    documento = _documento(entorno, "pending")

    def embed(textos, is_query=False):
        if entorno.embeddings.embed.call_count == 4:  # el último lote: otra instancia elimina el documento
            with entorno.fabrica() as otra:
                otra.execute(delete(Document).where(Document.id == documento))
                otra.commit()
        return [[0.1, 0.2]] * len(textos)

    entorno.embeddings.embed.side_effect = embed

    pipeline.ingest_document(documento)  # no lanza StaleDataError

    assert _estado(entorno, documento) is None
    assert entorno.almacen.count_chunks(documento) == 0


def test_si_la_fila_desaparece_justo_antes_de_marcar_procesando_no_falla_ni_deja_fragmentos(entorno, monkeypatch):
    documento = _documento(entorno, "pending")
    original = pipeline.is_cancelled

    def borra_la_fila_y_consulta(document_id):
        with entorno.fabrica() as otra:
            otra.execute(delete(Document).where(Document.id == document_id))
            otra.commit()
        return original(document_id)

    monkeypatch.setattr(pipeline, "is_cancelled", borra_la_fila_y_consulta)

    pipeline.ingest_document(documento)

    assert _estado(entorno, documento) is None
    assert entorno.almacen.count_chunks(documento) == 0


def test_si_el_cerrojo_no_se_libera_a_tiempo_responde_ocupado_sin_tocar_nada(entorno):
    documento = _documento(entorno, "processing")
    entorno.almacen.fragmentos[documento] = 64

    assert pipeline.acquire_ingest_lock(1)  # la ingesta de ese documento no suelta el cerrojo
    try:
        with pytest.raises(DocumentBusy):
            _eliminar(entorno, documento, espera=0.2)
    finally:
        pipeline.release_ingest_lock()

    assert _estado(entorno, documento) == "processing"
    assert entorno.almacen.count_chunks(documento) == 64
    assert (entorno.subidas / f"{documento}.txt").exists()
    assert not pipeline.is_cancelled(documento)  # la marca se quita para no frenar una ingesta que siga


def test_un_documento_procesandose_cuyo_proceso_murio_se_elimina_enseguida(entorno):
    documento = _documento(entorno, "processing")  # quedó así por un corte; nadie tiene el cerrojo

    _eliminar(entorno, documento, espera=0.2)

    assert _estado(entorno, documento) is None


def test_si_falla_el_almacen_con_el_documento_procesandose_queda_en_error_visible_y_se_puede_reintentar(entorno):
    from mia.ingestion.removal import StoreUnavailable

    documento = _documento(entorno, "processing")
    entorno.almacen.fragmentos[documento] = 64
    entorno.almacen.falla_al_borrar = True

    with pytest.raises(StoreUnavailable):
        _eliminar(entorno, documento, espera=0.2)

    # La ingesta ya se detuvo: no se queda "Procesando" para siempre.
    assert _estado(entorno, documento) == "error"
    assert not pipeline.is_cancelled(documento)

    entorno.almacen.falla_al_borrar = False
    _eliminar(entorno, documento, espera=0.2)

    assert _estado(entorno, documento) is None and entorno.almacen.count_chunks(documento) == 0


@pytest.mark.parametrize("estado", ["done", "error", "pending"])
def test_si_falla_el_almacen_con_otro_estado_el_documento_conserva_su_estado(entorno, estado):
    from mia.ingestion.removal import StoreUnavailable

    documento = _documento(entorno, estado)
    entorno.almacen.fragmentos[documento] = 5
    entorno.almacen.falla_al_borrar = True

    with pytest.raises(StoreUnavailable):
        _eliminar(entorno, documento, espera=0.2)

    assert _estado(entorno, documento) == estado


def test_un_documento_en_cola_cuya_ingesta_lo_deja_procesando_justo_antes_de_fallar_el_almacen_queda_en_error(
    entorno, monkeypatch
):
    from sqlalchemy import update

    from mia.ingestion.removal import StoreUnavailable

    documento = _documento(entorno, "pending")
    entorno.almacen.fragmentos[documento] = 64
    entorno.almacen.falla_al_borrar = True
    pedir_cancelacion = pipeline.request_cancel

    def la_ingesta_arranca_y_se_detiene(document_id):
        # La eliminación ya leyó `pending`; justo ahora la ingesta (otra sesión) lo pasa a `processing` y, al ver la
        # cancelación, se detiene sin tocar el estado.
        pedir_cancelacion(document_id)
        with entorno.fabrica() as otra:
            otra.execute(update(Document).where(Document.id == document_id).values(status="processing"))
            otra.commit()

    monkeypatch.setattr(pipeline, "request_cancel", la_ingesta_arranca_y_se_detiene)

    with pytest.raises(StoreUnavailable):
        _eliminar(entorno, documento, espera=0.2)

    assert _estado(entorno, documento) == "error"
    assert not pipeline.is_cancelled(documento)

    entorno.almacen.falla_al_borrar = False
    monkeypatch.setattr(pipeline, "request_cancel", pedir_cancelacion)
    _eliminar(entorno, documento, espera=0.2)

    assert _estado(entorno, documento) is None
