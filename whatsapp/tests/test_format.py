"""Formato del texto de WhatsApp: de Markdown a WhatsApp, fuentes breves, saludo y partición de mensajes largos."""

import re

import pytest

from mia_whatsapp.format import compose_text, split_message, to_whatsapp

# --- to_whatsapp -----------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("**negrita**", "*negrita*"),
        ("__negrita__", "*negrita*"),
        ("una **palabra** en medio", "una *palabra* en medio"),
        ("*cursiva*", "_cursiva_"),
        ("_cursiva_", "_cursiva_"),
        ("~~tachado~~", "~tachado~"),
        ("**negrita** y *cursiva* juntas", "*negrita* y _cursiva_ juntas"),
        ("`código`", "`código`"),
    ],
)
def test_el_formato_en_linea_pasa_al_de_whatsapp(entrada, esperado):
    assert to_whatsapp(entrada) == esperado


@pytest.mark.parametrize(
    ("entrada", "esperado"),
    [
        ("# Título", "*Título*"),
        ("## Subtítulo con **negrita**", "*Subtítulo con negrita*"),
        ("###### Seis", "*Seis*"),
        ("## Con almohadillas al final ##", "*Con almohadillas al final*"),
    ],
)
def test_los_encabezados_pasan_a_una_linea_en_negrita(entrada, esperado):
    assert to_whatsapp(entrada) == esperado


def test_los_enlaces_pasan_a_texto_y_direccion():
    assert to_whatsapp("[la guía](https://ejemplo.cr/guia)") == "la guía (https://ejemplo.cr/guia)"
    assert to_whatsapp("[https://ejemplo.cr](https://ejemplo.cr)") == "https://ejemplo.cr"
    assert to_whatsapp("![el horario](https://ejemplo.cr/h.png)") == "el horario (https://ejemplo.cr/h.png)"


def test_las_listas_con_asterisco_o_mas_pasan_a_guion_y_las_numeradas_no_cambian():
    entrada = "* uno\n+ dos\n- tres\n  * anidado\n1. primero\n2. segundo"
    assert to_whatsapp(entrada) == "- uno\n- dos\n- tres\n  - anidado\n1. primero\n2. segundo"


def test_un_asterisco_de_lista_no_se_toma_por_cursiva():
    assert to_whatsapp("* **Requisito:** título\n* *Otro* dato") == "- *Requisito:* título\n- _Otro_ dato"


def test_las_tablas_pasan_a_filas_de_texto():
    entrada = "| Fecha | Actividad |\n|---|---|\n| 3 de agosto | Matrícula |\n| 7 de agosto | Cierre |"
    assert to_whatsapp(entrada) == "*Fecha - Actividad*\n3 de agosto - Matrícula\n7 de agosto - Cierre"


def test_las_reglas_horizontales_se_quitan():
    assert to_whatsapp("Antes\n\n---\n\nDespués") == "Antes\n\nDespués"
    assert to_whatsapp("Antes\n\n***\n\nDespués") == "Antes\n\nDespués"


def test_un_bloque_de_codigo_queda_como_esta():
    entrada = "Mira:\n```\n**no tocar** # esto\n```\nFin **negrita**"
    assert to_whatsapp(entrada) == "Mira:\n```\n**no tocar** # esto\n```\nFin *negrita*"


def test_no_quedan_marcas_de_markdown_en_una_respuesta_tipica():
    markdown = (
        "## Requisitos de admisión\n\n**Documentos:**\n\n* Título universitario\n* Currículum *actualizado*\n\n"
        "Más información en [el sitio](https://ejemplo.cr).\n\n---\n\n| A | B |\n|---|---|\n| 1 | 2 |"
    )
    resultado = to_whatsapp(markdown)
    assert "**" not in resultado and "##" not in resultado and "](" not in resultado and "---" not in resultado
    assert not re.search(r"^\s*\*\s", resultado, re.MULTILINE)


def test_las_lineas_en_blanco_seguidas_se_reducen_y_se_recorta_el_texto():
    assert to_whatsapp("\n\nUno\n\n\n\n\nDos\n\n") == "Uno\n\nDos"


def test_el_texto_vacio_da_vacio():
    assert to_whatsapp("") == ""
    assert to_whatsapp("   \n  ") == ""


