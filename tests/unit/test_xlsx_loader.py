"""Cargador de libros de Excel (feature 018): texto de una línea por fila con el contexto de la hoja y las columnas."""

import pytest

from mia.ingestion.loaders.base import LoaderError, get_loader
from mia.ingestion.loaders.xlsx_loader import ERROR_ILEGIBLE, ERROR_SIN_CONTENIDO, XlsxLoader
from tests.unit.libros_de_prueba import hacer_libro


def _leer(ruta) -> list[str]:
    return XlsxLoader().load(ruta).splitlines()


def test_el_factory_entrega_el_cargador_de_excel():
    assert isinstance(get_loader("xlsx"), XlsxLoader)


def test_cada_fila_con_contenido_es_una_linea_con_el_prefijo_de_su_hoja(tmp_path):
    # Una sola columna: no hay fila de encabezados (eso es la historia 2), cada fila es una línea.
    ruta = hacer_libro(tmp_path / "l.xlsx", {"Cursos": [["Redes"], ["Datos"], ["Seguridad"]]})

    lineas = _leer(ruta)

    assert lineas[0] == "## Hoja: Cursos"
    assert lineas[1:] == ["[Cursos] Redes", "[Cursos] Datos", "[Cursos] Seguridad"]


def test_las_hojas_se_escriben_una_tras_otra_cada_una_con_su_titulo(tmp_path):
    ruta = hacer_libro(tmp_path / "l.xlsx", {"Uno": [["a", "b"], [1, 2]], "Dos": [["c", "d"], [3, 4]]})

    lineas = _leer(ruta)

    assert lineas.index("## Hoja: Uno") < lineas.index("## Hoja: Dos")
    assert any(linea.startswith("[Uno]") for linea in lineas)
    assert any(linea.startswith("[Dos]") for linea in lineas)


def test_las_filas_totalmente_vacias_no_producen_linea(tmp_path):
    ruta = hacer_libro(tmp_path / "l.xlsx", {"H": [["a"], [None], ["x"], [None]]})

    assert _leer(ruta) == ["## Hoja: H", "[H] a", "[H] x"]


def test_un_archivo_que_no_es_un_libro_lanza_loader_error(tmp_path):
    ruta = tmp_path / "falso.xlsx"
    ruta.write_text("esto no es un libro", encoding="utf-8")

    with pytest.raises(LoaderError) as error:
        XlsxLoader().load(ruta)

    assert str(error.value) == ERROR_ILEGIBLE
    assert ERROR_ILEGIBLE == "No se pudo leer el libro: el archivo está dañado o protegido con contraseña."


