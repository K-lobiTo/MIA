"""Imágenes de los documentos de las fuentes en la respuesta de la consulta (feature 011, contracts/imagenes-api.md)."""

import logging
import re
import uuid
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import event

from mia.api.routes import query as query_routes
from mia.config import settings
from mia.rag.llm import LLMAnswer
from mia.storage.models import Bot, Document, DocumentImage, Domain, Unit
from mia.storage.vector_store import SearchResult
from tests.unit.imagenes_de_prueba import PNG

SERVICIO = "clave-del-servicio-de-prueba"


@pytest.fixture
def base(db, modes_config):
    with db() as session:
        session.add(Unit(id="u1", name="Computación"))
        session.flush()
        session.add(Domain(id="dom-1", unit_id="u1", name="Admisión", description=""))
        session.flush()
        for numero in (1, 2, 3):
            session.add(
                Document(
                    id=f"doc-{numero}", domain_id="dom-1", filename=f"documento-{numero}.pdf", source_type="pdf",
                    file_hash=f"h{numero}", status="done",
                )
            )
        session.flush()
        session.add_all([
            DocumentImage(
                id="img-1a", document_id="doc-1", public_id="1a" * 16, content_type="image/png", content=PNG,
                size_bytes=len(PNG), caption="Horario de matrícula", position=0, created_by="automatizacion",
            ),
            DocumentImage(
                id="img-1b", document_id="doc-1", public_id="1b" * 16, content_type="image/png", content=PNG,
                size_bytes=len(PNG), caption="Detalle", position=1, created_by="automatizacion",
            ),
            DocumentImage(
                id="img-2a", document_id="doc-2", public_id="2a" * 16, content_type="image/png", content=PNG,
                size_bytes=len(PNG), caption="", position=0, created_by="automatizacion",
            ),
        ])
        session.commit()


def pasajes(*documentos):
    return [
        SearchResult(chunk_id=f"c{i}", document_id=f"doc-{n}", domain="dom-1", text=f"Texto del documento {n}.", score=0.9 - i / 100)
        for i, n in enumerate(documentos)
    ]


def consultar(client, artefacto, texto_del_modelo, resultados, cited="on"):
    almacen = MagicMock()
    almacen.count_chunks.return_value = 100  # documentos largos: no se pasan completos
    almacen.search.return_value = resultados
    almacen.get_chunks.return_value = []
    embeddings = MagicMock()
    embeddings.embed.return_value = [[0.1, 0.2]]
    modelo = MagicMock()
    modelo.answer.return_value = LLMAnswer(text=texto_del_modelo)
    with (
        patch.object(settings, "query_cited_sources", cited),
        patch.object(settings, "query_context_neighbors", 0),
        patch.object(query_routes, "get_vector_store", return_value=almacen),
        patch.object(query_routes, "get_embedding_provider", return_value=embeddings),
        patch.object(query_routes, "get_llm_provider", return_value=modelo),
    ):
        return client.post(
            "/query", json={"domains": ["dom-1"], "question": "¿Cuándo es la matrícula?"}, headers=artefacto.headers
        )


def imagen(public, caption, documento):
    return {"url": f"/media/{public}", "caption": caption, "document": documento}


IMG_1A = imagen("1a" * 16, "Horario de matrícula", "documento-1.pdf")
IMG_1B = imagen("1b" * 16, "Detalle", "documento-1.pdf")
IMG_2A = imagen("2a" * 16, "", "documento-2.pdf")


# --- Qué imágenes se devuelven ---------------------------------------------------------------------------------


def test_una_fuente_con_imagenes_las_devuelve_con_url_relativa_descripcion_y_nombre_del_documento(client, base, make_artifact):
    artefacto = make_artifact(units=["u1"])

    respuesta = consultar(client, artefacto, "Es el 3 de agosto.\nFUENTES: 1", pasajes(1))

    assert respuesta.status_code == 200
    assert respuesta.json()["images"] == [IMG_1A, IMG_1B]


def test_las_imagenes_siguen_el_orden_de_las_fuentes_y_cada_documento_va_una_vez(client, base, make_artifact):
    artefacto = make_artifact(units=["u1"])

    # Dos fragmentos del documento 1 y uno del 2: el documento 1 aporta sus imágenes una sola vez, antes que el 2.
    respuesta = consultar(client, artefacto, "Respuesta.\nFUENTES: 1, 2, 3", pasajes(1, 1, 2))

    assert respuesta.json()["images"] == [IMG_1A, IMG_1B, IMG_2A]


def test_si_el_documento_2_va_primero_sus_imagenes_van_primero(client, base, make_artifact):
    artefacto = make_artifact(units=["u1"])

    respuesta = consultar(client, artefacto, "Respuesta.\nFUENTES: 1, 2", pasajes(2, 1))

    assert respuesta.json()["images"] == [IMG_2A, IMG_1A, IMG_1B]


def test_con_citas_solo_salen_las_imagenes_de_los_documentos_que_el_modelo_cito(client, base, make_artifact):
    artefacto = make_artifact(units=["u1"])

    # El modelo recibió los documentos 1, 2 y 3 pero solo citó el 2: las imágenes del 1 no aportaron.
    respuesta = consultar(client, artefacto, "Respuesta.\nFUENTES: 2", pasajes(1, 2, 3))

    assert respuesta.json()["images"] == [IMG_2A]
    assert [s["document"] for s in respuesta.json()["sources"]] == ["documento-2.pdf"]