# --- compose_text ----------------------------------------------------------------------------------------------


def test_compone_saludo_respuesta_y_fuentes_en_un_solo_mensaje():
    texto = compose_text("La matrícula es del 3 al 7 de agosto.", ["horario_matricula.pdf"], "Hola, soy un asistente.")
    assert texto == "Hola, soy un asistente.\n\nLa matrícula es del 3 al 7 de agosto.\n\nFuentes: horario_matricula.pdf"


def test_sin_saludo_no_lo_antepone():
    assert compose_text("Respuesta.", ["a.pdf"], None) == "Respuesta.\n\nFuentes: a.pdf"
    assert compose_text("Respuesta.", ["a.pdf"], "") == "Respuesta.\n\nFuentes: a.pdf"


def test_sin_fuentes_no_agrega_la_linea():
    assert compose_text("Respuesta.", [], None) == "Respuesta."


def test_las_fuentes_no_se_repiten_y_se_limitan_a_tres():
    assert compose_text("R.", ["a.pdf", "b.pdf", "a.pdf"], None) == "R.\n\nFuentes: a.pdf, b.pdf"
    assert compose_text("R.", ["a.pdf", "b.pdf", "c.pdf"], None) == "R.\n\nFuentes: a.pdf, b.pdf, c.pdf"
    assert compose_text("R.", ["a.pdf", "b.pdf", "c.pdf", "d.pdf", "e.pdf"], None) == (
        "R.\n\nFuentes: a.pdf, b.pdf, c.pdf y 2 más"
    )
    assert compose_text("R.", [f"{x}.pdf" for x in "abcd"], None).endswith("y 1 más")


def test_la_respuesta_se_convierte_al_formato_de_whatsapp_dentro_del_mensaje():
    texto = compose_text("**Importante:** lleva *cédula*.", [], "Hola.")
    assert texto == "Hola.\n\n*Importante:* lleva _cédula_."


# --- split_message ---------------------------------------------------------------------------------------------


def test_un_texto_corto_no_se_parte():
    assert split_message("Hola") == ["Hola"]
    assert split_message("x" * 4000) == ["x" * 4000]


def test_un_texto_largo_se_parte_por_parrafos_en_orden_y_cada_parte_cabe():
    parrafos = [f"Párrafo {i}. " + "palabra " * 120 for i in range(10)]  # ~1.000 caracteres cada uno
    partes = split_message("\n\n".join(parrafos), limit=4000)

    assert len(partes) > 1
    assert all(len(p) <= 4000 for p in partes)
    # Sin perder nada y en orden: al unir las partes salen los mismos párrafos.
    assert "\n\n".join(partes).split("\n\n") == [p.strip() for p in parrafos]


def test_un_parrafo_mas_largo_que_el_limite_se_parte_por_oraciones():
    oraciones = [f"Oración número {i} con algo de texto para ocupar espacio." for i in range(200)]
    texto = " ".join(oraciones)
    partes = split_message(texto, limit=500)

    assert all(len(p) <= 500 for p in partes) and len(partes) > 1
    assert " ".join(partes) == texto
    # Cada parte termina en el final de una oración.
    assert all(p.endswith(".") for p in partes)


def test_una_lista_larga_se_parte_por_lineas():
    lineas = [f"- elemento {i} de la lista de requisitos" for i in range(300)]
    partes = split_message("\n".join(lineas), limit=600)

    assert all(len(p) <= 600 for p in partes)
    assert "\n".join(partes) == "\n".join(lineas)


def test_sin_oraciones_se_parte_por_palabras_sin_cortar_ninguna():
    texto = " ".join(["supercalifragilistico"] * 100)
    partes = split_message(texto, limit=100)

    assert all(len(p) <= 100 for p in partes)
    assert " ".join(partes) == texto


def test_una_palabra_mas_larga_que_el_limite_se_corta_como_ultimo_recurso():
    partes = split_message("x" * 250, limit=100)
    assert [len(p) for p in partes] == [100, 100, 50]
    assert "".join(partes) == "x" * 250


def test_no_hay_partes_vacias():
    partes = split_message("\n\n".join(["a" * 90] * 5), limit=100)
    assert all(p for p in partes)
