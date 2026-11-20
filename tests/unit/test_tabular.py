"""La lógica de filas compartida por los cargadores de Excel y de CSV (feature 021, research R1) y la prueba "dorada" que fija el
texto exacto de un libro de Excel para detectar cualquier cambio de resultado al extraerla."""

import datetime

import pytest
from openpyxl import Workbook

from mia.ingestion.loaders.tabular import MAX_COLUMNAS, MAX_FILAS_VACIAS_SEGUIDAS, lineas_de_tabla
from mia.ingestion.loaders.xlsx_loader import XlsxLoader


def _filas(*filas):
    """`(número, textos)` con la numeración que daría una hoja: desde 1, una por fila."""
    return [(i, list(f)) for i, f in enumerate(filas, start=1)]


def _leer(filas, *, prefijo="", objeto="el archivo", escritas=0, limite=1000):
    return lineas_de_tabla(prefijo, objeto, filas, escritas, limite)


def test_cada_fila_es_una_linea_con_sus_encabezados_y_el_prefijo():
    lineas, escritas, corte, avisos = _leer(
        _filas(["Código", "Nombre"], ["MC1", "Redes"], ["MC2", "Datos"]), prefijo="[H] "
    )

    assert lineas == ["[H] Código: MC1 | Nombre: Redes", "[H] Código: MC2 | Nombre: Datos"]
    assert (escritas, corte, avisos) == (2, None, [])


def test_el_encabezado_es_la_primera_fila_con_dos_celdas_y_las_anteriores_van_como_texto_simple():
    lineas, escritas, _, _ = _leer(_filas(["Título del documento"], ["Nota", "otra"], ["Código", "Nombre"], ["MC1", "Redes"]))

    # "Nota | otra" ya tiene dos celdas con contenido: es la fila de encabezados.
    assert lineas == ["Título del documento", "Nota: Código | otra: Nombre", "Nota: MC1 | otra: Redes"]
    assert escritas == 3


def test_el_encabezado_no_cuenta_para_el_tope_ni_se_escribe():
    lineas, escritas, corte, _ = _leer(_filas(["a", "b"], ["1", "2"], ["3", "4"], ["5", "6"]), limite=2)

    assert lineas == ["a: 1 | b: 2", "a: 3 | b: 4"]
    assert (escritas, corte) == (2, 4)  # se corta en la fila 4, la primera que ya no cabe


def test_con_exactamente_el_tope_de_filas_no_hay_corte():
    lineas, escritas, corte, _ = _leer(_filas(["a", "b"], ["1", "2"], ["3", "4"]), limite=2)

    assert len(lineas) == 2 and escritas == 2 and corte is None


def test_columnas_vacias_se_nombran_por_su_letra_y_los_encabezados_repetidos_llevan_la_letra():
    lineas, _, _, _ = _leer(_filas(["Nombre", None, "Nombre", "Edad"], ["Ana", "x", "Beto", "5"]))

    assert lineas == ["Nombre: Ana | Columna B: x | Nombre (C): Beto | Edad: 5"]


def test_una_fila_mas_ancha_que_el_encabezado_nombra_sus_celdas_de_mas_sin_desplazar_nada():
    lineas, _, _, _ = _leer(_filas(["a", "b"], ["1", "2", "3", "4"]))

    assert lineas == ["a: 1 | b: 2 | Columna C: 3 | Columna D: 4"]


def test_una_fila_mas_corta_omite_las_celdas_que_faltan():
    lineas, _, _, _ = _leer(_filas(["a", "b", "c"], ["1"], [None, "2"]))

    assert lineas == ["a: 1", "b: 2"]


def test_las_filas_vacias_y_las_de_solo_celdas_vacias_no_generan_texto():
    lineas, escritas, _, _ = _leer(_filas(["a", "b"], [None, None], [], ["1", "2"], [None]))

    assert lineas == ["a: 1 | b: 2"] and escritas == 1


def test_sin_dos_celdas_con_contenido_no_hay_encabezado_y_cada_fila_es_texto_simple():
    lineas, _, _, _ = _leer(_filas(["Redes"], ["Datos"]), prefijo="[H] ")

    assert lineas == ["[H] Redes", "[H] Datos"]


def test_mas_de_200_columnas_con_contenido_se_cortan_y_se_avisa_con_el_objeto():
    fila = ["c" + str(i) for i in range(MAX_COLUMNAS + 1)]  # la columna 201 trae contenido
    datos = [str(i) for i in range(MAX_COLUMNAS + 1)]

    lineas, _, _, avisos = _leer(_filas(fila, datos), objeto='la hoja "H"')

    assert avisos == [f'en la hoja "H" se leyeron solo las primeras {MAX_COLUMNAS} columnas']
    assert lineas[0].count(" | ") == MAX_COLUMNAS - 1  # 200 columnas, 199 separadores
    assert "c200" not in lineas[0]


