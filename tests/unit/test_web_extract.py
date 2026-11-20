"""Extracción del texto de una página web (feature 022). Páginas inventadas de tests/fixtures/web/."""

from datetime import UTC, datetime
from itertools import pairwise

from mia.config import settings
from mia.ingestion.web.extract import armar_documento, extraer, nombre_del_documento
from tests.unit.web_de_prueba import pagina, pagina_cp1252

BASE = "https://www.ejemplo.test/programa"


def test_el_titulo_prefiere_og_title_luego_title_y_luego_el_primer_h1():
    assert extraer(pagina("programa.html"), BASE).titulo == "Maestría de Ejemplo"

    solo_title = "<html><head><title>Admisión | Sitio Ejemplo</title></head><body><main><h1>Otro</h1></main></body></html>"
    assert extraer(solo_title, BASE).titulo == "Admisión"  # el sufijo coincide con el sitio y se quita

    sin_sitio = "<html><head><title>Admisión | Otra Cosa</title></head><body></body></html>"
    assert extraer(sin_sitio, BASE).titulo == "Admisión | Otra Cosa"  # no coincide con el sitio: se conserva

    solo_h1 = "<html><body><main><h1>Plan de estudios</h1><p>Texto.</p></main></body></html>"
    assert extraer(solo_h1, BASE).titulo == "Plan de estudios"

    assert extraer("<html><body><p>Sin título</p></body></html>", BASE).titulo == ""


def test_el_sufijo_del_sitio_no_deja_el_titulo_vacio():
    solo_sitio = "<html><head><title>Sitio Ejemplo | Sitio Ejemplo</title></head><body></body></html>"

    assert extraer(solo_sitio, BASE).titulo != ""


def test_el_texto_trae_los_parrafos_del_contenido_principal():
    texto = extraer(pagina("programa.html"), BASE).texto

    assert "Maestría de Ejemplo" in texto
    assert "cuatro semestres" in texto
    assert "Requisitos de admisión" in texto


def test_scripts_estilos_y_noscript_no_aparecen():
    texto = extraer(pagina("programa.html"), BASE).texto

    assert "TEXTO-DE-SCRIPT" not in texto and "color: red" not in texto
    assert "requiere JavaScript" not in extraer(pagina("vacia_js.html"), BASE).texto


def test_los_caracteres_de_control_y_espacios_no_separables_se_normalizan_a_nfc():
    html = (
        "<html><body><main><p>Educación superior\u200b  con\x07 control</p>"
        "<p>   </p><p>Segunda   línea</p></main></body></html>"
    )

    texto = extraer(html, BASE).texto

    assert texto == "Educación superior con control\nSegunda línea"


def test_armar_documento_pone_la_fuente_primero_luego_el_nombre_y_el_contenido():
    ahora = datetime(2026, 11, 21, 3, 30, tzinfo=UTC)  # 20 de noviembre a las 21:30 en Costa Rica

    documento = armar_documento("https://ejemplo.test/programa", "Maestría de Ejemplo", "Línea 1\nLínea 2", ahora)

    assert documento.splitlines()[0] == (
        "Fuente: https://ejemplo.test/programa (consultada el 20 de noviembre de 2026)"
    )
    assert documento.splitlines()[1] == "Maestría de Ejemplo"
    assert documento.splitlines()[2] == ""
    assert documento.endswith("Línea 1\nLínea 2")


def test_armar_documento_usa_la_zona_horaria_configurada(monkeypatch):
    ahora = datetime(2026, 3, 1, 3, 0, tzinfo=UTC)

    assert "(consultada el 28 de febrero de 2026)" in armar_documento("https://e.test/", "N", "t", ahora)
    monkeypatch.setattr(settings, "cap_timezone", "UTC")
    assert "(consultada el 1 de marzo de 2026)" in armar_documento("https://e.test/", "N", "t", ahora)


