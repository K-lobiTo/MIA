import csv
import io
from datetime import timedelta
from decimal import Decimal

import pytest

from mia.access.caps import day_start_utc
from mia.storage.models import Artifact, Domain, QueryLog, Unit


@pytest.fixture
def datos(db):
    """Dos artefactos y siete consultas con cifras fáciles de calcular a mano.

    Hoy (a partir del inicio del día de Costa Rica): seis consultas. Ayer: una, para comparar.
    """
    hoy = day_start_utc()
    ayer = hoy - timedelta(days=1)

    def fila(id_, artefacto, cuando, **campos):
        base = {"mode": "literal", "outcome": "answered", "cost_usd": Decimal(0), "question": f"pregunta {id_}", "domain_ids": "[]", "sources": "[]"}
        base.update(campos)
        return QueryLog(id=id_, artifact_id=artefacto, created_at=cuando, **base)

    with db() as session:
        session.add(Unit(id="u1", name="Computación"))
        session.flush()
        session.add(Domain(id="d1", unit_id="u1", name="Currículum"))
        session.add_all(
            [
                Artifact(id="a1", name="Consulta Computación", key_hash="h1", key_prefix="mia_aaaa", daily_cap_usd=Decimal("1.5")),
                Artifact(id="a2", name="Consulta Administración", key_hash="h2", key_prefix="mia_bbbb", daily_cap_usd=Decimal("0.5")),
            ]
        )
        session.flush()
        session.add_all(
            [
                fila("q1", "a1", hoy + timedelta(hours=1), mode="razonamiento", model="z-ai/glm", cost_usd=Decimal("0.02"),
                     prompt_tokens=1000, completion_tokens=300, reasoning_tokens=200, latency_ms=10000, rating="util",
                     rating_comment="Justo lo que necesitaba", domain_ids='["d1"]',
                     sources='[{"domain": "Currículum", "document": "plan.pdf"}]'),
                fila("q2", "a1", hoy + timedelta(hours=1, minutes=30), model="flash", cost_usd=Decimal("0.002"),
                     prompt_tokens=800, completion_tokens=50, latency_ms=2000, rating="no_util"),
                fila("q3", "a1", hoy + timedelta(hours=2), model="flash", outcome="no_info", cost_usd=Decimal("0.001"),
                     prompt_tokens=700, completion_tokens=5, latency_ms=1000),
                fila("q4", "a2", hoy + timedelta(hours=3), outcome="error", latency_ms=500, reject_reason="saldo agotado"),
                fila("q5", "a2", hoy + timedelta(hours=3, minutes=1), outcome="rejected_cap", latency_ms=5,
                     reject_reason="Este artefacto alcanzó su tope diario de gasto"),
                fila("q6", "a2", hoy + timedelta(hours=4), outcome="rejected_permission", latency_ms=5,
                     reject_reason="=cmd|' /C calc'!A0", question="=SUMA(1+1)"),
                fila("p1", "a1", ayer + timedelta(hours=3), model="flash", cost_usd=Decimal("0.004"),
                     prompt_tokens=500, completion_tokens=100, latency_ms=4000),
            ]
        )
        session.commit()


def _uso(client, admin, **params):
    return client.get("/usage", params=params, headers=admin)


def test_el_uso_exige_la_clave_de_administracion(client, admin, datos):
    assert client.get("/usage").status_code == 401
    assert client.get("/usage/queries").status_code == 401
    assert client.get("/usage/queries/q1").status_code == 401
    assert client.get("/usage/balance").status_code == 401


