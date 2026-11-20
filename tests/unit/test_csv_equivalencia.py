"""La misma tabla guardada como CSV y como libro de Excel produce el mismo texto de filas (feature 021, SC-006): la única diferencia
es la marca de hoja de Excel (la línea `## Hoja: ...` y el prefijo `[Hoja] ` de cada fila), que el CSV no tiene."""

import re

from mia.ingestion.loaders.csv_loader import CsvLoader
from mia.ingestion.loaders.xlsx_loader import XlsxLoader
from tests.unit.csv_de_prueba import csv_bytes
from tests.unit.libros_de_prueba import hacer_libro

TABLA = [
    ["Código", "Nombre del curso", "Créditos", "Notas", "", "Profesor", "Nombre del curso"],
    ["MC4001", "Redes seguras", "4", "", "", "Persona 01", "Ñandú"],
    ["MC4002", "", "3", "con, coma", "x", "Persona 02", ""],
    ["MC4003", "Criptografía", "3", "85%", "", "", "Otro"],
    ["", "", "", "", "", "", ""],
    ["MC4004", "Datos", "15/03/2026", "007", "extra", "Persona 04", "Último"],
]


def _lineas_de_filas_de_excel(tmp_path) -> list[str]:
    ruta = hacer_libro(tmp_path / "tabla.xlsx", {"Hoja1": [[celda or None for celda in fila] for fila in TABLA]})
    lineas = XlsxLoader().load(ruta).splitlines()
    assert lineas[0] == "## Hoja: Hoja1"
    return [re.sub(r"^\[Hoja1\] ", "", linea) for linea in lineas[1:]]


def _lineas_de_filas_de_csv(tmp_path) -> list[str]:
    ruta = tmp_path / "tabla.csv"
    ruta.write_bytes(csv_bytes(TABLA, separador=";", codificacion="cp1252"))
    return CsvLoader().load(ruta).splitlines()


def test_las_filas_del_csv_y_del_excel_son_idénticas_salvo_la_marca_de_hoja(tmp_path):
    del_excel = _lineas_de_filas_de_excel(tmp_path)
    del_csv = _lineas_de_filas_de_csv(tmp_path)

    assert del_csv == del_excel
    assert del_csv[0] == "Código: MC4001 | Nombre del curso: Redes seguras | Créditos: 4 | Profesor: Persona 01 | Nombre del curso (G): Ñandú"
    assert len(del_csv) == 4


def test_las_mismas_preguntas_encuentran_las_mismas_filas(tmp_path):
    def pares(lineas):
        return [set(linea.split(" | ")) for linea in lineas]

    del_excel = pares(_lineas_de_filas_de_excel(tmp_path))
    del_csv = pares(_lineas_de_filas_de_csv(tmp_path))

    for pregunta in ("Créditos: 3", "Profesor: Persona 04", "Código: MC4002", "Notas: 85%"):
        assert [pregunta in fila for fila in del_csv] == [pregunta in fila for fila in del_excel]