def test_nombre_del_documento_prefiere_el_propio_luego_el_titulo_y_luego_el_sitio():
    f = nombre_del_documento
    assert f("  Mi nombre  ", "Título", "https://www.ejemplo.test/a") == "Mi nombre"
    assert f("", "Título", "https://www.ejemplo.test/a") == "Título"
    assert f("   ", "Título", "https://www.ejemplo.test/a") == "Título"
    assert f(None, "", "https://www.ejemplo.test/a") == "www.ejemplo.test"


def test_nombre_del_documento_se_limpia_y_se_recorta_a_200_sin_error():
    f = nombre_del_documento
    assert f("Línea 1\nLínea 2\t\x07fin", "", "https://e.test/") == "Línea 1 Línea 2 fin"
    assert len(f("a" * 300, "", "https://e.test/")) == 200
    assert not f("Programa.web", "", "https://e.test/").endswith(".web")


# ---------- enlaces y elementos incrustados (US3) ----------

BASE_ENLACES = "https://ejemplo.test/seccion/pagina"


def _texto_de_enlaces():
    return extraer(pagina("enlaces.html"), BASE_ENLACES).texto


def test_los_enlaces_relativos_se_escriben_con_su_direccion_completa():
    texto = _texto_de_enlaces()

    assert "otra página del sitio (https://ejemplo.test/otra)" in texto
    assert "página hermana (https://ejemplo.test/hermana)" in texto
    assert "hoja relativa (https://ejemplo.test/seccion/hoja)" in texto
    assert "sitio externo (https://externo.ejemplo.test/info)" in texto


def test_el_enlace_a_un_pdf_queda_como_texto_con_su_direccion():
    texto = _texto_de_enlaces()

    assert "reglamento en PDF (https://ejemplo.test/archivos/reglamento.pdf)" in texto


def test_las_anclas_y_los_destinos_que_no_son_web_dejan_solo_el_texto():
    texto = _texto_de_enlaces()

    assert "ancla interna" in texto and "ancla interna (" not in texto
    assert "Enlace de programación" in texto and "javascript" not in texto
    assert "correo de contacto" in texto and "mailto" not in texto and "correo de contacto (" not in texto
    assert "teléfono" in texto and "tel:" not in texto and "teléfono (" not in texto


def test_si_el_texto_del_enlace_ya_es_su_direccion_no_se_repite():
    texto = _texto_de_enlaces()

    assert "Dirección escrita como texto: https://ejemplo.test/x." in texto
    assert "https://ejemplo.test/x (https://ejemplo.test/x)" not in texto


def test_un_enlace_sin_texto_no_deja_parentesis_sueltos():
    texto = _texto_de_enlaces()

    assert "()" not in texto and "solo-imagen" not in texto


def test_lo_incrustado_no_aporta_texto():
    texto = _texto_de_enlaces()

    for ajeno in ("TEXTO-DE-MARCO", "TEXTO-DE-VIDEO", "TEXTO-ALT-DE-IMAGEN", "TEXTO-DE-SCRIPT", "incrustado.ejemplo.test"):
        assert ajeno not in texto


def test_un_enlace_a_un_esquema_distinto_de_http_se_trata_como_las_demas_direcciones_omitidas():
    html = '<html><body><main><p>' + "Texto de relleno suficiente. " * 5 + '<a href="ftp://ejemplo.test/archivo">el archivo</a></p></main></body></html>'

    texto = extraer(html, BASE_ENLACES).texto

    assert "el archivo" in texto and "ftp" not in texto


# ---------- ruido y estructura (US4) ----------

BASE_RUIDO = "https://ejemplo.test/calendario"
MENUS = ["MENU-", "MIGAS-", "BARRA-LATERAL", "BOTON-", "SOCIAL-", "COOKIES-", "PIE-", "Leer más"]