def test_indicadores_de_hoy_con_su_comparacion_con_ayer(client, admin, datos):
    body = _uso(client, admin, period="today").json()
    k = body["kpis"]

    assert body["period"]["bucket"] == "hour" and body["period"]["from"] == body["period"]["to"]
    assert k["spend_usd"]["value"] == pytest.approx(0.023) and k["spend_usd"]["previous"] == pytest.approx(0.004)
    assert k["spend_usd"]["change_pct"] == pytest.approx(475.0)
    assert k["queries"]["value"] == 6 and k["queries"]["previous"] == 1 and k["queries"]["change_pct"] == pytest.approx(500.0)
    # El total de tokens es entrada más salida; los de razonamiento son parte de la salida.
    assert k["tokens"]["input"] == 2500 and k["tokens"]["output"] == 355 and k["tokens"]["reasoning"] == 200
    assert k["tokens"]["value"] == 2855 and k["tokens"]["previous"] == 600
    assert k["tokens"]["change_pct"] == pytest.approx(375.8)
    # El costo medio solo promedia las consultas que llegaron al modelo (q1, q2, q3).
    assert k["avg_cost_usd"]["value"] == pytest.approx(0.023 / 3) and k["avg_cost_usd"]["previous"] == pytest.approx(0.004)


def test_tiempos_de_respuesta_excluyen_las_rechazadas(client, admin, datos):
    k = _uso(client, admin, period="today").json()["kpis"]["latency_ms"]

    # q1, q2, q3 y q4: [500, 1000, 2000, 10000]. Rango más cercano: mediana 1000 y percentil 95 = 10000.
    assert k["p50"] == 1000 and k["p95"] == 10000
    assert k["previous_p50"] == 4000 and k["change_pct"] == pytest.approx(-75.0)


def test_porcentajes_de_sin_informacion_errores_y_utiles(client, admin, datos):
    k = _uso(client, admin, period="today").json()["kpis"]

    assert k["no_info_pct"]["value"] == pytest.approx(100 / 3, abs=0.1)  # 1 de 3 respuestas del modelo
    assert k["no_info_pct"]["previous"] == 0 and k["no_info_pct"]["change_pts"] == pytest.approx(33.3, abs=0.1)
    assert k["error_pct"]["value"] == pytest.approx(25.0)  # 1 de 4 consultas que no fueron rechazadas
    assert k["useful_pct"]["value"] == pytest.approx(50.0) and k["useful_pct"]["rated"] == 2
    assert k["useful_pct"]["previous"] is None and k["useful_pct"]["change_pts"] is None


def test_sin_consultas_en_el_periodo_anterior_no_hay_variacion(client, admin, datos):
    k = _uso(client, admin, period="7d").json()["kpis"]

    assert k["queries"]["value"] == 7 and k["queries"]["previous"] == 0 and k["queries"]["change_pct"] is None


def test_la_serie_de_hoy_es_por_hora_y_se_agrupa_por_artefacto_modo_o_modelo(client, admin, datos):
    por_artefacto = _uso(client, admin, period="today", group_by="artifact").json()
    assert len(por_artefacto["series"]) == 24  # todas las horas del día, también las vacías
    total = sum(g["spend_usd"] for punto in por_artefacto["series"] for g in punto["groups"].values())
    assert total == pytest.approx(0.023)
    nombres = {nombre for punto in por_artefacto["series"] for nombre in punto["groups"]}
    assert nombres == {"Consulta Computación", "Consulta Administración"}

    por_modo = _uso(client, admin, period="today", group_by="mode").json()
    assert {n for p in por_modo["series"] for n in p["groups"]} == {"literal", "razonamiento"}

    por_modelo = _uso(client, admin, period="today", group_by="model").json()
    assert {n for p in por_modelo["series"] for n in p["groups"]} == {"z-ai/glm", "flash", "(sin modelo)"}
    tokens = sum(g["tokens"] for p in por_modelo["series"] for g in p["groups"].values())
    assert tokens == 2855


def test_la_serie_de_varios_dias_es_por_dia(client, admin, datos):
    siete = _uso(client, admin, period="7d").json()
    treinta = _uso(client, admin, period="30d").json()

    assert siete["period"]["bucket"] == "day" and len(siete["series"]) == 7
    assert len(treinta["series"]) == 30
    consultas = sum(g["queries"] for p in siete["series"] for g in p["groups"].values())
    assert consultas == 7


