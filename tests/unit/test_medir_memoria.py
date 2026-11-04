"""La parte pura de `scripts/medir_memoria.py` (feature 014): carga de casos, aciertos y veredicto."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

from mia.config import settings

RAIZ_REPO = Path(__file__).resolve().parents[2]


def _cargar():
    spec = importlib.util.spec_from_file_location(
        "medir_memoria", RAIZ_REPO / "scripts" / "medir_memoria.py"
    )
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


script = _cargar()


def _resultado(documento, puntaje=0.9):
    return SimpleNamespace(document_id=documento, score=puntaje)


def test_los_casos_del_repositorio_se_cargan():
    casos = script.cargar_casos()

    assert len(casos) >= 15 and {c["categoria"] for c in casos} >= {
        "tema_anterior",
        "cambio_de_tema",
    }


def test_acierta_si_un_fragmento_sobre_el_umbral_es_de_un_documento_esperado():
    resultados = [
        _resultado("otro", 0.95),
        _resultado("Maestria_Admision", 0.9),
        _resultado("Maestria_Plan", 0.5),
    ]

    assert script.acierta(resultados, ["Maestria_Admision.txt"], 0.82, 5)
    assert not script.acierta(resultados, ["Maestria_Plan.txt"], 0.82, 5)  # bajo el umbral
    assert not script.acierta(
        resultados, ["Maestria_Admision.txt"], 0.82, 1
    )  # fuera de los mejores
    assert not script.acierta([], ["Maestria_Admision.txt"], 0.82, 5)


class AlmacenSimulado:
    """Devuelve el documento del programa que nombra el texto de búsqueda (como lo haría una búsqueda por significado)."""

    def buscar(self, texto):
        bajo = texto.lower()
        if "analítica" in bajo or "analitica" in bajo:
            return [_resultado("Maestria_en_Analitica_de_Negocio_Plan_de_Estudio")]
        if "ciberseguridad" in bajo:
            return [_resultado("Maestria_en_Ciberseguridad_Presentacion")]
        return []


def _medir(estrategia, monkeypatch):
    monkeypatch.setattr(settings, "history_reformulation", "rules")
    casos = script.cargar_casos()
    almacen = AlmacenSimulado()
    return script.resumir(
        estrategia, [script.medir_caso(c, estrategia, almacen.buscar, 0.82, 5) for c in casos]
    )


def test_sin_reformular_los_seguimientos_no_encuentran_y_con_reglas_si(monkeypatch):
    apagada = _medir("off", monkeypatch)
    reglas = _medir("rules", monkeypatch)

    assert apagada.tasa(("tema_anterior",)) < reglas.tasa(("tema_anterior",))
    assert reglas.por_categoria["tema_anterior"][0] >= 3
    assert apagada.falsos_seguimientos == []  # sin reformular no hay falsos seguimientos


def test_los_casos_de_calculo_no_se_cuentan_en_la_busqueda(monkeypatch):
    resumen = _medir("rules", monkeypatch)

    assert "calculo_en_razonamiento" not in resumen.por_categoria


def test_el_veredicto_falla_bajo_el_80_por_ciento_y_con_falsos_seguimientos():
    resumen = script.Resumen("rules")
    resumen.por_categoria["tema_anterior"] = [3, 4]
    resumen.por_categoria["pronombre"] = [2, 3]
    assert "71%" in script.veredicto(resumen)[0]  # 5 de 7: falla
    resumen.por_categoria["tema_anterior"] = [4, 4]
    resumen.por_categoria["pronombre"] = [3, 3]
    assert script.veredicto(resumen) == []
    resumen.falsos_seguimientos = ["CT1"]
    assert "CT1" in script.veredicto(resumen)[0]


@pytest.mark.parametrize(
    ("texto", "esperado"),
    [
        ("Suman 21 créditos.", True),
        ("Son 21", True),
        ("El código MC2101 no cuenta", False),
        ("Hay 121 horas", False),
        ("Cuesta 21,5 mil", False),
        ("No tengo ese dato en los documentos.", False),
    ],
)
def test_contiene_valor_distingue_el_numero_completo(texto, esperado):
    assert script.contiene_valor(texto, "21") is esperado


def test_el_aumento_de_entrada_crece_con_la_memoria():
    caso = script.cargar_casos()[0]
    sin = script.aumento_de_entrada(caso, "contexto", 0)
    con = script.aumento_de_entrada(caso, "contexto", 4)

    assert sin == (0, 0) and con[0] > 0 and con[1] > 0
