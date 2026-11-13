"""Reglas de texto de los datos de contacto (feature 017, research R4): negativa, "para qué", correo, nombre, borrado y
reapertura. Todas son deterministas, sin modelo de lenguaje, y nunca lanzan."""

import pytest

from mia_whatsapp.contacts import (
    EXAMPLE_EMAIL,
    Reading,
    mask_email,
    read_message,
    render_retry,
    render_thanks,
)


def leer(texto: str, estado: str = "invitada") -> Reading:
    return read_message(texto, estado)


# --- negativa: coincidencia EXACTA con una lista corta de frases ---


@pytest.mark.parametrize(
    "texto",
    ["no", "No", "NO.", "No gracias", "no, gracias", "omitir", "Omitir", "ahora no", "por ahora no", "prefiero no",
     "no quiero", "no por ahora", "no gracias por ahora", "paso", "saltar", "cancelar", "  no  ", "¡No, gracias!"],
)
def test_es_negativa(texto):
    assert leer(texto).kind == "decline"


@pytest.mark.parametrize(
    "texto",
    [
        "no encuentro la matrícula",
        "no sé cuándo abren",
        "no tengo claro el costo",
        "paso a paso para inscribirme",
        "no gracias, pero cuánto cuesta",
        "cancelar la matrícula",
    ],
)
def test_lo_que_solo_empieza_como_una_negativa_es_una_pregunta(texto):
    assert leer(texto).kind == "question"


# --- "para qué" ---


@pytest.mark.parametrize(
    "texto",
    ["¿para qué piden mi correo?", "para que quieren mis datos", "¿por qué piden el correo?", "quién ve mis datos",
     "¿qué hacen con mi número?", "privacidad de los datos"],
)
def test_es_para_que(texto):
    assert leer(texto).kind == "why"


@pytest.mark.parametrize(
    "texto",
    [
        "¿para qué sirve la maestría y cuál es el nombre del programa?",  # largo y sin datos, correo ni número
        "para qué sirve la maestría",
        "¿por qué es tan caro el posgrado?",
    ],
)
def test_una_pregunta_que_contiene_para_que_pero_no_habla_de_datos_no_es_para_que(texto):
    assert leer(texto).kind == "question"


def test_para_que_solo_en_mensajes_cortos():
    largo = "para qué necesitan mis datos y mi correo si yo solo quiero saber cuánto cuesta el programa de maestría"
    assert leer(largo).kind == "question"


# --- correo ---


@pytest.mark.parametrize(
    ("texto", "nombre", "correo"),
    [
        ("ana@correo.com", None, "ana@correo.com"),
        ("Ana@Correo.COM", None, "ana@correo.com"),
        ("Ana Pérez ana@correo.com", "Ana Pérez", "ana@correo.com"),
        ("ana@correo.com Ana Pérez", "Ana Pérez", "ana@correo.com"),
        ("soy Ana y mi correo es ana@correo.com", "Ana", "ana@correo.com"),
        ("Me llamo ana pérez, mi correo es ana.perez@correo.cr.", "ana pérez", "ana.perez@correo.cr"),
        ("mi correo es ana@correo.com", None, "ana@correo.com"),
        ("ana perez ana@correo.com", "ana perez", "ana@correo.com"),
        ("Hola, soy Ana Solís, ana@correo.com", "Ana Solís", "ana@correo.com"),
    ],
)
def test_correo_valido_solo_o_con_nombre(texto, nombre, correo):
    lectura = leer(texto)
    assert (lectura.kind, lectura.name, lectura.email) == ("provided", nombre, correo)


@pytest.mark.parametrize("texto", ["ana@", "ana@correo", "mi correo es ana arroba correo", "@correo.com", "ana@@correo.com"])
def test_correo_invalido(texto):
    lectura = leer(texto)
    assert lectura.kind == "bad_email" and lectura.email is None


def test_correo_invalido_con_nombre_conserva_el_nombre():
    lectura = leer("Soy Ana Pérez, mi correo es ana@")
    assert (lectura.kind, lectura.name) == ("bad_email", "Ana Pérez")


def test_un_correo_de_mas_de_254_caracteres_es_invalido():
    assert leer("a" * 250 + "@correo.com").kind == "bad_email"


# --- nombre ---