def test_tabla_por_artefacto_con_el_gasto_de_hoy_frente_a_su_tope(client, admin, datos):
    filas = {f["name"]: f for f in _uso(client, admin, period="today").json()["by_artifact"]}

    a1, a2 = filas["Consulta Computación"], filas["Consulta Administración"]
    assert a1["id"] == "a1" and a1["daily_cap_usd"] == 1.5 and a1["today_spent_usd"] == pytest.approx(0.023)
    assert a1["spend_usd"] == pytest.approx(0.023) and a1["queries"] == 3
    assert a1["avg_latency_ms"] == pytest.approx(13000 / 3)
    assert a2["daily_cap_usd"] == 0.5 and a2["queries"] == 3 and a2["spend_usd"] == 0
    assert a2["avg_latency_ms"] == 500  # solo cuenta la consulta que no fue rechazada


def test_el_gasto_de_hoy_de_la_tabla_no_depende_del_periodo_elegido(client, admin, datos):
    a1 = next(f for f in _uso(client, admin, period="7d").json()["by_artifact"] if f["id"] == "a1")

    assert a1["today_spent_usd"] == pytest.approx(0.023) and a1["spend_usd"] == pytest.approx(0.027)


def test_tabla_por_modelo_ordenada_por_gasto(client, admin, datos):
    modelos = _uso(client, admin, period="today").json()["by_model"]

    assert [m["model"] for m in modelos] == ["z-ai/glm", "flash"]
    glm, flash = modelos
    assert glm["queries"] == 1 and glm["tokens"] == 1300 and glm["spend_usd"] == pytest.approx(0.02)
    assert flash["queries"] == 2 and flash["tokens"] == 1555 and flash["spend_usd"] == pytest.approx(0.003)
    assert glm["avg_latency_ms"] == 10000 and flash["avg_latency_ms"] == 1500


def test_filtros_por_artefacto_y_por_modo(client, admin, datos):
    solo_a2 = _uso(client, admin, period="today", artifact_id="a2").json()
    assert solo_a2["kpis"]["queries"]["value"] == 3 and solo_a2["kpis"]["spend_usd"]["value"] == 0
    assert [f["id"] for f in solo_a2["by_artifact"]] == ["a2"]

    ambos = client.get("/usage", params=[("period", "today"), ("artifact_id", "a1"), ("artifact_id", "a2")], headers=admin).json()
    assert ambos["kpis"]["queries"]["value"] == 6

    razonamiento = _uso(client, admin, period="today", mode="razonamiento").json()
    assert razonamiento["kpis"]["queries"]["value"] == 1 and razonamiento["kpis"]["spend_usd"]["value"] == pytest.approx(0.02)

    assert _uso(client, admin, period="today", mode="inventado").status_code == 422


def test_periodo_personalizado(client, admin, datos):
    ayer = (day_start_utc() - timedelta(days=1) + timedelta(hours=12)).date().isoformat()  # mediodía UTC de la fecha de ayer en Costa Rica

    body = _uso(client, admin, period="custom", **{"from": ayer, "to": ayer}).json()

    assert body["kpis"]["queries"]["value"] == 1 and body["period"]["bucket"] == "day" and len(body["series"]) == 1


@pytest.mark.parametrize(
    "params",
    [
        {"period": "custom"},
        {"period": "custom", "from": "2026-10-09", "to": "2026-10-01"},
        {"period": "custom", "from": "no-es-fecha", "to": "2026-10-01"},
        {"period": "custom", "from": "2024-01-01", "to": "2026-10-01"},
        {"period": "mes"},
    ],
)
def test_periodos_invalidos_responden_422(client, admin, datos, params):
    assert _uso(client, admin, **params).status_code == 422


def test_sin_consultas_los_indicadores_son_cero_y_sin_variacion(client, admin, db):
    body = _uso(client, admin, period="today").json()

    assert body["kpis"]["queries"] == {"value": 0, "previous": 0, "change_pct": None}
    assert body["kpis"]["latency_ms"]["p50"] is None and body["kpis"]["useful_pct"]["rated"] == 0
    assert body["by_artifact"] == [] and body["by_model"] == []


# ----- Registro de consultas -----