def test_el_ruido_de_las_paginas_de_prueba_no_aparece_y_los_datos_principales_si():
    for archivo, base in (("programa.html", BASE), ("ruidosa.html", BASE_RUIDO)):
        texto = extraer(pagina(archivo), base).texto
        for ruido in MENUS + ["PIE-DERECHOS", "Usamos cookies"]:
            assert ruido not in texto, (archivo, ruido)

    programa = extraer(pagina("programa.html"), BASE).texto
    for dato in ("80", "16 de marzo al 17 de julio de 2026", "Créditos: 4", "Créditos: 3"):
        assert dato in programa
    calendario = extraer(pagina("ruidosa.html"), BASE_RUIDO).texto
    for dato in ("9 de febrero", "12 de junio", "20 de enero al 6 de febrero"):
        assert dato in calendario


def test_nav_header_footer_aside_form_y_button_fuera_del_contenido_principal_no_aportan_texto():
    html = (
        "<html><body><header>ENCABEZADO-DEL-SITIO</header><nav>NAVEGACION</nav><aside>LATERAL</aside>"
        "<form>BUSCADOR</form><div>Contenido sin main ni article, suficiente para comprobar el comportamiento.</div>"
        "<button>BOTON</button><footer>PIE</footer></body></html>"
    )

    texto = extraer(html, BASE).texto

    assert texto == "Contenido sin main ni article, suficiente para comprobar el comportamiento."


def test_clases_e_ids_de_ruido_se_descartan_pero_un_nombre_parecido_se_conserva():
    html = (
        "<html><body><main>"
        '<div class="menu">MENU-A</div><div id="social-share">COMPARTIR</div><div class="cookie-banner">COOKIES</div>'
        '<div class="sidebar">LATERAL</div><div class="breadcrumbs">MIGAS</div><div class="advertisement">ANUNCIO</div>'
        '<p class="menu-item-description">Descripción del plato que sí es contenido</p>'
        '<p class="share-price-table">Precio de la acción que sí es contenido</p>'
        "</main></body></html>"
    )

    texto = extraer(html, BASE).texto

    for ruido in ("MENU-A", "COMPARTIR", "COOKIES", "LATERAL", "MIGAS", "ANUNCIO"):
        assert ruido not in texto
    assert "Descripción del plato que sí es contenido" in texto
    assert "Precio de la acción que sí es contenido" in texto


def test_el_contenido_de_main_o_article_tiene_prioridad_sobre_el_resto_del_cuerpo():
    html = "<html><body><div>FUERA-DEL-ARTICULO</div><article><p>Dentro del artículo</p></article></body></html>"

    assert extraer(html, BASE).texto == "Dentro del artículo"


def test_el_encabezado_de_un_articulo_con_su_titulo_se_conserva():
    html = "<html><body><article><header><h1>Título del artículo</h1></header><p>Cuerpo.</p></article></body></html>"

    assert extraer(html, BASE).texto == "Título del artículo\nCuerpo."


def test_cada_titulo_va_en_su_propia_linea():
    html = "<html><body><main><h1>Uno</h1>texto suelto<h2>Dos</h2><p>Párrafo</p><h3>Tres</h3></main></body></html>"

    assert extraer(html, BASE).texto.splitlines() == ["Uno", "texto suelto", "Dos", "Párrafo", "Tres"]


def test_las_listas_usan_guion_y_las_anidadas_se_sangran_dos_espacios_por_nivel():
    html = (
        "<html><body><main><ul><li>A<ul><li>A1<ul><li>A1a</li></ul></li><li>A2</li></ul></li><li>B</li></ul>"
        "<ol><li>Primero</li><li>Segundo</li></ol></main></body></html>"
    )

    assert extraer(html, BASE).texto.splitlines() == [
        "- A", "  - A1", "    - A1a", "  - A2", "- B", "- Primero", "- Segundo",
    ]


