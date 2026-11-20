"""Ajustes de la lectura de una página web (feature 022)."""

import pytest
from pydantic import ValidationError

from mia.config import Settings


def test_valores_por_defecto():
    ajustes = Settings(_env_file=None)

    assert ajustes.web_fetch_timeout_seconds == 15
    assert ajustes.web_max_page_kb == 2048
    assert ajustes.web_max_redirects == 5
    assert ajustes.web_min_text_chars == 300
    assert ajustes.web_user_agent.startswith("MIA-Lector/")
    assert "@" not in ajustes.web_user_agent  # sin correos ni datos personales


@pytest.mark.parametrize(
    "variable,valor",
    [
        ("WEB_FETCH_TIMEOUT_SECONDS", "0"),
        ("WEB_FETCH_TIMEOUT_SECONDS", "61"),
        ("WEB_MAX_PAGE_KB", "10"),
        ("WEB_MAX_PAGE_KB", "20000"),
        ("WEB_MAX_REDIRECTS", "-1"),
        ("WEB_MAX_REDIRECTS", "11"),
        ("WEB_MIN_TEXT_CHARS", "10"),
        ("WEB_MIN_TEXT_CHARS", "6000"),
    ],
)
def test_un_valor_fuera_de_rango_no_valida(monkeypatch, variable, valor):
    monkeypatch.setenv(variable, valor)

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_los_valores_del_entorno_se_leen(monkeypatch):
    monkeypatch.setenv("WEB_FETCH_TIMEOUT_SECONDS", "30")
    monkeypatch.setenv("WEB_MIN_TEXT_CHARS", "100")

    ajustes = Settings(_env_file=None)

    assert ajustes.web_fetch_timeout_seconds == 30
    assert ajustes.web_min_text_chars == 100
