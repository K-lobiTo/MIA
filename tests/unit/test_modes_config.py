import pytest
from pydantic import ValidationError

from mia.config import Settings, settings
from mia.rag.llm import NO_INFO_MARKER, RAG_SYSTEM_PROMPT, REASONING_SYSTEM_PROMPT
from mia.rag.modes import mode_config


def test_el_modo_literal_usa_la_instruccion_y_los_resultados_de_siempre(modes_config):
    config = mode_config("literal")

    assert config.instructions == RAG_SYSTEM_PROMPT
    assert config.search_limit == settings.query_search_limit


def test_el_modo_con_razonamiento_tiene_su_instruccion_y_mas_resultados(modes_config):
    config = mode_config("razonamiento")

    assert config.instructions == REASONING_SYSTEM_PROMPT
    assert config.search_limit == settings.query_search_limit_razonamiento
    assert settings.query_search_limit_razonamiento > settings.query_search_limit


def test_la_instruccion_con_razonamiento_pide_dos_partes_y_prohibe_el_conocimiento_externo():
    texto = REASONING_SYSTEM_PROMPT

    assert NO_INFO_MARKER in texto
    assert "Lo que dicen los documentos" in texto and "**Conclusión**" in texto
    assert "conocimiento externo" in texto
    assert "calcular" in texto


def test_la_instruccion_con_razonamiento_no_obliga_a_calcular():
    # La conclusión es la respuesta; la operación se muestra solo si hizo falta combinar datos.
    texto = REASONING_SYSTEM_PROMPT

    assert "Cálculo o conclusión" not in texto
    assert "resumir" in texto and "no inventes una operación" in texto


@pytest.mark.parametrize("campo", ["query_search_limit", "query_search_limit_razonamiento"])
@pytest.mark.parametrize("valor", [0, 51])
def test_el_limite_de_resultados_debe_estar_entre_1_y_50(campo, valor):
    with pytest.raises(ValidationError):
        Settings(**{campo: valor})


def test_el_limite_de_resultados_acepta_los_extremos():
    assert Settings(query_search_limit_razonamiento=1).query_search_limit_razonamiento == 1
    assert Settings(query_search_limit_razonamiento=50).query_search_limit_razonamiento == 50