def test_una_tabla_sale_con_una_linea_por_fila_y_cada_celda_con_su_encabezado():
    html = (
        "<html><body><main><table>"
        "<tr><th>Curso</th><th>Créditos</th><th>Profesor</th></tr>"
        "<tr><td>Datos</td><td>4</td><td></td></tr>"
        "<tr><td>Estadística</td><td>3</td><td>A. Ejemplo</td></tr>"
        "</table></main></body></html>"
    )

    assert extraer(html, BASE).texto.splitlines() == [
        "Curso: Datos | Créditos: 4",  # la celda vacía no genera texto
        "Curso: Estadística | Créditos: 3 | Profesor: A. Ejemplo",
    ]


def test_una_tabla_de_una_columna_sale_como_lineas_simples_y_una_sin_encabezado_se_une_con_barras():
    uno = "<html><body><main><table><tr><td>Uno</td></tr><tr><td>Dos</td></tr></table></main></body></html>"
    assert extraer(uno, BASE).texto.splitlines() == ["Uno", "Dos"]


def test_br_es_un_salto_de_linea():
    html = "<html><body><main><p>Línea uno<br>Línea dos<br/>Línea tres</p></main></body></html>"

    assert extraer(html, BASE).texto.splitlines() == ["Línea uno", "Línea dos", "Línea tres"]


def test_sin_lineas_vacias_sobrantes_ni_duplicadas_seguidas_ni_vinetas_huerfanas():
    texto = extraer(pagina("ruidosa.html"), BASE_RUIDO).texto

    lineas = texto.splitlines()
    assert all(linea.strip() for linea in lineas)
    assert all(a != b for a, b in pairwise(lineas))
    assert "-" not in [linea.strip() for linea in lineas] and "- -" not in lineas
    assert lineas.count("- Inicio de lecciones: 9 de febrero de 2026") == 1


def test_la_limpieza_no_toca_la_primera_linea_ni_el_nombre():
    ahora = datetime(2026, 11, 21, 3, 30, tzinfo=UTC)
    documento = armar_documento(BASE, "Calendario de Ejemplo", extraer(pagina("ruidosa.html"), BASE_RUIDO).texto, ahora)

    lineas = documento.splitlines()
    assert lineas[0].startswith("Fuente: ") and lineas[1] == "Calendario de Ejemplo" and lineas[2] == ""


# ---------- codificación (US4) ----------


def test_una_pagina_en_windows_1252_conserva_tildes_y_enes():
    texto = extraer(pagina_cp1252("latin1.html"), BASE).texto

    assert "¿Cuándo empieza el semestre?" in texto and "Ñ" in texto and "información" in texto.lower()
    assert "Ã" not in texto and "�" not in texto


def test_la_codificacion_de_la_cabecera_tiene_prioridad_sobre_el_meta():
    html = '<html><head><meta charset="utf-8"></head><body><main><p>Educación y diseño</p></main></body></html>'

    texto = extraer(html.encode("cp1252"), BASE, codificacion="windows-1252").texto

    assert texto == "Educación y diseño"


def test_sin_declaracion_se_prueba_utf_8_y_luego_windows_1252():
    sin_declarar = "<html><body><main><p>Ñandú y camión</p></main></body></html>"

    assert extraer(sin_declarar.encode("utf-8"), BASE).texto == "Ñandú y camión"
    assert extraer(sin_declarar.encode("cp1252"), BASE).texto == "Ñandú y camión"


def test_el_meta_http_equiv_se_reconoce():
    html = (
        '<html><head><meta http-equiv="Content-Type" content="text/html; charset=windows-1252"></head>'
        "<body><main><p>Año académico</p></main></body></html>"
    )

    assert extraer(html.encode("cp1252"), BASE).texto == "Año académico"


def test_una_declaracion_desconocida_no_falla():
    html = '<html><head><meta charset="klingon"></head><body><main><p>Hola mundo</p></main></body></html>'

    assert extraer(html.encode("utf-8"), BASE).texto == "Hola mundo"
    assert extraer(html.encode("utf-8"), BASE, codificacion="klingon").texto == "Hola mundo"
