"""Los casos de medición de la memoria de conversación (feature 014) son válidos y cubren las cinco categorías."""

import json
from pathlib import Path

RUTA = Path(__file__).resolve().parents[2] / "scripts" / "datos" / "casos_memoria.json"
CATEGORIAS = {
    "tema_anterior",
    "pronombre",
    "cambio_de_modo",
    "cambio_de_tema",
    "calculo_en_razonamiento",
}
MINIMOS = {
    "tema_anterior": 4,
    "pronombre": 3,
    "cambio_de_modo": 3,
    "cambio_de_tema": 3,
    "calculo_en_razonamiento": 2,
}


def _casos():
    return json.loads(RUTA.read_text(encoding="utf-8"))


def test_los_casos_tienen_ids_unicos_y_la_forma_esperada():
    casos = _casos()
    ids = [c["id"] for c in casos]

    assert len(ids) == len(set(ids))
    for caso in casos:
        assert caso["categoria"] in CATEGORIAS
        assert caso["pregunta"].strip() and caso["nota"].strip()
        assert caso["modo"] in {"literal", "razonamiento"}
        assert caso["historial"], "todo caso lleva al menos una vuelta anterior"
        for turno in caso["historial"]:
            assert turno["question"].strip() and turno["answer"].strip()
            assert turno["mode"] in {"literal", "razonamiento"}


def test_hay_los_casos_minimos_de_cada_categoria():
    casos = _casos()

    for categoria, minimo in MINIMOS.items():
        assert sum(c["categoria"] == categoria for c in casos) >= minimo, categoria


def test_los_documentos_esperados_estan_salvo_en_los_calculos_y_los_calculos_dicen_que_no_repetir():
    for caso in _casos():
        if caso["categoria"] == "calculo_en_razonamiento":
            assert caso["no_debe_contener"].strip()
            assert any(
                t["mode"] == "razonamiento" and caso["no_debe_contener"] in t["answer"]
                for t in caso["historial"]
            )
        else:
            assert caso["documentos"] and all(d.endswith(".txt") for d in caso["documentos"])
            assert "no_debe_contener" not in caso
