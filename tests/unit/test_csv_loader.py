"""Cargador de CSV (feature 021): texto de una línea por fila con el encabezado de cada columna, como el de Excel pero sin marca de
hoja. Los archivos se generan con `csv_de_prueba.py`: datos inventados, nunca reales."""

import csv
import io

import pytest

from mia.ingestion.loaders.base import LoaderError, get_loader
from mia.ingestion.loaders.csv_loader import CsvLoader
from tests.unit.csv_de_prueba import csv_bytes, csv_como_el_real, tabla_inventada


def _leer(tmp_path, contenido: bytes) -> list[str]:
    ruta = tmp_path / "datos.csv"
    ruta.write_bytes(contenido)
    return CsvLoader().load(ruta).splitlines()


def _ruta(tmp_path, contenido: bytes):
    ruta = tmp_path / "datos.csv"
    ruta.write_bytes(contenido)
    return ruta


def test_el_factory_entrega_el_cargador_de_csv():
    assert isinstance(get_loader("csv"), CsvLoader)


def test_cada_fila_es_una_linea_con_sus_encabezados_y_sin_marca_de_hoja(tmp_path):
    lineas = _leer(tmp_path, csv_bytes(tabla_inventada(2), separador=",", codificacion="utf-8"))

    assert lineas == [
        "Código: MC4001 | Nombre del curso: Curso número 1 (Ñandú) | Créditos: 4 | Profesor: Persona 01 | Correo: correo01@ejemplo.test",
        "Código: MC4002 | Nombre del curso: Curso número 2 (Ñandú) | Créditos: 3 | Profesor: Persona 02 | Correo: correo02@ejemplo.test",
    ]
    assert not any(linea.startswith(("## Hoja", "[")) for linea in lineas)


def test_sin_avisos_el_cargador_deja_las_notas_vacias(tmp_path):
    cargador = CsvLoader()

    cargador.load(_ruta(tmp_path, csv_bytes(tabla_inventada(2), separador=",", codificacion="utf-8")))

    assert cargador.notes == []


@pytest.mark.parametrize("contenido", [b"", b"\r\n\r\n  \r\n", b"Codigo,Nombre\r\n", b",,\r\n,,\r\n"])
def test_un_archivo_vacio_o_solo_con_encabezados_es_un_error_de_sin_contenido(tmp_path, contenido):
    with pytest.raises(LoaderError) as error:
        CsvLoader().load(_ruta(tmp_path, contenido))

    assert str(error.value) == "El archivo CSV no tiene contenido."


def test_el_csv_de_ejemplo_con_la_estructura_real_tiene_45_registros_de_29_campos():
    texto = csv_como_el_real().decode("cp1252")

    registros = list(csv.reader(io.StringIO(texto, newline=""), delimiter=";", strict=True))

    assert len(registros) == 45
    assert {len(r) for r in registros} == {29}
    assert registros[0][-1] == ""  # la última columna no tiene encabezado
    assert sum(1 for r in registros for celda in r if "\n" in celda) == 11
    assert sum(1 for r in registros if not any(r)) == 3


# --- Codificación y separador (US2, SC-002) ---

LINEAS_ESPERADAS = [
    "Código: MC4001 | Nombre del curso: Curso número 1 (Ñandú) | Créditos: 4 | Profesor: Persona 01 | Correo: correo01@ejemplo.test",
    "Código: MC4002 | Nombre del curso: Curso número 2 (Ñandú) | Créditos: 3 | Profesor: Persona 02 | Correo: correo02@ejemplo.test",
]
ERROR_ILEGIBLE = (
    "No se pudo leer el archivo: no es un CSV de texto en UTF-8 ni en Windows-1252. "
    "Guárdalo de nuevo como «CSV UTF-8» y vuelve a subirlo."
)


@pytest.mark.parametrize("fin_de_linea", ["\r\n", "\n", "\r"], ids=["crlf", "lf", "cr"])
@pytest.mark.parametrize("separador", [";", ",", "\t", "|"], ids=["punto_y_coma", "coma", "tabulador", "barra"])
@pytest.mark.parametrize(
    ("codificacion", "bom"), [("utf-8", False), ("utf-8", True), ("cp1252", False)], ids=["utf8", "utf8_con_bom", "windows1252"]
)
def test_todas_las_variantes_reales_se_leen_igual_sin_indicar_nada(tmp_path, codificacion, bom, separador, fin_de_linea):
    contenido = csv_bytes(tabla_inventada(2), separador=separador, codificacion=codificacion, bom=bom, fin_de_linea=fin_de_linea)

    texto = CsvLoader().load(_ruta(tmp_path, contenido))

    assert texto.splitlines() == LINEAS_ESPERADAS
    assert "Ã" not in texto and "�" not in texto and "﻿" not in texto