@pytest.mark.parametrize(
    ("texto", "nombre"),
    [
        ("Ana Pérez", "Ana Pérez"),
        ("María de los Ángeles Solís", "María de los Ángeles Solís"),
        ("Juan Carlos Vargas Mora", "Juan Carlos Vargas Mora"),
        ("soy Ana", "Ana"),
        ("Soy Admisión Pérez", "Admisión Pérez"),
        ("me llamo ana", "ana"),
        ("mi nombre es luis mora", "luis mora"),
        ("J. Pérez", "J. Pérez"),
        ("O'Connor Díaz", "O'Connor Díaz"),
    ],
)
def test_es_un_nombre(texto, nombre):
    lectura = leer(texto)
    assert (lectura.kind, lectura.name, lectura.email) == ("provided", nombre, None)


@pytest.mark.parametrize(
    "texto",
    [
        "Admisión",  # una palabra sin introductor
        "requisitos de admisión",  # minúsculas
        "Requisitos de Admisión",  # palabras de dominio
        "Maestría Computación",
        "Costos Matrícula",
        "Cuánto cuesta",  # no todas con mayúscula
        "¿Cuánto Cuesta?",  # con ?
        "Ana Pérez 2",  # con dígitos
        "Hola",
        "gracias",
        "ok",
        "sí",
        "Juan Carlos Vargas Mora Solís",  # más de 4 palabras
        "soy estudiante de computación",  # "soy" exige mayúscula inicial
        "soy estudiante de ingeniería y quiero saber el costo",
    ],
)
def test_lo_que_no_es_un_nombre_es_una_pregunta(texto):
    assert leer(texto).kind == "question"


def test_el_nombre_se_recorta_a_80_caracteres():
    largo = "me llamo " + " ".join(["Abcdefghijklmnopqrstu"] * 4)
    lectura = leer(largo)
    assert lectura.kind == "provided" and len(lectura.name) <= 80


# --- borrado y reapertura (en cualquier estado, sin distinguir mayúsculas ni tildes) ---


@pytest.mark.parametrize(
    "texto",
    ["borrar mis datos", "Borrar mis datos", "BORRAR MIS DATOS", "Elimina mi correo", "quiero que borren mis datos",
     "elimina mi información", "quitar mi nombre", "borra mi número"],
)
@pytest.mark.parametrize("estado", ["pendiente", "invitada", "entrego", "declino"])
def test_frases_de_borrado_en_cualquier_estado(texto, estado):
    assert leer(texto, estado).kind == "erase"


@pytest.mark.parametrize(
    "texto",
    ["quiero dejar mis datos", "Quiero dejar mis datos", "actualizar mis datos", "quiero dejar mi correo", "cambiar mi correo"],
)
@pytest.mark.parametrize("estado", ["pendiente", "invitada", "entrego", "declino"])
def test_frases_de_reapertura_en_cualquier_estado(texto, estado):
    assert leer(texto, estado).kind == "reopen"


def test_el_borrado_gana_sobre_la_reapertura():
    assert leer("quiero borrar mis datos y dejar otros").kind == "erase"


def test_una_pregunta_larga_con_las_mismas_palabras_no_borra_nada():
    texto = "Quisiera saber si en el programa de maestría puedo borrar mis datos del sistema de matrícula antes de pagar"
    assert leer(texto).kind == "question"


# --- fuera de la invitación solo valen las frases de control ---


@pytest.mark.parametrize("estado", ["pendiente", "entrego", "declino"])
def test_sin_invitacion_abierta_lo_demas_es_una_pregunta(estado):
    for texto in ("no", "Ana Pérez ana@correo.com", "para qué piden mi correo", "ana@correo.com"):
        assert leer(texto, estado).kind == "question"


# --- textos ---


def test_enmascarado_del_correo():
    assert mask_email("ana@correo.com") == "a**@correo.com"
    assert mask_email("x@y.cr") == "x**@y.cr"


def test_lo_que_se_confirma_incluye_el_nombre_y_el_correo_enmascarado():
    plantilla = "Listo, guardé {saved}."
    assert render_thanks(plantilla, "Ana Pérez", "ana@correo.com") == (
        "Listo, guardé tu nombre (Ana Pérez) y tu correo (a**@correo.com)."
    )
    assert render_thanks(plantilla, None, "ana@correo.com") == "Listo, guardé tu correo (a**@correo.com)."
    assert render_thanks(plantilla, "Ana", None) == "Listo, guardé tu nombre (Ana)."


def test_el_reintento_lleva_el_ejemplo():
    assert EXAMPLE_EMAIL in render_retry("Por ejemplo: {example}.")


def test_nunca_lanza_con_entradas_raras():
    for texto in ("", "   ", "\n\n", "@", "¿?", "🙂🙂", "a" * 5000, "\x00"):
        for estado in ("pendiente", "invitada", "entrego", "declino"):
            assert isinstance(leer(texto, estado), Reading)
