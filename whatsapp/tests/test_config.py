"""Configuración del servicio: variables obligatorias, rangos y textos por defecto."""

import re

import pytest
from pydantic import ValidationError

from mia_whatsapp.config import (
    DEFAULT_TEXT_GREETING,
    DEFAULT_TEXT_NO_INFO,
    DEFAULT_TEXT_NOT_TEXT,
    DEFAULT_TEXT_RATE_LIMIT,
    DEFAULT_TEXT_TOO_LONG,
    DEFAULT_TEXT_UNAVAILABLE,
    Settings,
    contact_warnings,
)

OBLIGATORIAS = {
    "mia_api_url": "https://mia.example.com",
    "bot_service_key": "clave-de-servicio",
    "kapso_api_key": "clave-de-kapso",
    "kapso_webhook_secret": "secreto-del-webhook",
}


def hacer(**cambios) -> Settings:
    """Configuración de prueba: nunca lee el .env de quien corre las pruebas."""
    return Settings(_env_file=None, **{**OBLIGATORIAS, **cambios})


@pytest.mark.parametrize("variable", sorted(OBLIGATORIAS))
def test_sin_una_variable_obligatoria_no_arranca_y_el_mensaje_la_nombra(variable, monkeypatch):
    for nombre in OBLIGATORIAS:
        monkeypatch.delenv(nombre.upper(), raising=False)
    datos = {k: v for k, v in OBLIGATORIAS.items() if k != variable}
    with pytest.raises(ValidationError, match=variable):
        Settings(_env_file=None, **datos)


@pytest.mark.parametrize("variable", sorted(OBLIGATORIAS))
def test_una_variable_obligatoria_vacia_tampoco_deja_arrancar(variable):
    with pytest.raises(ValidationError, match=variable):
        hacer(**{variable: ""})


def test_valores_por_defecto():
    base = hacer()
    assert base.kapso_api_url == "https://api.kapso.ai/meta/whatsapp/v24.0"
    assert (base.bot_max_messages_per_hour, base.bot_max_messages_per_day) == (10, 30)
    assert (base.bot_max_question_chars, base.bot_max_concurrent_queries, base.bot_queue_size) == (500, 5, 20)
    assert (base.bot_max_images, base.bot_greeting_hours, base.bot_query_timeout_s) == (1, 24, 30)
    assert (base.bot_kapso_rate_per_min, base.bot_seen_ttl_hours) == (90, 24)
    assert base.bot_text_greeting == DEFAULT_TEXT_GREETING and base.bot_text_no_info == DEFAULT_TEXT_NO_INFO


@pytest.mark.parametrize(
    ("campo", "valor"),
    [
        ("bot_max_messages_per_hour", 0),
        ("bot_max_messages_per_hour", 1001),
        ("bot_max_messages_per_day", 0),
        ("bot_max_question_chars", 9),
        ("bot_max_question_chars", 2001),
        ("bot_max_concurrent_queries", 0),
        ("bot_queue_size", -1),
        ("bot_max_images", 11),
        ("bot_greeting_hours", 0),
        ("bot_query_timeout_s", 121),
        ("bot_kapso_rate_per_min", 101),
        ("bot_seen_ttl_hours", 0),
    ],
)
def test_un_valor_fuera_de_rango_no_deja_arrancar_y_el_mensaje_nombra_la_variable(campo, valor):
    with pytest.raises(ValidationError, match=campo):
        hacer(**{campo: valor})


def test_las_variables_se_leen_del_entorno(monkeypatch):
    for nombre, valor in OBLIGATORIAS.items():
        monkeypatch.setenv(nombre.upper(), valor)
    monkeypatch.setenv("BOT_QUEUE_SIZE", "3")
    monkeypatch.setenv("BOT_TEXT_NO_INFO", "Sin datos.")
    configuracion = Settings(_env_file=None)
    assert configuracion.bot_queue_size == 3 and configuracion.bot_text_no_info == "Sin datos."


def test_la_direccion_de_la_api_se_recorta_sin_barra_final():
    assert hacer(mia_api_url="https://mia.example.com/").mia_api_url == "https://mia.example.com"
    assert hacer(mia_api_url=" https://mia.example.com// ").mia_api_url == "https://mia.example.com"
    assert hacer(kapso_api_url="http://localhost:9000/").kapso_api_url == "http://localhost:9000"


TEXTOS = {
    "saludo": DEFAULT_TEXT_GREETING,
    "sin información": DEFAULT_TEXT_NO_INFO,
    "no disponible": DEFAULT_TEXT_UNAVAILABLE,
    "límite por persona": DEFAULT_TEXT_RATE_LIMIT,
    "no es texto": DEFAULT_TEXT_NOT_TEXT,
    "pregunta larga": DEFAULT_TEXT_TOO_LONG,
}


@pytest.mark.parametrize(("nombre", "texto"), sorted(TEXTOS.items()))
def test_los_textos_por_defecto_no_dan_el_contacto_del_programa(nombre, texto):
    """FR-017: ni correos, ni teléfonos, ni enlaces."""
    assert "@" not in texto and "http" not in texto.lower() and "www." not in texto.lower()
    assert not re.search(r"\d(?:[\s().-]*\d){6,}", texto), nombre


def test_el_saludo_dice_lo_que_pide_el_requisito():
    texto = DEFAULT_TEXT_GREETING.lower()
    for fragmento in ("asistente automático", "documentos oficiales", "whatsapp", "kapso", "datos personales"):
        assert fragmento in texto


# --- Resguardo del contacto del programa (FR-017) --------------------------------------------------------------


def test_con_los_textos_por_defecto_no_hay_avisos_de_contacto():
    assert contact_warnings(hacer()) == []


@pytest.mark.parametrize(
    "texto",
    [
        "Escribe a admision@tec.ac.cr",
        "Visita https://www.tec.ac.cr/posgrados",
        "Visita HTTP://sitio.cr",
        "Llama al 2550 2000",
        "Llama al +506 2550-2000",
        "Llama al (506) 2550 2000",
        "Whatsapp 50688887777",
    ],
)
def test_un_texto_cambiado_con_correo_enlace_o_telefono_se_reporta_por_el_nombre_de_su_variable(texto):
    assert contact_warnings(hacer(bot_text_no_info=texto)) == ["BOT_TEXT_NO_INFO"]


def test_se_reportan_todos_los_textos_que_tengan_contacto():
    avisos = contact_warnings(hacer(bot_text_greeting="Escribe a a@b.cr", bot_text_too_long="Llama al 25502000"))
    assert avisos == ["BOT_TEXT_GREETING", "BOT_TEXT_TOO_LONG"]


def test_unos_pocos_digitos_no_son_un_telefono():
    assert contact_warnings(hacer(bot_text_no_info="Son 3 pasos de los 12 del trámite, del 2026.")) == []