def test_un_xml_de_hoja_corrupto_lanza_loader_error(tmp_path):
    import zipfile

    buena = hacer_libro(tmp_path / "buena.xlsx", {"H": [["a", "b"], [1, 2]]})
    rota = tmp_path / "rota.xlsx"
    with zipfile.ZipFile(buena) as origen, zipfile.ZipFile(rota, "w") as destino:
        for nombre in origen.namelist():
            datos = origen.read(nombre)
            if nombre == "xl/worksheets/sheet1.xml":
                datos = datos[: len(datos) // 2]
            destino.writestr(nombre, datos)

    with pytest.raises(LoaderError) as error:
        XlsxLoader().load(rota)

    assert str(error.value) == ERROR_ILEGIBLE


def test_un_libro_sin_celdas_con_contenido_lanza_loader_error(tmp_path):
    ruta = hacer_libro(tmp_path / "vacio.xlsx", {"H": [[None, None], [None]]})

    with pytest.raises(LoaderError) as error:
        XlsxLoader().load(ruta)

    assert str(error.value) == ERROR_SIN_CONTENIDO
    assert ERROR_SIN_CONTENIDO == "El libro no tiene hojas visibles con contenido."


def test_los_valores_de_las_filas_de_datos_estan_en_el_texto(tmp_path):
    ruta = hacer_libro(tmp_path / "l.xlsx", {"Cursos": [["Código", "Nombre", "Créditos"], ["MC4001", "Redes seguras", 3]]})

    texto = XlsxLoader().load(ruta)

    assert "MC4001" in texto and "Redes seguras" in texto and "3" in texto


# --- Historia 2: cada valor conserva el encabezado de su columna ---


def test_cada_fila_de_datos_lleva_el_encabezado_de_su_columna(tmp_path):
    ruta = hacer_libro(
        tmp_path / "l.xlsx",
        {"Cursos": [["Código", "Nombre", "Créditos"], ["MC4001", "Redes", 3], ["MC4002", "Datos", 4]]},
    )

    lineas = _leer(ruta)

    assert lineas == [
        "## Hoja: Cursos",
        "[Cursos] Código: MC4001 | Nombre: Redes | Créditos: 3",
        "[Cursos] Código: MC4002 | Nombre: Datos | Créditos: 4",
    ]


def test_las_celdas_vacias_de_una_fila_de_datos_se_omiten(tmp_path):
    ruta = hacer_libro(tmp_path / "l.xlsx", {"H": [["a", "b", "c"], ["x", None, "z"]]})

    assert _leer(ruta)[1] == "[H] a: x | c: z"


def test_las_filas_de_titulo_previas_se_conservan_y_los_encabezados_se_buscan_mas_abajo(tmp_path):
    ruta = hacer_libro(
        tmp_path / "l.xlsx",
        {"H": [["Horarios 2027"], [None], ["Curso", "Aula"], ["Redes", "A1"]]},
    )

    assert _leer(ruta) == ["## Hoja: H", "[H] Horarios 2027", "[H] Curso: Redes | Aula: A1"]


def test_una_hoja_de_una_sola_columna_no_tiene_encabezados(tmp_path):
    ruta = hacer_libro(tmp_path / "l.xlsx", {"H": [["uno"], ["dos"]]})

    assert _leer(ruta) == ["## Hoja: H", "[H] uno", "[H] dos"]


def test_un_encabezado_vacio_se_nombra_por_su_letra(tmp_path):
    ruta = hacer_libro(tmp_path / "l.xlsx", {"H": [["a", "b", "c", None], [1, 2, 3, 4]]})

    assert _leer(ruta)[1] == "[H] a: 1 | b: 2 | c: 3 | Columna D: 4"


def test_un_encabezado_repetido_agrega_la_letra_a_los_siguientes(tmp_path):
    ruta = hacer_libro(tmp_path / "l.xlsx", {"H": [["Nombre", "x", "y", "z", "Nombre"], ["Ana", 1, 2, 3, "Luis"]]})

    assert _leer(ruta)[1] == "[H] Nombre: Ana | x: 1 | y: 2 | z: 3 | Nombre (E): Luis"


def test_las_hojas_no_mezclan_encabezados(tmp_path):
    ruta = hacer_libro(
        tmp_path / "l.xlsx",
        {"Uno": [["a", "b"], [1, 2]], "Dos": [["c", "d"], [3, 4]]},
    )

    lineas = _leer(ruta)

    assert "[Uno] a: 1 | b: 2" in lineas
    assert "[Dos] c: 3 | d: 4" in lineas


def test_una_celda_combinada_aporta_su_valor_una_sola_vez(tmp_path):
    from openpyxl import Workbook

    libro = Workbook()
    hoja = libro.active
    hoja.title = "H"
    hoja.append(["a", "b", "c"])
    hoja.append(["unido", None, "fin"])
    hoja.merge_cells("A2:B2")
    ruta = tmp_path / "l.xlsx"
    libro.save(ruta)

    linea = _leer(ruta)[1]

    assert linea == "[H] a: unido | c: fin"
    assert linea.count("unido") == 1


def test_tildes_enes_y_saltos_de_linea_dentro_de_una_celda(tmp_path):
    ruta = hacer_libro(tmp_path / "l.xlsx", {"H": [["Descripción", "Año"], ["Diseño\ny gestión", "Ñandú ₡"]]})

    assert _leer(ruta)[1] == "[H] Descripción: Diseño y gestión | Año: Ñandú ₡"


# --- Historia 3: valores como los ve la persona ---

from datetime import date, datetime

from mia.ingestion.loaders.xlsx_loader import _texto_de_celda


@pytest.mark.parametrize(
    ("valor", "formato", "esperado"),
    [
        ("  hola  ", "General", "hola"),
        (datetime(2027, 3, 15), "dd/mm/yyyy", "15/03/2027"),  # noqa: DTZ001 (las fechas de Excel no tienen zona)
        (datetime(2027, 3, 15, 14, 30), "dd/mm/yyyy hh:mm", "15/03/2027 14:30"),  # noqa: DTZ001
        (date(2027, 3, 15), "yyyy-mm-dd", "15/03/2027"),
        (0.85, "0%", "85%"),
        (0.125, "0.0%", "12.5%"),
        (0.07, "0%", "7%"),
        (3.0, "General", "3"),
        (3.5, "General", "3.5"),
        (1250000, "#,##0", "1250000"),
        (True, "General", "Sí"),
        (False, "General", "No"),
        (None, "General", None),
        ("", "General", None),
        ("   ", "General", None),
        ("#DIV/0!", "General", None),
        ("#N/A", "General", None),
        ("#REF!", "General", None),
        ("#VALUE!", "General", None),
        ("#NAME?", "General", None),
        ("#NUM!", "General", None),
        ("#NULL!", "General", None),
    ],
)
def test_texto_de_celda_sigue_la_tabla_de_formatos(valor, formato, esperado):
    assert _texto_de_celda(valor, formato) == esperado


def test_un_libro_con_fecha_y_porcentaje_los_muestra_legibles(tmp_path):
    from openpyxl import Workbook

    libro = Workbook()
    hoja = libro.active
    hoja.title = "Calendario"
    hoja.append(["Actividad", "Inicio", "Avance"])
    hoja.append(["Matrícula", datetime(2027, 3, 15), 0.85])  # noqa: DTZ001
    hoja["B2"].number_format = "dd/mm/yyyy"
    hoja["C2"].number_format = "0%"
    ruta = tmp_path / "l.xlsx"
    libro.save(ruta)

    assert _leer(ruta)[1] == "[Calendario] Actividad: Matrícula | Inicio: 15/03/2027 | Avance: 85%"


def _libro_con_formula(ruta, resultado):
    """openpyxl no guarda resultados de fórmulas: se escribe `<v>` a mano dentro de la celda con `<f>`."""
    import re
    import zipfile

    from openpyxl import Workbook

    libro = Workbook()
    hoja = libro.active
    hoja.title = "Costos"
    hoja.append(["Rubro", "Monto"])
    hoja.append(["A", 2])
    hoja.append(["B", 3])
    hoja.append(["Total", "=SUM(B2:B3)"])
    base = ruta.with_name("base_" + ruta.name)
    libro.save(base)
    with zipfile.ZipFile(base) as origen, zipfile.ZipFile(ruta, "w") as destino:
        for nombre in origen.namelist():
            datos = origen.read(nombre)
            if nombre == "xl/worksheets/sheet1.xml" and resultado is not None:
                xml = datos.decode("utf-8")
                xml = re.sub(r"(<f>SUM\(B2:B3\)</f>)<v\s*/>|(<f>SUM\(B2:B3\)</f>)<v></v>", rf"\1\2<v>{resultado}</v>", xml)
                assert f"<v>{resultado}</v>" in xml
                datos = xml.encode("utf-8")
            destino.writestr(nombre, datos)
    return ruta


def test_una_formula_con_resultado_guardado_aparece_como_su_resultado(tmp_path):
    ruta = _libro_con_formula(tmp_path / "f.xlsx", 5)

    linea = _leer(ruta)[-1]

    assert linea == "[Costos] Rubro: Total | Monto: 5"
    assert "SUM" not in linea


def test_una_formula_sin_resultado_guardado_se_omite_sin_romper_la_hoja(tmp_path):
    ruta = _libro_con_formula(tmp_path / "f.xlsx", None)

    lineas = _leer(ruta)

    assert "[Costos] Rubro: A | Monto: 2" in lineas and "[Costos] Rubro: B | Monto: 3" in lineas
    assert lineas[-1] == "[Costos] Rubro: Total"


# --- Historia 4: hojas ocultas y tope de filas ---

from mia.config import settings


def test_las_hojas_ocultas_no_aparecen_en_el_texto(tmp_path):
    from openpyxl import Workbook

    libro = Workbook()
    visible = libro.active
    visible.title = "Visible"
    visible.append(["a", "b"])
    visible.append(["dato-visible", 1])
    oculta = libro.create_sheet("Oculta")
    oculta.append(["a", "b"])
    oculta.append(["dato-oculto", 2])
    oculta.sheet_state = "hidden"
    muy_oculta = libro.create_sheet("MuyOculta")
    muy_oculta.append(["a", "b"])
    muy_oculta.append(["dato-muy-oculto", 3])
    muy_oculta.sheet_state = "veryHidden"
    ruta = tmp_path / "l.xlsx"
    libro.save(ruta)

    texto = XlsxLoader().load(ruta)

    assert "dato-visible" in texto
    for oculto in ("dato-oculto", "dato-muy-oculto", "Oculta", "MuyOculta"):
        assert oculto not in texto


def test_una_hoja_de_grafico_se_lee_sin_falla_y_no_aparece_en_el_texto(tmp_path):
    from openpyxl import Workbook
    from openpyxl.chart import BarChart, Reference

    libro = Workbook()
    hoja = libro.active
    hoja.title = "Datos"
    hoja.append(["a", "b"])
    hoja.append(["x", 1])
    hoja.append(["y", 2])
    grafico = BarChart()
    grafico.add_data(Reference(hoja, min_col=2, min_row=1, max_row=3), titles_from_data=True)
    hoja_de_grafico = libro.create_chartsheet("Grafico")
    hoja_de_grafico.add_chart(grafico)
    ruta = tmp_path / "l.xlsx"
    libro.save(ruta)

    texto = XlsxLoader().load(ruta)

    assert "[Datos] a: x | b: 1" in texto
    assert "Grafico" not in texto


def test_un_libro_con_solo_hojas_visibles_vacias_y_una_oculta_con_datos_es_un_error(tmp_path):
    from openpyxl import Workbook

    libro = Workbook()
    libro.active.title = "Vacia"
    oculta = libro.create_sheet("Oculta")
    oculta.append(["a", "b"])
    oculta.append([1, 2])
    oculta.sheet_state = "hidden"
    ruta = tmp_path / "l.xlsx"
    libro.save(ruta)

    with pytest.raises(LoaderError) as error:
        XlsxLoader().load(ruta)

    assert str(error.value) == ERROR_SIN_CONTENIDO


def _filas(n):
    return [[f"fila-{i}", i] for i in range(1, n + 1)]


def test_con_mas_filas_que_el_tope_se_recorta_con_aviso_en_el_texto_y_en_las_notas(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "max_excel_rows", 100)
    ruta = hacer_libro(tmp_path / "l.xlsx", {"H": [["nombre", "valor"], *_filas(300)]})
    cargador = XlsxLoader()

    lineas = cargador.load(ruta).splitlines()

    datos = [linea for linea in lineas if linea.startswith("[H] nombre:")]
    assert len(datos) == 100
    assert lineas[-1] == '[Aviso: el libro se recortó en la fila 102 de la hoja "H" por superar el tope de 100 filas]'
    assert cargador.notes == ['El libro se recortó en la fila 102 de la hoja "H" por superar el tope de 100 filas.']
    assert "fila-101" not in "\n".join(lineas)


def test_el_tope_cuenta_las_filas_de_todas_las_hojas_visibles_juntas(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "max_excel_rows", 100)
    ruta = hacer_libro(
        tmp_path / "l.xlsx",
        {"Uno": [["nombre", "valor"], *_filas(80)], "Dos": [["nombre", "valor"], *_filas(80)]},
    )

    lineas = XlsxLoader().load(ruta).splitlines()

    assert len([linea for linea in lineas if linea.startswith("[Uno] nombre:")]) == 80
    assert len([linea for linea in lineas if linea.startswith("[Dos] nombre:")]) == 20
    assert 'de la hoja "Dos"' in lineas[-1]


def test_un_libro_con_exactamente_el_tope_no_se_recorta(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "max_excel_rows", 100)
    ruta = hacer_libro(tmp_path / "l.xlsx", {"H": [["nombre", "valor"], *_filas(100)]})
    cargador = XlsxLoader()

    lineas = cargador.load(ruta).splitlines()

    assert len([linea for linea in lineas if linea.startswith("[H] nombre:")]) == 100
    assert not any(linea.startswith("[Aviso") for linea in lineas)
    assert cargador.notes == []


def test_un_libro_que_no_se_recorta_deja_las_notas_vacias_y_cada_lectura_las_reinicia(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "max_excel_rows", 100)
    grande = hacer_libro(tmp_path / "grande.xlsx", {"H": [["nombre", "valor"], *_filas(300)]})
    chico = hacer_libro(tmp_path / "chico.xlsx", {"H": [["nombre", "valor"], *_filas(3)]})
    cargador = XlsxLoader()

    cargador.load(grande)
    assert cargador.notes
    cargador.load(chico)

    assert cargador.notes == []
