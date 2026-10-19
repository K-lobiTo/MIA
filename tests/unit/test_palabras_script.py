"""scripts/palabras.py (feature 010) con un almacén simulado: estado, preparar y quitar."""

import importlib.util
from pathlib import Path
from unittest.mock import MagicMock

RAIZ_REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("palabras_script", RAIZ_REPO / "scripts" / "palabras.py")
script = importlib.util.module_from_spec(spec)
spec.loader.exec_module(script)

CON_INDICE = {
    "exists": True, "params": {"tokenizer": "prefix", "min_token_len": 3, "max_token_len": 15}, "indexed": 90,
    "points": 100,
}
SIN_INDICE = {"exists": False, "params": {}, "indexed": 0, "points": 100}


def _correr(capsys, almacen, *argv, respuesta="s"):
    entrada = MagicMock(return_value=respuesta)
    codigo = script.main(list(argv), almacen_y_destino=lambda: (almacen, "http://qdrant (colección c)"), entrada=entrada)
    salida = capsys.readouterr()
    return codigo, salida.out, salida.err, entrada


def test_estado_solo_lee_e_informa_indexados_frente_a_totales(capsys):
    almacen = MagicMock()
    almacen.text_index_status.return_value = CON_INDICE
    codigo, salida, _, entrada = _correr(capsys, almacen, "estado")
    assert codigo == 0 and "existe" in salida and "90 de 100" in salida and "prefix" in salida
    almacen.ensure_text_index.assert_not_called()
    almacen.drop_text_index.assert_not_called()
    entrada.assert_not_called()
    almacen.text_index_status.return_value = SIN_INDICE
    _, salida, _, _ = _correr(capsys, almacen, "estado")
    assert "no existe" in salida


def test_preparar_pide_confirmacion_y_sin_ella_no_hace_nada(capsys):
    almacen = MagicMock()
    almacen.text_index_status.return_value = SIN_INDICE
    codigo, salida, _, entrada = _correr(capsys, almacen, "preparar", respuesta="n")
    assert codigo == 0 and "No se hizo nada" in salida
    entrada.assert_called_once()
    almacen.ensure_text_index.assert_not_called()


def test_preparar_crea_el_indice_una_vez_y_muestra_el_estado(capsys):
    almacen = MagicMock()
    almacen.text_index_status.return_value = CON_INDICE
    codigo, salida, _, _ = _correr(capsys, almacen, "preparar")
    assert codigo == 0 and "http://qdrant (colección c)" in salida and "quedó creado" in salida
    almacen.ensure_text_index.assert_called_once()
    # Repetirlo es seguro (idempotente en el almacén) y --si salta la confirmación.
    _, _, _, entrada = _correr(capsys, almacen, "--si", "preparar")
    entrada.assert_not_called()
    assert almacen.ensure_text_index.call_count == 2


def test_quitar_pide_confirmacion_y_solo_quita_el_indice(capsys):
    almacen = MagicMock()
    almacen.text_index_status.return_value = SIN_INDICE
    codigo, salida, _, _ = _correr(capsys, almacen, "quitar")
    assert codigo == 0 and "no se tocaron" in salida
    almacen.drop_text_index.assert_called_once()
    almacen.upsert.assert_not_called()


def test_un_error_de_qdrant_da_un_mensaje_claro_y_codigo_distinto_de_cero(capsys):
    almacen = MagicMock()
    almacen.ensure_text_index.side_effect = RuntimeError("otros parámetros")
    codigo, _, error, _ = _correr(capsys, almacen, "--si", "preparar")
    assert codigo == 1 and "otros parámetros" in error


def test_un_archivo_de_entorno_ilegible_falla_con_mensaje(capsys, tmp_path):
    codigo = script.main(["--env-file", str(tmp_path / "no-existe.env"), "estado"])
    assert codigo == 1 and "No se pudo leer el archivo de entorno" in capsys.readouterr().err
