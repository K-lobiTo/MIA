import pytest

from mia.ingestion.loaders.base import DocumentLoader, LoaderError, get_loader


def test_los_cargadores_existentes_empiezan_sin_avisos():
    for tipo in ("pdf", "docx", "txt", "csv"):
        assert get_loader(tipo).notes == []


def test_el_factory_entrega_el_cargador_de_csv():
    from mia.ingestion.loaders.csv_loader import CsvLoader

    assert isinstance(get_loader("csv"), CsvLoader)


def test_dos_cargadores_no_comparten_la_lista_de_avisos():
    uno, otro = get_loader("txt"), get_loader("txt")
    uno.notes.append("aviso")
    assert otro.notes == []


def test_tipo_no_soportado_sigue_lanzando_value_error():
    with pytest.raises(ValueError, match="Tipo de fuente no soportado: xyz"):
        get_loader("xyz")


def test_loader_error_es_una_excepcion_con_mensaje():
    assert issubclass(LoaderError, Exception)
    assert str(LoaderError("mensaje")) == "mensaje"
    assert issubclass(get_loader("txt").__class__, DocumentLoader)
