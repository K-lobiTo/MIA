"""Índice de texto contra un Qdrant real (feature 010). Se omite si no hay un Qdrant local en QDRANT_URL
(por defecto http://localhost:6333); usa una colección temporal que borra al terminar."""

import os
import uuid

import pytest
from qdrant_client import QdrantClient

from mia.storage.vector_store import Chunk, QdrantVectorStore

URL = os.environ.get("MIA_TEST_QDRANT_URL", "http://localhost:6333")


def _cliente():
    try:
        client = QdrantClient(url=URL, timeout=3)
        client.get_collections()
        return client
    except Exception:  # noqa: BLE001
        return None


@pytest.fixture
def almacen():
    client = _cliente()
    if client is None:
        pytest.skip(f"No hay un Qdrant local en {URL}")
    nombre = f"mia_prueba_{uuid.uuid4().hex[:8]}"
    store = QdrantVectorStore(url=URL, collection=nombre)
    store.ensure_collection(4)
    yield store
    client.delete_collection(nombre)


def _chunk(texto, dominio="d1", documento="doc", indice=0, vector=(1.0, 0.0, 0.0, 0.0)):
    return Chunk(
        id=str(uuid.uuid4()), document_id=documento, domain=dominio, text=texto, chunk_index=indice,
        embedding=list(vector),
    )


def test_el_indice_de_texto_busca_por_inicio_de_palabra_sin_tildes_ni_mayusculas(almacen):
    joseph = _chunk("Arquitectura web. Joseph Obando2023800202 Resumen", documento="joseph")
    kenneth = _chunk("con la ayuda de Kenneth Obando en las encuestas", documento="kenneth")
    lineas = _chunk("Líneas de TFG de la maestría", documento="lineas")
    otro = _chunk("Joseph Obando en otro dominio", dominio="d2", documento="otro")
    almacen.upsert([joseph, kenneth, lineas, otro])
    almacen.ensure_text_index()
    almacen.ensure_text_index()  # idempotente

    estado = almacen.text_index_status()
    assert estado["exists"] is True and estado["points"] == 4
    assert estado["params"]["tokenizer"] == "prefix"

    assert set(almacen.match_chunks(["d1"], "obando", 200)) == {(joseph.id, "joseph"), (kenneth.id, "kenneth")}
    assert almacen.match_chunks(["d1"], "joseph obando", 200) == [(joseph.id, "joseph")]
    assert almacen.match_chunks(["d1"], "sandi", 200) == []
    assert almacen.match_chunks(["d1"], "LÍNEAS", 200) == almacen.match_chunks(["d1"], "lineas", 200) == [
        (lineas.id, "lineas")
    ]
    # Un dominio distinto no se ve (FR-004).
    assert almacen.match_chunks(["d1"], "otro", 200) == []
    assert almacen.match_chunks(["d2"], "obando", 200) == [(otro.id, "otro")]
    # El límite se respeta.
    assert len(almacen.match_chunks(["d1"], "obando", 1)) == 1


def test_score_chunks_devuelve_el_coseno_de_los_ids_pedidos_y_respeta_el_dominio(almacen):
    cerca = _chunk("uno", vector=(1.0, 0.0, 0.0, 0.0))
    lejos = _chunk("dos", vector=(0.0, 1.0, 0.0, 0.0))
    ajeno = _chunk("tres", dominio="d2", vector=(1.0, 0.0, 0.0, 0.0))
    almacen.upsert([cerca, lejos, ajeno])
    resultados = almacen.score_chunks([1.0, 0.0, 0.0, 0.0], ["d1"], [cerca.id, lejos.id, ajeno.id])
    por_id = {r.chunk_id: r for r in resultados}
    assert set(por_id) == {cerca.id, lejos.id}
    assert por_id[cerca.id].score == pytest.approx(1.0) and por_id[lejos.id].score == pytest.approx(0.0)
    assert por_id[cerca.id].text == "uno"


def test_mover_un_documento_de_dominio_se_ve_en_el_filtro_sin_recrear_el_indice(almacen):
    pieza = _chunk("Joseph Obando2023800202", dominio="d1", documento="doc-mover")
    almacen.upsert([pieza])
    almacen.ensure_text_index()
    assert almacen.match_chunks(["d1"], "obando", 200) == [(pieza.id, "doc-mover")]
    almacen.set_domain("doc-mover", "d2")
    assert almacen.match_chunks(["d1"], "obando", 200) == []
    assert almacen.match_chunks(["d2"], "obando", 200) == [(pieza.id, "doc-mover")]


def test_quitar_el_indice_lo_deja_como_antes(almacen):
    almacen.upsert([_chunk("hola mundo")])
    almacen.ensure_text_index()
    almacen.drop_text_index()
    estado = almacen.text_index_status()
    assert estado["exists"] is False and estado["points"] == 1