def test_exactamente_200_columnas_no_avisa():
    fila = ["c" + str(i) for i in range(MAX_COLUMNAS)]

    _, _, _, avisos = _leer(_filas(fila, [str(i) for i in range(MAX_COLUMNAS)]))

    assert avisos == []


def test_tras_las_filas_vacias_seguidas_deja_de_leer_y_avisa_siempre():
    filas = [(1, ["a", "b"]), (2, ["1", "2"])]
    filas += [(i, [None, None]) for i in range(3, 3 + MAX_FILAS_VACIAS_SEGUIDAS)]
    filas += [(3 + MAX_FILAS_VACIAS_SEGUIDAS, ["9", "9"])]

    lineas, _, _, avisos = _leer(filas, objeto="el archivo")

    assert lineas == ["a: 1 | b: 2"]  # lo que está después no se lee
    assert avisos == [
        (
            f"se dejó de leer el archivo en la fila {2 + MAX_FILAS_VACIAS_SEGUIDAS} tras {MAX_FILAS_VACIAS_SEGUIDAS} filas "
            "vacías seguidas; si había datos después, no se ingestaron"
        )
    ]


def test_menos_filas_vacias_que_el_limite_no_cortan():
    filas = [(1, ["a", "b"])] + [(i, [None]) for i in range(2, MAX_FILAS_VACIAS_SEGUIDAS)] + [(MAX_FILAS_VACIAS_SEGUIDAS, ["1", "2"])]

    lineas, _, _, avisos = _leer(filas)

    assert lineas == ["a: 1 | b: 2"] and avisos == []


def test_un_generador_de_filas_tambien_sirve_y_se_lee_una_sola_vez():
    consumidas = []

    def filas():
        for fila in _filas(["a", "b"], ["1", "2"]):
            consumidas.append(fila[0])
            yield fila

    lineas, _, _, _ = _leer(filas())

    assert lineas == ["a: 1 | b: 2"] and consumidas == [1, 2]


# --- La prueba dorada: el texto exacto de un libro de Excel no cambia al extraer la lógica compartida (SC-008) ---


def _libro_variado(ruta):
    libro = Workbook()
    libro.remove(libro.active)
    cursos = libro.create_sheet("Cursos")
    cursos.append(["Plan de estudios 2026"])
    cursos.append(["Elaborado por la coordinación"])
    cursos.append(["Código", "Nombre", None, "Nombre", "Aprobado"])
    cursos.append(["MC4001", "Redes seguras", "extra", "Duplicado", 0.85])
    cursos.append([None, None, None, None, None])
    cursos.append(["MC4002", None, "x", "Otro", 1])
    cursos.cell(row=4, column=5).number_format = "0%"
    cursos.append(["MC4003", datetime.date(2026, 3, 15), None, datetime.datetime(2026, 3, 15, 14, 30), True])  # noqa: DTZ001 (valor de celda, sin zona)
    notas = libro.create_sheet("Notas")
    notas.append(["Solo una columna"])
    notas.append(["otra línea"])
    oculta = libro.create_sheet("Oculta")
    oculta.sheet_state = "hidden"
    oculta.append(["a", "b"])
    oculta.append([1, 2])
    libro.save(ruta)
    return ruta


TEXTO_DORADO = """## Hoja: Cursos
[Cursos] Plan de estudios 2026
[Cursos] Elaborado por la coordinación
[Cursos] Código: MC4001 | Nombre: Redes seguras | Columna C: extra | Nombre (D): Duplicado | Aprobado: 85%
[Cursos] Código: MC4002 | Columna C: x | Nombre (D): Otro | Aprobado: 1
[Cursos] Código: MC4003 | Nombre: 15/03/2026 | Nombre (D): 15/03/2026 14:30 | Aprobado: Sí
## Hoja: Notas
[Notas] Solo una columna
[Notas] otra línea"""


def test_el_texto_de_un_libro_de_excel_es_exactamente_el_de_siempre(tmp_path):
    ruta = _libro_variado(tmp_path / "libro.xlsx")

    cargador = XlsxLoader()
    assert cargador.load(ruta) == TEXTO_DORADO
    assert cargador.notes == []


@pytest.mark.parametrize("nombre", ["MAX_COLUMNAS", "MAX_FILAS_VACIAS_SEGUIDAS", "ERROR_ILEGIBLE", "ERROR_SIN_CONTENIDO", "_texto_de_celda"])
def test_el_cargador_de_excel_sigue_exponiendo_sus_nombres(nombre):
    from mia.ingestion.loaders import xlsx_loader

    assert hasattr(xlsx_loader, nombre)
