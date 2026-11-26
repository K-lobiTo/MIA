"""Lectura de mantenimiento de Qdrant (src/mia/storage/keepalive.py)."""

import asyncio

import pytest
from pydantic import ValidationError
from qdrant_client import QdrantClient

from mia.config import Settings
from mia.storage.keepalive import keep_active
from mia.storage.vector_store import QdrantVectorStore


def test_la_lectura_funciona_sobre_una_coleccion_vacia_y_no_escribe_nada():
    store = QdrantVectorStore.__new__(QdrantVectorStore)
    store.collection = "prueba"
    store.client = QdrantClient(":memory:")
    store.ensure_collection(4)
    store.ping(4)
    assert store.client.count("prueba").count == 0


def _correr_hasta(ping, llamadas, objetivo: int) -> None:
    async def principal():
        tarea = asyncio.create_task(keep_active(ping, interval_seconds=0.01, retry_seconds=0.01))
        async with asyncio.timeout(5):
            while len(llamadas) < objetivo:
                await asyncio.sleep(0.005)
        tarea.cancel()
        with pytest.raises(asyncio.CancelledError):
            await tarea

    asyncio.run(principal())


def test_se_repite_en_cada_intervalo():
    llamadas = []
    _correr_hasta(lambda: llamadas.append(1), llamadas, 3)


def test_un_fallo_no_detiene_las_lecturas(caplog):
    llamadas = []

    def ping():
        llamadas.append(1)
        if len(llamadas) == 1:
            raise ConnectionError("sin red")

    _correr_hasta(ping, llamadas, 2)
    assert "Lectura de mantenimiento de Qdrant fallida" in caplog.text


def test_un_almacen_que_no_la_implementa_termina_la_tarea():
    def ping():
        raise NotImplementedError

    asyncio.run(asyncio.wait_for(keep_active(ping, interval_seconds=60), timeout=5))


def test_el_intervalo_no_puede_superar_los_seis_dias():
    assert Settings(_env_file=None).qdrant_keepalive_hours == 24
    assert Settings(_env_file=None, qdrant_keepalive_hours=0).qdrant_keepalive_hours == 0
    with pytest.raises(ValidationError):
        Settings(_env_file=None, qdrant_keepalive_hours=168)