def test_una_coma_dentro_de_un_texto_no_parte_la_celda_en_un_archivo_con_punto_y_coma(tmp_path):
    registros = [["Código", "Nombre", "Dirección"], ["A1", "Ana", "Calle 1, casa 2"], ["A2", "Beto", "Avenida 5"], ["A3", "Carla", "Plaza, local 9"]]

    lineas = _leer(tmp_path, csv_bytes(registros, separador=";", codificacion="utf-8"))

    assert lineas[0] == "Código: A1 | Nombre: Ana | Dirección: Calle 1, casa 2"
    assert lineas[2] == "Código: A3 | Nombre: Carla | Dirección: Plaza, local 9"


def test_un_punto_y_coma_dentro_de_un_texto_no_parte_la_celda_en_un_archivo_con_comas(tmp_path):
    registros = [["Código", "Nombre", "Nota"], ["A1", "Ana", "uno; dos"], ["A2", "Beto", "tres"], ["A3", "Carla", "cuatro; cinco"]]

    lineas = _leer(tmp_path, csv_bytes(registros, separador=",", codificacion="utf-8"))

    assert lineas[0] == "Código: A1 | Nombre: Ana | Nota: uno; dos"
    assert lineas[2] == "Código: A3 | Nombre: Carla | Nota: cuatro; cinco"


def test_con_solo_dos_registros_elige_el_separador_correcto(tmp_path):
    contenido = "Nombre;Dirección\r\nAna;Calle 1, casa 2\r\n".encode()

    assert _leer(tmp_path, contenido) == ["Nombre: Ana | Dirección: Calle 1, casa 2"]


@pytest.mark.parametrize(
    "contenido",
    [
        "Nombre;Edad\r\nAna;31\r\n".encode("utf-16"),  # Excel con «Texto Unicode»: UTF-16 con marca de orden de bytes
        "Nombre;Edad\r\nAna;31\r\n".encode("utf-16-le"),  # sin marca: trae bytes nulos
        b"PK\x03\x04\x00\x00\x00\x00 un xlsx renombrado a csv",
        b"Nombre;Edad\r\nAna;\x81\x8d\x8f\x90\x9d\r\n",  # bytes que no existen ni en UTF-8 ni en Windows-1252
    ],
    ids=["utf16_con_marca", "utf16_sin_marca", "xlsx_renombrado", "bytes_sin_sentido"],
)
def test_un_archivo_que_no_es_texto_utf8_ni_windows1252_da_el_error_con_la_sugerencia(tmp_path, contenido):
    with pytest.raises(LoaderError) as error:
        CsvLoader().load(_ruta(tmp_path, contenido))

    assert str(error.value) == ERROR_ILEGIBLE


def test_un_archivo_de_una_sola_columna_se_lee_como_una_columna_y_avisa(tmp_path):
    cargador = CsvLoader()

    lineas = cargador.load(_ruta(tmp_path, b"Nombre\r\nAna\r\nBeto\r\n")).splitlines()

    assert lineas[:3] == ["Nombre", "Ana", "Beto"]
    aviso = "No se reconoció un separador de columnas: se leyó como una sola columna."
    assert cargador.notes == [aviso]
    assert lineas[-1] == "[Aviso: no se reconoció un separador de columnas: se leyó como una sola columna]"


def test_el_csv_con_la_estructura_real_se_lee_completo_sin_avisos(tmp_path):
    cargador = CsvLoader()

    texto = cargador.load(_ruta(tmp_path, csv_como_el_real()))

    lineas = texto.splitlines()
    assert len(lineas) == 41  # 45 registros, menos el encabezado y las 3 filas vacías
    assert cargador.notes == []
    assert "Ã" not in texto and "�" not in texto
    assert "Título: Ingeniería en Computación" in lineas[0] and "Promedio de cursos: 81" in lineas[0]
    # La última columna no tiene encabezado: se nombra por su letra y solo aparece donde hay un valor.
    assert any("Columna AC: Nota 5" in linea for linea in lineas)


# --- Estructura de la tabla (US3) ---


