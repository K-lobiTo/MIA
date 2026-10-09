import importlib.util
from pathlib import Path

import pytest

RAIZ_REPO = Path(__file__).resolve().parents[2]


def _cargar_script():
    spec = importlib.util.spec_from_file_location("servicios", RAIZ_REPO / "scripts" / "servicios.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


servicios = _cargar_script()


def nombres(lista):
    return [s.nombre for s in lista]


def test_sin_nombres_se_eligen_los_cuatro_con_la_api_primero():
    assert nombres(servicios.seleccionar([])) == ["MIA", "mia-computacion", "mia-administracion", "mia-panel"]


def test_al_apagar_se_invierte_el_orden_y_la_api_queda_al_final():
    assert nombres(servicios.seleccionar([], invertir=True))[-1] == "MIA"


def test_se_respeta_el_orden_de_los_servicios_y_no_el_de_la_linea_de_comandos():
    assert nombres(servicios.seleccionar(["mia-panel", "MIA"])) == ["MIA", "mia-panel"]


def test_los_nombres_no_distinguen_mayusculas():
    assert nombres(servicios.seleccionar(["mia", "MIA-PANEL"])) == ["MIA", "mia-panel"]


def test_un_nombre_repetido_no_duplica_el_servicio():
    assert nombres(servicios.seleccionar(["mia-panel", "mia-panel"])) == ["mia-panel"]


def test_un_nombre_desconocido_da_un_error_con_los_validos():
    with pytest.raises(ValueError) as error:
        servicios.seleccionar(["otro"])
    assert "otro" in str(error.value) and "mia-computacion" in str(error.value)


def test_cada_servicio_tiene_su_direccion_https_sin_barra_final():
    for servicio in servicios.SERVICIOS:
        assert servicio.url.startswith("https://") and not servicio.url.endswith("/")
