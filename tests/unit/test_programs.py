"""El programa de un documento (feature 013): título "<PROGRAMA>: <SECCIÓN>" a nombre natural y clave, con caché."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from mia.rag import programs
from mia.rag.programs import (
    Program,
    content_words,
    group_by_program,
    has_evidence,
    natural_name,
    parse_title,
    program_key,
    program_of_document,
)
from mia.storage.vector_store import SearchResult


@pytest.fixture(autouse=True)
def cache_limpia():
    programs.clear_cache()
    yield
    programs.clear_cache()


CIBER = "MAESTRÍA EN CIBERSEGURIDAD"
ANALITICA = "MAESTRÍA EN ANALÍTICA DE NEGOCIO (BUSINESS ANALYTICS)"


def test_nombre_natural_de_una_etiqueta_en_mayusculas():
    assert natural_name(CIBER) == "Maestría en Ciberseguridad"
    assert natural_name(ANALITICA) == "Maestría en Analítica de Negocio (Business Analytics)"


def test_las_palabras_de_enlace_quedan_en_minuscula_salvo_la_primera():
    assert natural_name("EN DEFENSA Y ATAQUE DE SISTEMAS PARA LA EMPRESA") == "En Defensa y Ataque de Sistemas para la Empresa"
    assert natural_name("LA MAESTRÍA CON ÉNFASIS A LOS DATOS POR EL TEC") == "La Maestría con Énfasis a los Datos por el Tec"


def test_una_etiqueta_con_minusculas_se_respeta_tal_cual():
    assert natural_name("Maestría en Computación (MSc)") == "Maestría en Computación (MSc)"
    assert natural_name("Doctorado en TI") == "Doctorado en TI"


def test_la_clave_quita_tildes_signos_y_palabras_vacias():
    assert program_key("Maestría en Ciberseguridad") == "ciberseguridad"
    assert program_key("Maestría en Analítica de Negocio (Business Analytics)") == "analitica negocio business analytics"
    assert program_key("MAESTRÍA EN CIBERSEGURIDAD") == program_key("maestria en ciberseguridad")
    assert program_key("Maestría") == ""


def test_el_titulo_es_la_etiqueta_antes_de_los_dos_puntos_de_la_primera_linea():
    assert parse_title("MAESTRÍA EN CIBERSEGURIDAD: ADMISIÓN\nUnidad de Posgrados...") == CIBER
    assert parse_title("\n\n  MAESTRÍA EN CIBERSEGURIDAD: PLAN DE ESTUDIOS \nresto") == CIBER
    assert parse_title(f"{ANALITICA}: PRESENTACIÓN\nÁrea...") == ANALITICA


@pytest.mark.parametrize(
    "texto",
    [
        "",
        "   \n  ",
        "Un documento sin dos puntos en la primera línea\nPero: aquí sí en la segunda",
        ": sin etiqueta",
        "AB: etiqueta demasiado corta",
        f"{'X' * 121}: etiqueta demasiado larga",
        "https://www.tec.ac.cr: un enlace no es un programa",
        "1234 5678: solo números",
    ],
)
def test_sin_la_forma_del_titulo_el_documento_no_tiene_programa(texto):
    assert parse_title(texto) is None


def _almacen(textos: dict[str, str | None]):
    """Un almacén cuyo fragmento 0 de cada documento es el texto dado (None: el documento no tiene fragmentos)."""
    almacen = MagicMock()

    def get_chunks(document_id, indexes):
        texto = textos.get(document_id)
        if texto is None:
            return []
        return [SearchResult(chunk_id="c0", document_id=document_id, domain="d", text=texto, score=0.0, chunk_index=0)]

    almacen.get_chunks.side_effect = get_chunks
    return almacen


def test_el_programa_de_un_documento_sale_del_fragmento_cero():
    almacen = _almacen({"d1": "MAESTRÍA EN CIBERSEGURIDAD: ADMISIÓN\nresto del texto"})

    assert program_of_document(almacen, "d1") == Program("Maestría en Ciberseguridad", "ciberseguridad")
    almacen.get_chunks.assert_called_once_with("d1", [0])


def test_se_lee_el_almacen_una_sola_vez_por_documento():
    almacen = _almacen({"d1": "MAESTRÍA EN CIBERSEGURIDAD: ADMISIÓN\nresto", "d2": "Sin título con la forma\nresto"})

    for _ in range(3):
        program_of_document(almacen, "d1")
        assert program_of_document(almacen, "d2") is None

    assert almacen.get_chunks.call_count == 2  # una lectura por documento, también para los que no tienen programa


def test_un_documento_sin_fragmentos_o_un_fallo_del_almacen_no_rompen_ni_se_guardan_en_la_cache():
    almacen = _almacen({"nuevo": None})
    assert program_of_document(almacen, "nuevo") is None
    almacen.get_chunks.side_effect = RuntimeError("Qdrant no responde")
    assert program_of_document(almacen, "d1") is None

    # Cuando el documento ya tiene fragmentos (o el almacén vuelve) se lee de nuevo.
    almacen.get_chunks.side_effect = None
    almacen.get_chunks.return_value = [
        SimpleNamespace(text="MAESTRÍA EN CIBERSEGURIDAD: PLAN DE ESTUDIOS\nresto")
    ]
    assert program_of_document(almacen, "nuevo") == Program("Maestría en Ciberseguridad", "ciberseguridad")


def _resultado(document_id, score):
    return SearchResult(chunk_id=f"{document_id}-{score}", document_id=document_id, domain="d", text="x", score=score)


def test_agrupa_por_programa_sin_contar_los_sin_programa_y_ordena_por_el_mejor_puntaje():
    almacen = _almacen(
        {
            "ana-presentacion": f"{ANALITICA}: PRESENTACIÓN\n...",
            "ana-admision": f"{ANALITICA}: ADMISIÓN\n...",
            "ciber-admision": f"{CIBER}: ADMISIÓN\n...",
            "suelto": "Sin la forma del título\n...",
        }
    )
    resultados = [
        _resultado("ciber-admision", 0.71),
        _resultado("suelto", 0.70),
        _resultado("ana-admision", 0.66),
        _resultado("ana-presentacion", 0.65),
        _resultado("ana-admision", 0.40),
    ]

    candidatos = group_by_program(resultados, almacen, min_score=0.5, max_programs=5)

    assert [p.name for p in candidatos] == ["Maestría en Ciberseguridad", "Maestría en Analítica de Negocio (Business Analytics)"]


def test_el_puntaje_minimo_y_el_maximo_de_programas_recortan_la_lista():
    almacen = _almacen({f"d{i}": f"MAESTRÍA EN PROGRAMA {i}: ADMISIÓN\n..." for i in range(6)})
    resultados = [_resultado(f"d{i}", 0.9 - i * 0.05) for i in range(6)]  # 0,90 0,85 0,80 0,75 0,70 0,65

    assert [p.key for p in group_by_program(resultados, almacen, min_score=0.78, max_programs=5)] == ["programa 0", "programa 1", "programa 2"]
    assert len(group_by_program(resultados, almacen, min_score=0.0, max_programs=2)) == 2
    assert group_by_program([], almacen, min_score=0.0, max_programs=5) == []


# --- Evidencia léxica (calibración del 27 de octubre de 2026: el puntaje solo no distingue una pregunta ambigua de una
# sin relación) ----------------------------------------------------------------------------------------------------


def test_las_palabras_con_contenido_quitan_interrogativos_vacias_y_genericas():
    assert content_words("¿Cuándo empiezan las lecciones?") == ["empiezan", "lecciones"]
    assert content_words("¿Cómo me postulo a la maestría?") == ["postulo"]
    assert content_words("¿Cuánto cuesta la luna?") == ["cuesta", "luna"]
    assert content_words("¿Qué es esto?") == []
    assert content_words("") == []


def test_las_palabras_con_contenido_van_sin_tildes_en_minusculas_y_sin_repetir():
    assert content_words("¿Cuál es la MATRÍCULA? ¿La matrícula anual?") == ["matricula", "anual"]


def test_hay_evidencia_si_una_palabra_aparece_al_inicio_de_una_palabra_del_texto():
    assert has_evidence("Inicio de lecciones: 5 de octubre de 2026", ["empiezan", "lecciones"])
    assert has_evidence("Para postularse a la maestría...", ["postulo"])  # inicio de palabra con los primeros 6 caracteres
    assert has_evidence("Fecha de MATRÍCULA", ["matricula"])  # sin tildes ni mayúsculas
    assert not has_evidence("Inicio de lecciones", ["luna"])
    assert not has_evidence("Inversión: ₡61 000 por crédito", ["cuesta"])
    assert not has_evidence("una columna de datos", ["luna"])  # no es inicio de palabra
    assert not has_evidence("cualquier texto", [])


def test_con_palabras_de_evidencia_solo_cuentan_los_fragmentos_que_las_traen():
    almacen = _almacen({"ciber": f"{CIBER}: ADMISIÓN\n...", "ana": f"{ANALITICA}: ADMISIÓN\n..."})
    resultados = [
        SearchResult(chunk_id="a", document_id="ciber", domain="d", text="Inicio de lecciones: I trimestre", score=0.80),
        SearchResult(chunk_id="b", document_id="ana", domain="d", text="Plan de estudios con 8 bloques", score=0.79),
    ]

    assert [p.key for p in group_by_program(resultados, almacen, 0.5, 5, evidence_words=["lecciones"])] == ["ciberseguridad"]
    assert len(group_by_program(resultados, almacen, 0.5, 5)) == 2  # sin palabras de evidencia, como antes
    assert group_by_program(resultados, almacen, 0.5, 5, evidence_words=[]) == []  # sin palabras no hay evidencia posible