def _texto(tmp_path, registros, **opciones) -> list[str]:
    return _leer(tmp_path, csv_bytes(registros, codificacion=opciones.pop("codificacion", "utf-8"), **opciones))


def test_una_celda_con_saltos_de_linea_es_una_sola_celda_de_una_sola_linea(tmp_path):
    registros = [["Código", "Labores"], ["A1", "línea 1\nlínea 2\r\nlínea 3"], ["A2", "otra"]]

    lineas = _texto(tmp_path, registros)

    assert lineas == ["Código: A1 | Labores: línea 1 línea 2 línea 3", "Código: A2 | Labores: otra"]


def test_las_lineas_en_blanco_y_las_filas_de_solo_separadores_no_generan_texto(tmp_path):
    contenido = "Código;Nombre\r\n\r\nA1;Ana\r\n;;\r\n   ;  \r\nA2;Beto\r\n".encode()

    assert _leer(tmp_path, contenido) == ["Código: A1 | Nombre: Ana", "Código: A2 | Nombre: Beto"]


def test_una_celda_vacia_no_deja_su_encabezado_en_la_linea(tmp_path):
    lineas = _texto(tmp_path, [["Código", "Nombre", "Correo"], ["A1", "", "a@ejemplo.test"]])

    assert lineas == ["Código: A1 | Correo: a@ejemplo.test"]


def test_la_columna_final_sin_encabezado_se_nombra_por_su_letra(tmp_path):
    encabezados = [f"C{i}" for i in range(1, 29)] + [""]  # 29 columnas, la última sin nombre
    fila = ["x"] * 28 + ["valor final"]

    lineas = _texto(tmp_path, [encabezados, fila])

    assert lineas[0].endswith("C28: x | Columna AC: valor final")


def test_un_encabezado_repetido_lleva_la_letra_de_su_columna(tmp_path):
    lineas = _texto(tmp_path, [["Nombre", "Edad", "Nombre"], ["Ana", "31", "Beto"]])

    assert lineas == ["Nombre: Ana | Edad: 31 | Nombre (C): Beto"]


def test_una_fila_con_una_celda_de_mas_la_nombra_por_su_letra_y_una_con_menos_no_desplaza_nada(tmp_path):
    contenido = "Código;Nombre;Edad\r\nA1;Ana;31;extra\r\nA2;Beto\r\nA3;;40\r\n".encode()

    assert _leer(tmp_path, contenido) == [
        "Código: A1 | Nombre: Ana | Edad: 31 | Columna D: extra",
        "Código: A2 | Nombre: Beto",
        "Código: A3 | Edad: 40",
    ]


def test_un_titulo_y_notas_arriba_de_la_tabla_van_como_texto_simple(tmp_path):
    contenido = "Proceso 2026\r\nElaborado por la coordinación\r\nCódigo;Nombre\r\nA1;Ana\r\n".encode()

    lineas = _leer(tmp_path, contenido)

    assert lineas == ["Proceso 2026", "Elaborado por la coordinación", "Código: A1 | Nombre: Ana"]


def test_los_valores_se_conservan_como_estan_escritos_y_nada_se_evalua(tmp_path):
    registros = [
        ["Campo", "Valor"],
        ["fecha", "15/03/2026"],
        ["porcentaje", "85%"],
        ["moneda", "₡1 250 000"],
        ["código", "007"],
        ["fórmula", "=SUMA(A1:A2)"],
        ["peligrosa", "=HYPERLINK(\"http://ejemplo.test\")"],
        ["más", "+1 000"],
    ]

    lineas = _texto(tmp_path, registros, separador=",")

    assert lineas == [
        "Campo: fecha | Valor: 15/03/2026",
        "Campo: porcentaje | Valor: 85%",
        "Campo: moneda | Valor: ₡1 250 000",
        "Campo: código | Valor: 007",
        "Campo: fórmula | Valor: =SUMA(A1:A2)",
        'Campo: peligrosa | Valor: =HYPERLINK("http://ejemplo.test")',
        "Campo: más | Valor: +1 000",
    ]


def test_los_espacios_repetidos_y_los_saltos_de_linea_dentro_de_una_celda_se_unen_en_uno(tmp_path):
    lineas = _texto(tmp_path, [["Código", "Texto"], ["A1", "  mucho    espacio\t y\n\nsaltos  "]])

    assert lineas == ["Código: A1 | Texto: mucho espacio y saltos"]


