"""Cargador de documentos web (feature 022): lee el texto ya extraído que dejó la ruta en uploads/<id>.web."""

import pytest

from mia.ingestion.loaders.base import LoaderError, get_loader
from mia.ingestion.loaders.web_loader import WebLoader


def test_get_loader_devuelve_el_cargador_web():
    assert isinstance(get_loader("web"), WebLoader)


def test_devuelve_el_texto_tal_cual_y_sin_avisos(tmp_path):
    ruta = tmp_path / "doc.web"
    ruta.write_text("Fuente: https://e.test/ (consultada el 20 de noviembre de 2026)\nNombre\n\nÑandú\n", encoding="utf-8")
    cargador = WebLoader()

    texto = cargador.load(ruta)

    assert texto == "Fuente: https://e.test/ (consultada el 20 de noviembre de 2026)\nNombre\n\nÑandú\n"
    assert cargador.notes == []


@pytest.mark.parametrize("contenido", [b"", b"  \n\t ", b"\xff\xfe\x00bytes que no son utf-8 \xc3("])
def test_un_archivo_vacio_o_ilegible_es_un_error_claro(tmp_path, contenido):
    ruta = tmp_path / "doc.web"
    ruta.write_bytes(contenido)

    with pytest.raises(LoaderError, match="La página no tiene contenido para procesar."):
        WebLoader().load(ruta)


def test_un_tipo_desconocido_sigue_lanzando_value_error():
    with pytest.raises(ValueError):
        get_loader("tsv")
