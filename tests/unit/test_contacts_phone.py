"""Normalización del teléfono de los contactos de WhatsApp (feature 017)."""

import pytest

from mia.contacts.phone import InvalidPhone, normalize_phone


@pytest.mark.parametrize(
    "crudo",
    ["50688887777", "+506 8888-7777", "(506) 8888 7777", " +50688887777 ", "506.8888.7777"],
)
def test_se_normaliza_a_mas_y_digitos(crudo):
    assert normalize_phone(crudo) == "+50688887777"


@pytest.mark.parametrize("crudo", ["", "   ", "123456", "1" * 16, "506abc8888", "hola", "+", "++50688887777x"])
def test_un_telefono_invalido_se_rechaza(crudo):
    with pytest.raises(InvalidPhone):
        normalize_phone(crudo)


def test_los_limites_son_de_7_a_15_digitos():
    assert normalize_phone("1234567") == "+1234567"
    assert normalize_phone("1" * 15) == "+" + "1" * 15


def test_el_mensaje_de_error_no_repite_el_telefono():
    with pytest.raises(InvalidPhone) as error:
        normalize_phone("12345")
    assert "12345" not in str(error.value)