def test_un_documento_citado_sin_imagenes_no_aporta(client, base, make_artifact):
    artefacto = make_artifact(units=["u1"])

    respuesta = consultar(client, artefacto, "Respuesta.\nFUENTES: 3", pasajes(1, 2, 3))

    assert respuesta.status_code == 200 and respuesta.json()["images"] == []


def test_con_las_citas_apagadas_salen_las_de_todos_los_documentos_entregados(client, base, make_artifact):
    artefacto = make_artifact(units=["u1"])

    respuesta = consultar(client, artefacto, "Respuesta.", pasajes(1, 2, 3), cited="off")

    assert respuesta.json()["images"] == [IMG_1A, IMG_1B, IMG_2A]


def test_una_respuesta_sin_informacion_no_devuelve_imagenes(client, base, make_artifact):
    artefacto = make_artifact(units=["u1"])

    respuesta = consultar(client, artefacto, "SIN_INFORMACION", pasajes(1, 2))

    cuerpo = respuesta.json()
    assert cuerpo["no_info"] is True and cuerpo["images"] == []


def test_sin_fragmentos_relevantes_no_hay_imagenes(client, base, make_artifact):
    artefacto = make_artifact(units=["u1"])

    respuesta = consultar(client, artefacto, "No se llama", [])

    assert respuesta.json()["no_info"] is True and respuesta.json()["images"] == []


def test_sin_imagenes_asociadas_la_lista_va_vacia_y_el_resto_de_la_respuesta_es_igual(client, base, make_artifact):
    artefacto = make_artifact(units=["u1"])

    respuesta = consultar(client, artefacto, "Respuesta.\nFUENTES: 3", pasajes(3))

    cuerpo = respuesta.json()
    assert cuerpo["images"] == [] and cuerpo["answer"] == "Respuesta." and cuerpo["no_info"] is False
    assert set(cuerpo) == {"id", "answer", "sources", "mode", "latency_ms", "no_info", "images"}


# --- Robustez y costo ------------------------------------------------------------------------------------------


def test_si_falla_la_consulta_de_imagenes_la_respuesta_se_entrega_sin_ellas_y_con_un_aviso(client, base, make_artifact, caplog):
    artefacto = make_artifact(units=["u1"])

    with (
        patch.object(query_routes, "images_for_documents", side_effect=RuntimeError("base caída")),
        caplog.at_level(logging.WARNING, logger="mia.api.routes.query"),
    ):
        respuesta = consultar(client, artefacto, "Respuesta.\nFUENTES: 1", pasajes(1))

    assert respuesta.status_code == 200
    assert respuesta.json()["images"] == [] and respuesta.json()["answer"] == "Respuesta."
    assert any("imágenes" in r.getMessage() for r in caplog.records)


def test_se_buscan_las_imagenes_con_una_sola_consulta_y_sin_leer_los_binarios(client, db, base, make_artifact):
    artefacto = make_artifact(units=["u1"])
    sentencias = []
    engine = db.kw["bind"]

    def espiar(conn, cursor, statement, parameters, context, executemany):
        sentencias.append(statement)

    event.listen(engine, "before_cursor_execute", espiar)
    try:
        consultar(client, artefacto, "Respuesta.\nFUENTES: 1, 2", pasajes(1, 2))
    finally:
        event.remove(engine, "before_cursor_execute", espiar)

    consultas = [s for s in sentencias if "document_images" in s]
    assert len(consultas) == 1
    assert not re.search(r"document_images\.content(?!_)", consultas[0])


def test_la_consulta_de_imagenes_no_cuenta_en_el_registro_de_uso(client, db, base, make_artifact):
    from mia.storage.models import QueryLog

    artefacto = make_artifact(units=["u1"])
    consultar(client, artefacto, "Respuesta.\nFUENTES: 1", pasajes(1))
    with db() as session:
        registros = session.query(QueryLog).all()
    assert len(registros) == 1 and registros[0].outcome == "answered"


# --- También en la consulta del bot ----------------------------------------------------------------------------


def test_la_consulta_del_bot_devuelve_las_mismas_imagenes(client, db, base, make_artifact, monkeypatch):
    monkeypatch.setattr(settings, "bot_service_key", SERVICIO)
    artefacto = make_artifact("Bot", units=["u1"])
    with db() as session:
        session.add(Bot(id=str(uuid.uuid4()), name="Bot de pruebas", kapso_number_id="111", artifact_id=artefacto.id))
        session.commit()
    almacen = MagicMock()
    almacen.count_chunks.return_value = 100
    almacen.search.return_value = pasajes(1, 2)
    almacen.get_chunks.return_value = []
    embeddings = MagicMock()
    embeddings.embed.return_value = [[0.1, 0.2]]
    modelo = MagicMock()
    modelo.answer.return_value = LLMAnswer(text="Respuesta.\nFUENTES: 1, 2")
    with (
        patch.object(settings, "query_cited_sources", "on"),
        patch.object(query_routes, "get_vector_store", return_value=almacen),
        patch.object(query_routes, "get_embedding_provider", return_value=embeddings),
        patch.object(query_routes, "get_llm_provider", return_value=modelo),
    ):
        respuesta = client.post(
            "/bot/query",
            json={"number_id": "111", "question": "¿Cuándo es la matrícula?"},
            headers={"X-Bot-Service-Key": SERVICIO},
        )

    assert respuesta.status_code == 200
    assert respuesta.json()["images"] == [IMG_1A, IMG_1B, IMG_2A]
