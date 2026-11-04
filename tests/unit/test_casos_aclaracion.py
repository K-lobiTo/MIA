"""Los casos de calibración de la aclaración de programa (feature 013) son válidos y cubren los tres tipos."""

import json
from pathlib import Path

RUTA = Path(__file__).resolve().parents[2] / "scripts" / "datos" / "casos_aclaracion.json"


def test_los_casos_tienen_id_unico_pregunta_y_una_espera_valida():
    casos = json.loads(RUTA.read_text(encoding="utf-8"))
    ids = [c["id"] for c in casos]

    assert len(ids) == len(set(ids)) and len(casos) >= 10
    assert all(c["pregunta"].strip() and c["nota"].strip() for c in casos)
    assert {c["espera"] for c in casos} == {"aclaracion", "sin_aclaracion"}


def test_hay_ambiguas_de_un_programa_y_sin_relacion_incluida_la_que_origina_la_feature():
    casos = {c["id"]: c for c in json.loads(RUTA.read_text(encoding="utf-8"))}

    assert casos["AC1"]["pregunta"] == "¿Cuándo empiezan las lecciones?" and casos["AC1"]["espera"] == "aclaracion"
    assert casos["SR1"]["pregunta"] == "¿Cuánto cuesta la luna?" and casos["SR1"]["espera"] == "sin_aclaracion"
    assert any(i.startswith("UP") for i in casos) and any(i.startswith("SR") for i in casos)