def _lista(client, admin, **params):
    return client.get("/usage/queries", params=params, headers=admin)


def test_registro_de_consultas_de_la_mas_reciente_a_la_mas_antigua(client, admin, datos):
    body = _lista(client, admin, period="7d").json()

    assert body["total"] == 7 and body["page"] == 1 and body["page_size"] == 50
    assert [q["id"] for q in body["items"]] == ["q6", "q5", "q4", "q3", "q2", "q1", "p1"]
    primera = next(q for q in body["items"] if q["id"] == "q1")
    assert primera["artifact"] == "Consulta Computación" and primera["mode"] == "razonamiento" and primera["model"] == "z-ai/glm"
    assert primera["tokens"] == 1300 and primera["cost_usd"] == pytest.approx(0.02) and primera["cost_estimated"] is False
    assert primera["latency_ms"] == 10000 and primera["outcome"] == "answered" and primera["rating"] == "util"
    assert primera["created_at"].endswith("Z")
    assert "question" not in primera


def test_paginacion_y_filtro_por_resultado(client, admin, datos):
    pagina2 = _lista(client, admin, period="7d", page=2, page_size=3).json()
    assert pagina2["total"] == 7 and [q["id"] for q in pagina2["items"]] == ["q3", "q2", "q1"]

    rechazadas = _lista(client, admin, period="today", outcome=["rejected_cap", "rejected_permission"]).json()
    assert [q["id"] for q in rechazadas["items"]] == ["q6", "q5"]
    assert rechazadas["items"][1]["reject_reason"].startswith("Este artefacto alcanzó")

    assert _lista(client, admin, period="today", page_size=500).status_code == 422
    assert _lista(client, admin, period="today", page=0).status_code == 422


def test_el_registro_respeta_los_filtros_de_periodo_artefacto_y_modo(client, admin, datos):
    assert _lista(client, admin, period="today").json()["total"] == 6
    assert _lista(client, admin, period="today", artifact_id="a2").json()["total"] == 3
    assert _lista(client, admin, period="today", mode="razonamiento").json()["total"] == 1


def test_detalle_de_una_consulta(client, admin, datos):
    body = client.get("/usage/queries/q1", headers=admin).json()

    assert body["question"] == "pregunta q1" and body["domains"] == ["Computación / Currículum"]
    assert body["sources"] == [{"domain": "Currículum", "document": "plan.pdf"}]
    assert body["rating"] == "util" and body["rating_comment"] == "Justo lo que necesitaba"
    assert client.get("/usage/queries/no-existe", headers=admin).status_code == 404


def _csv(respuesta):
    return list(csv.DictReader(io.StringIO(respuesta.text.lstrip("﻿"))))


def test_csv_sin_el_texto_de_las_preguntas_por_defecto(client, admin, datos):
    respuesta = _lista(client, admin, period="today", format="csv")

    assert respuesta.status_code == 200 and respuesta.headers["content-type"].startswith("text/csv")
    assert "attachment" in respuesta.headers["content-disposition"] and ".csv" in respuesta.headers["content-disposition"]
    filas = _csv(respuesta)
    assert len(filas) == 6 and "question" not in filas[0]
    assert "pregunta q1" not in respuesta.text
    primera = next(f for f in filas if f["id"] == "q1")
    assert primera["artifact"] == "Consulta Computación" and primera["prompt_tokens"] == "1000" and primera["rating"] == "util"


def test_csv_con_las_preguntas_solo_si_se_piden(client, admin, datos):
    filas = _csv(_lista(client, admin, period="today", format="csv", include_questions="true"))

    assert next(f for f in filas if f["id"] == "q1")["question"] == "pregunta q1"


def test_csv_neutraliza_celdas_que_parecen_formulas(client, admin, datos):
    filas = _csv(_lista(client, admin, period="today", format="csv", include_questions="true"))

    q6 = next(f for f in filas if f["id"] == "q6")
    # Una celda que empieza con = + - @ se abriría como fórmula en una hoja de cálculo.
    assert q6["question"].startswith("'=") and q6["reject_reason"].startswith("'=")