def test_los_caracteres_especiales_se_conservan_sin_alterarse(tmp_path):
    registros = [["Nombre", "Texto"], ["Ñandú", "«güe» €, ü, ¿qué?, ¡sí!, %, #"]]

    assert _texto(tmp_path, registros) == ["Nombre: Ñandú | Texto: «güe» €, ü, ¿qué?, ¡sí!, %, #"]


# --- Límites y robustez (US4) ---


def _cargar(tmp_path, contenido: bytes):
    cargador = CsvLoader()
    texto = cargador.load(_ruta(tmp_path, contenido))
    return texto.splitlines(), cargador.notes


def _tabla_larga(filas: int) -> list[list[str]]:
    return [["Código", "Nombre"], *[[f"A{i}", f"Persona {i:03d}"] for i in range(1, filas + 1)]]


def test_mas_filas_que_el_tope_se_recorta_con_nota_y_aviso_en_el_texto(tmp_path, monkeypatch):
    monkeypatch.setattr("mia.ingestion.loaders.csv_loader.settings.max_excel_rows", 100)

    lineas, notas = _cargar(tmp_path, csv_bytes(_tabla_larga(150), codificacion="utf-8"))

    assert len(lineas) == 101  # 100 filas y la línea de aviso
    assert lineas[0] == "Código: A1 | Nombre: Persona 001" and lineas[99] == "Código: A100 | Nombre: Persona 100"
    # El registro 1 es el encabezado, los registros 2 a 101 se escriben y el 102 es el primero que no cabe.
    assert notas == ["El archivo se recortó en la fila 102 por superar el tope de 100 filas."]
    assert lineas[-1] == "[Aviso: el archivo se recortó en la fila 102 por superar el tope de 100 filas]"


def test_con_exactamente_el_tope_de_filas_no_hay_aviso(tmp_path, monkeypatch):
    monkeypatch.setattr("mia.ingestion.loaders.csv_loader.settings.max_excel_rows", 100)

    lineas, notas = _cargar(tmp_path, csv_bytes(_tabla_larga(100), codificacion="utf-8"))

    assert len(lineas) == 100 and notas == []


def test_mas_de_200_columnas_se_leen_las_primeras_200_y_se_avisa(tmp_path):
    encabezados = [f"c{i}" for i in range(1, 202)]
    fila = [f"v{i}" for i in range(1, 202)]

    lineas, notas = _cargar(tmp_path, csv_bytes([encabezados, fila], codificacion="utf-8"))

    assert notas == ["En el archivo se leyeron solo las primeras 200 columnas."]
    assert "c200: v200" in lineas[0] and "c201" not in lineas[0]


def test_tras_las_filas_vacias_seguidas_deja_de_leer_y_avisa(tmp_path):
    from mia.ingestion.loaders.tabular import MAX_FILAS_VACIAS_SEGUIDAS

    registros = [["a", "b"], ["1", "2"], *[["", ""]] * MAX_FILAS_VACIAS_SEGUIDAS, ["9", "9"]]

    lineas, notas = _cargar(tmp_path, csv_bytes(registros, codificacion="utf-8"))

    assert lineas[0] == "a: 1 | b: 2" and "a: 9" not in " ".join(lineas)
    assert notas == [
        (
            f"Se dejó de leer el archivo en la fila {2 + MAX_FILAS_VACIAS_SEGUIDAS} tras {MAX_FILAS_VACIAS_SEGUIDAS} filas "
            "vacías seguidas; si había datos después, no se ingestaron."
        )
    ]


def test_una_celda_de_mas_de_20000_caracteres_se_recorta_con_aviso(tmp_path):
    from mia.ingestion.loaders.csv_loader import MAX_CELDA_CARACTERES
    from tests.unit.csv_de_prueba import csv_con_celda_de

    assert MAX_CELDA_CARACTERES == 20000
    lineas, notas = _cargar(tmp_path, csv_con_celda_de(50_000))

    assert lineas[0] == "Código: A1 | Texto: " + "x" * 20000
    assert notas == ["Se recortó 1 celda que superaba 20000 caracteres."]
    assert lineas[-1] == "[Aviso: se recortó 1 celda que superaba 20000 caracteres]"


def test_varias_celdas_largas_se_cuentan_en_plural(tmp_path):
    registros = [["Código", "Texto"], *[[f"A{i}", "y" * 25_000] for i in range(3)], ["B", "corta"]]

    _, notas = _cargar(tmp_path, csv_bytes(registros, codificacion="utf-8"))

    assert notas == ["Se recortaron 3 celdas que superaban 20000 caracteres."]


