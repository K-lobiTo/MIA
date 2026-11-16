import uuid
from unittest.mock import MagicMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from mia.ingestion import pipeline
from mia.storage.models import Base, Document, Domain


def _make_session_factory(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def _make_pending_document(session_factory, upload_dir, content: str, source_type: str = "txt") -> str:
    with session_factory() as session:
        domain = Domain(id=str(uuid.uuid4()), name="Memoria del Consejo", description="")
        session.add(domain)
        session.commit()

        document_id = str(uuid.uuid4())
        (upload_dir / f"{document_id}.{source_type}").write_text(content, encoding="utf-8")

        document = Document(
            id=document_id,
            domain_id=domain.id,
            filename=f"{document_id}.{source_type}",
            source_type=source_type,
            file_hash="hash",
            status="pending",
        )
        session.add(document)
        session.commit()
        return document_id


def test_ingest_document_exito(tmp_path, monkeypatch):
    session_factory = _make_session_factory(tmp_path)
    monkeypatch.setattr(pipeline, "SessionLocal", session_factory)
    monkeypatch.setattr(pipeline, "UPLOAD_DIR", tmp_path)

    document_id = _make_pending_document(
        session_factory, tmp_path, "Contenido de prueba con texto suficiente para trocear."
    )

    fake_embedding_provider = MagicMock()
    fake_embedding_provider.embed.return_value = [[0.1, 0.2, 0.3]]
    fake_vector_store = MagicMock()

    with (
        patch.object(pipeline, "get_embedding_provider", return_value=fake_embedding_provider),
        patch.object(pipeline, "get_vector_store", return_value=fake_vector_store),
    ):
        pipeline.ingest_document(document_id)

    with session_factory() as session:
        document = session.get(Document, document_id)
        assert document.status == "done"

    fake_vector_store.upsert.assert_called_once()
    chunks = fake_vector_store.upsert.call_args.args[0]
    assert len(chunks) == 1
    assert chunks[0].document_id == document_id


def test_ingest_document_sin_texto_extraible(tmp_path, monkeypatch):
    session_factory = _make_session_factory(tmp_path)
    monkeypatch.setattr(pipeline, "SessionLocal", session_factory)
    monkeypatch.setattr(pipeline, "UPLOAD_DIR", tmp_path)

    document_id = _make_pending_document(session_factory, tmp_path, "   ")

    with (
        patch.object(pipeline, "get_embedding_provider"),
        patch.object(pipeline, "get_vector_store"),
    ):
        pipeline.ingest_document(document_id)

    with session_factory() as session:
        document = session.get(Document, document_id)
        assert document.status == "error"


def test_reingerir_un_documento_crea_fragmentos_nuevos_y_solo_usa_el_upsert(tmp_path, monkeypatch):
    """Feature 010 (FR-010): el índice de texto de Qdrant se actualiza con el `upsert` normal, así que la ingesta no
    llama a ningún método de la búsqueda por palabras. Reingerir crea fragmentos nuevos (otros ids) sin borrar los
    anteriores: es el comportamiento previo de la ingesta y el documento puede aparecer duplicado hasta limpiar la colección."""
    session_factory = _make_session_factory(tmp_path)
    monkeypatch.setattr(pipeline, "SessionLocal", session_factory)
    monkeypatch.setattr(pipeline, "UPLOAD_DIR", tmp_path)
    document_id = _make_pending_document(session_factory, tmp_path, "Joseph Obando2023800202 escribe un resumen.")
    embeddings = MagicMock()
    embeddings.embed.return_value = [[0.1, 0.2, 0.3]]
    store = MagicMock()

    with (
        patch.object(pipeline, "get_embedding_provider", return_value=embeddings),
        patch.object(pipeline, "get_vector_store", return_value=store),
    ):
        pipeline.ingest_document(document_id)
        with session_factory() as session:
            session.get(Document, document_id).status = "pending"
            session.commit()
        pipeline.ingest_document(document_id)

    primero, segundo = (call.args[0][0] for call in store.upsert.call_args_list)
    assert primero.text == segundo.text and primero.id != segundo.id
    llamados = {call[0] for call in store.method_calls}
    assert llamados == {"upsert"}
    store.delete.assert_not_called()


class _CargadorFalso:
    def __init__(self, texto="Texto de prueba.", error=None, notes=None):
        self._texto, self._error = texto, error
        self.notes = list(notes or [])

    def load(self, path):
        if self._error:
            raise self._error
        return self._texto


def _ingerir_con_cargador(tmp_path, monkeypatch, cargador):
    session_factory = _make_session_factory(tmp_path)
    monkeypatch.setattr(pipeline, "SessionLocal", session_factory)
    monkeypatch.setattr(pipeline, "UPLOAD_DIR", tmp_path)
    monkeypatch.setattr(pipeline, "get_loader", lambda tipo: cargador)
    document_id = _make_pending_document(session_factory, tmp_path, "x")
    provider = MagicMock()
    provider.embed.return_value = [[0.1, 0.2, 0.3]]
    with (
        patch.object(pipeline, "get_embedding_provider", return_value=provider),
        patch.object(pipeline, "get_vector_store", return_value=MagicMock()),
    ):
        pipeline.ingest_document(document_id)
    return session_factory, document_id


def test_un_loader_error_deja_el_documento_en_error_con_su_mensaje(tmp_path, monkeypatch):
    from mia.ingestion.loaders.base import LoaderError

    factory, document_id = _ingerir_con_cargador(tmp_path, monkeypatch, _CargadorFalso(error=LoaderError("mensaje")))
    with factory() as session:
        document = session.get(Document, document_id)
        assert (document.status, document.status_note) == ("error", "mensaje")


def test_los_avisos_del_cargador_quedan_como_nota_de_un_documento_listo(tmp_path, monkeypatch):
    factory, document_id = _ingerir_con_cargador(tmp_path, monkeypatch, _CargadorFalso(notes=["aviso", "otro"]))
    with factory() as session:
        document = session.get(Document, document_id)
        assert (document.status, document.status_note) == ("done", "aviso otro")


def test_un_documento_sin_avisos_queda_sin_nota(tmp_path, monkeypatch):
    factory, document_id = _ingerir_con_cargador(tmp_path, monkeypatch, _CargadorFalso())
    with factory() as session:
        assert session.get(Document, document_id).status_note is None


def test_reprocesar_limpia_la_nota_anterior(tmp_path, monkeypatch):
    session_factory = _make_session_factory(tmp_path)
    monkeypatch.setattr(pipeline, "SessionLocal", session_factory)
    monkeypatch.setattr(pipeline, "UPLOAD_DIR", tmp_path)
    monkeypatch.setattr(pipeline, "get_loader", lambda tipo: _CargadorFalso())
    document_id = _make_pending_document(session_factory, tmp_path, "x")
    with session_factory() as session:
        session.get(Document, document_id).status_note = "nota vieja"
        session.commit()
    provider = MagicMock()
    provider.embed.return_value = [[0.1, 0.2, 0.3]]
    with (
        patch.object(pipeline, "get_embedding_provider", return_value=provider),
        patch.object(pipeline, "get_vector_store", return_value=MagicMock()),
    ):
        pipeline.ingest_document(document_id)
    with session_factory() as session:
        assert session.get(Document, document_id).status_note is None


def test_la_nota_se_recorta_a_500_caracteres(tmp_path, monkeypatch):
    factory, document_id = _ingerir_con_cargador(tmp_path, monkeypatch, _CargadorFalso(notes=["a" * 600]))
    with factory() as session:
        assert len(session.get(Document, document_id).status_note) == 500
