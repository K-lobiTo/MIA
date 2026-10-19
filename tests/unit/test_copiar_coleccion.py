"""scripts/copiar_coleccion.py (feature 010) con clientes de Qdrant simulados."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

RAIZ_REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("copiar_script", RAIZ_REPO / "scripts" / "copiar_coleccion.py")
script = importlib.util.module_from_spec(spec)
spec.loader.exec_module(script)


def _punto(i):
    return SimpleNamespace(id=f"p{i}", vector=[float(i), 0.5], payload={"domain": "d", "text": f"t{i}"})


class _Origen:
    """Un cliente de Qdrant de solo lectura simulado, con 5 puntos que se entregan de a 2."""

    def __init__(self):
        self.puntos = [_punto(i) for i in range(5)]
        self.llamadas = []

    def get_collection(self, nombre):
        return SimpleNamespace(
            points_count=5, config=SimpleNamespace(params=SimpleNamespace(vectors=SimpleNamespace(size=2, distance="Cosine")))
        )

    def scroll(self, collection_name, limit, offset, with_payload, with_vectors):
        self.llamadas.append(("scroll", offset))
        assert with_payload and with_vectors
        inicio = offset or 0
        siguiente = inicio + 2
        return self.puntos[inicio:siguiente], (siguiente if siguiente < len(self.puntos) else None)

    def upsert(self, **kwargs):
        raise AssertionError("el origen no se escribe")

    def delete_collection(self, *args, **kwargs):
        raise AssertionError("el origen no se escribe")


def _destino(existe=False):
    destino = MagicMock()
    destino.collection_exists.return_value = existe
    destino.count.return_value = SimpleNamespace(count=5)
    return destino


def test_copia_todos_los_puntos_con_sus_vectores_y_crea_la_coleccion_y_los_indices():
    origen, destino = _Origen(), _destino()
    mostrado = []
    resultado = script.copiar(origen, destino, "mia_chunks", "mia_hibrida", mostrar=mostrado.append)
    assert resultado == {"origen": 5, "copiados": 5, "destino": 5}
    puntos = [p for llamada in destino.upsert.call_args_list for p in llamada.kwargs["points"]]
    assert [p.id for p in puntos] == [f"p{i}" for i in range(5)]
    assert puntos[3].vector == [3.0, 0.5] and puntos[3].payload == {"domain": "d", "text": "t3"}
    destino.create_collection.assert_called_once()
    campos = {c.kwargs["field_name"] for c in destino.create_payload_index.call_args_list}
    assert campos == {"domain", "document_id", "chunk_index"}


def test_con_indice_crea_tambien_el_indice_de_texto_en_el_destino():
    destino = _destino(existe=True)
    script.copiar(_Origen(), destino, "mia_chunks", "mia_hibrida", indice=True, mostrar=lambda *_: None)
    destino.create_collection.assert_not_called()
    campos = [c.kwargs["field_name"] for c in destino.create_payload_index.call_args_list]
    assert "text" in campos


def test_el_origen_rechaza_cualquier_escritura():
    origen = script.SoloLectura(_Origen())
    with pytest.raises(PermissionError):
        origen.upsert(collection_name="x", points=[])
    with pytest.raises(PermissionError):
        origen.delete_collection("x")
    assert origen.get_collection("x").points_count == 5


def test_repetir_la_copia_es_idempotente_porque_conserva_los_ids():
    destino = _destino(existe=True)
    for _ in range(2):
        script.copiar(_Origen(), destino, "mia_chunks", "mia_hibrida", mostrar=lambda *_: None)
    ids = [p.id for llamada in destino.upsert.call_args_list for p in llamada.kwargs["points"]]
    assert ids[:5] == ids[5:]


def test_se_niega_si_el_destino_es_el_mismo_que_el_origen(tmp_path, capsys):
    entorno = tmp_path / "origen.env"
    entorno.write_text("QDRANT_URL=http://localhost:6333\nQDRANT_COLLECTION=mia_chunks\n", encoding="utf-8")
    codigo = script.main(
        ["--origen-env", str(entorno), "--destino-url", "http://localhost:6333/", "--destino-coleccion", "mia_chunks"],
        clientes=(_Origen(), _destino()),
    )
    assert codigo == 1 and "mismo Qdrant" in capsys.readouterr().err


def test_main_copia_y_avisa_si_falta_el_origen_o_el_archivo(tmp_path, capsys):
    entorno = tmp_path / "origen.env"
    entorno.write_text("QDRANT_URL=https://origen.example\nQDRANT_COLLECTION=mia_chunks\n", encoding="utf-8")
    destino = _destino()
    codigo = script.main(
        ["--origen-env", str(entorno), "--destino-coleccion", "copia"], clientes=(_Origen(), destino)
    )
    salida = capsys.readouterr().out
    assert codigo == 0 and "5 puntos copiados" in salida and "solo lectura" in salida
    assert script.main(["--origen-env", str(tmp_path / "no.env"), "--destino-coleccion", "c"]) == 1
    vacio = tmp_path / "vacio.env"
    vacio.write_text("OTRA=1\n", encoding="utf-8")
    assert script.main(["--origen-env", str(vacio), "--destino-coleccion", "c"]) == 1
    assert "no define QDRANT_URL" in capsys.readouterr().err