def test_una_celda_de_dos_millones_de_caracteres_no_falla_y_no_deja_cambiado_el_limite_del_modulo(tmp_path):
    from tests.unit.csv_de_prueba import csv_con_celda_de

    antes = csv.field_size_limit()

    lineas, notas = _cargar(tmp_path, csv_con_celda_de(2_000_000))

    assert csv.field_size_limit() == antes
    assert len(lineas[0]) == len("Código: A1 | Texto: ") + 20000
    assert notas == ["Se recortó 1 celda que superaba 20000 caracteres."]


def test_una_comilla_sin_cerrar_no_se_traga_el_resto_del_archivo(tmp_path):
    from tests.unit.csv_de_prueba import csv_con_comilla_sin_cerrar

    lineas, notas = _cargar(tmp_path, csv_con_comilla_sin_cerrar())

    assert lineas[:4] == [
        "Código: A1 | Nombre: Ana",
        'Código: A2 | Nombre: "Beto sin cerrar',
        "Código: A3 | Nombre: Carla",
        "Código: A4 | Nombre: Diego",
    ]
    assert notas == ["El archivo tiene comillas sin cerrar: se leyó sin interpretarlas."]
    assert lineas[-1] == "[Aviso: el archivo tiene comillas sin cerrar: se leyó sin interpretarlas]"


def test_un_archivo_bien_formado_no_produce_el_aviso_de_comillas(tmp_path):
    registros = [["Código", "Texto"], ["A1", 'dijo "hola"'], ["A2", "dos\nlíneas"]]

    _, notas = _cargar(tmp_path, csv_bytes(registros, codificacion="utf-8"))

    assert notas == []


def test_un_csv_de_5000_filas_se_lee_en_un_tiempo_comparable_al_de_un_txt_equivalente(tmp_path):
    import statistics
    import time

    from mia.ingestion.loaders.txt_loader import TxtLoader

    contenido = csv_bytes(_tabla_larga(5000), codificacion="utf-8")
    ruta_csv = _ruta(tmp_path, contenido)
    ruta_txt = tmp_path / "datos.txt"
    ruta_txt.write_bytes(contenido)

    def medir(cargador, ruta):
        tiempos = []
        for _ in range(3):
            inicio = time.perf_counter()
            cargador.load(ruta)
            tiempos.append(time.perf_counter() - inicio)
        return statistics.median(tiempos)

    csv_s, txt_s = medir(CsvLoader(), ruta_csv), medir(TxtLoader(), ruta_txt)

    # Un margen holgado (10 veces) para no depender de la máquina: lo que importa es que no sea de otro orden de magnitud.
    assert csv_s < max(txt_s * 10, 0.5)


# --- Codificaciones mezcladas: celdas en UTF-8 dentro de un archivo en Windows-1252 (visto en un archivo real) ---


def test_un_archivo_en_windows1252_con_algunas_celdas_en_utf8_se_lee_bien(tmp_path):
    from tests.unit.csv_de_prueba import csv_con_codificaciones_mezcladas

    contenido = csv_con_codificaciones_mezcladas()
    with pytest.raises(UnicodeDecodeError):
        contenido.decode("utf-8")  # ni UTF-8 ...
    assert "Ã" in contenido.decode("cp1252", errors="replace")  # ... ni Windows-1252 por separado lo leen bien

    lineas, notas = _cargar(tmp_path, contenido)

    assert lineas == [
        "Código: A1 | Título: Ingeniería en Computación | Descripción: Cañón de datos",
        "Código: A2 | Título: Administración | Descripción: Número de teléfono",
        "Código: A3 | Título: Gestión pública | Descripción: Año 2026 «completo» – “ok” €",
    ]
    assert notas == []


def test_un_archivo_solo_en_windows1252_con_muchos_simbolos_no_cambia(tmp_path):
    # Ningún byte forma una letra válida de UTF-8: todo se lee como Windows-1252, igual que antes.
    registros = [["Código", "Texto"], ["A1", "Ñandú ± 5°, ½ «x» ¡hola! ¿qué? € ª º"], ["A2", "ÓÍÚ áéí óú ü"]]

    lineas, notas = _cargar(tmp_path, csv_bytes(registros, codificacion="cp1252"))

    assert lineas == ["Código: A1 | Texto: Ñandú ± 5°, ½ «x» ¡hola! ¿qué? € ª º", "Código: A2 | Texto: ÓÍÚ áéí óú ü"]
    assert notas == []
