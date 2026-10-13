"""Alcance por unidad en artefactos y en el módulo Uso (specs/004-acceso-panel-tec, US4)."""

import csv
import io
from datetime import timedelta
from decimal import Decimal

import pytest

from mia.access.caps import day_start_utc
from mia.storage.models import Domain, QueryLog

COORD = "coord.comp@itcr.ac.cr"
COORD_ADM = "coord.adm@itcr.ac.cr"
AMBAS = "ambas@itcr.ac.cr"
OPERADOR = "operador@itcr.ac.cr"


@pytest.fixture
def mundo(db, units, make_admin, make_artifact):
    with db() as session:
        session.add_all(
            [Domain(id="dc", unit_id=units.comp, name="Currículum"), Domain(id="da", unit_id=units.adm, name="Currículum")]
        )
        session.commit()
    make_admin(COORD, units=["Computación"])
    make_admin(COORD_ADM, units=["Administración de Empresas"])
    make_admin(AMBAS, units=["Computación", "Administración de Empresas"])
    make_admin(OPERADOR, global_=True)
    artefactos = {
        "comp": make_artifact("Consulta Computación", units=[units.comp]),
        "adm": make_artifact("Consulta Administración", units=[units.adm]),
        "todos": make_artifact("Consulta general", all_domains=True),
        "mezcla": make_artifact("Consulta mixta", units=[units.comp, units.adm]),
    }
    hoy = day_start_utc()
    with db() as session:
        for i, (clave, art) in enumerate(artefactos.items()):
            session.add(
                QueryLog(
                    id=f"q-{clave}", artifact_id=art.id, created_at=hoy + timedelta(hours=i + 1), mode="literal",
                    outcome="answered", model="modelo", cost_usd=Decimal("0.01"), prompt_tokens=10, completion_tokens=5,
                    latency_ms=1000, question=f"pregunta de {clave}", domain_ids="[]", sources="[]",
                )
            )
        session.commit()
    return artefactos


def nombres(response):
    return sorted(a["name"] for a in response.json()["artifacts"])


def test_listado_de_artefactos_por_alcance(client, mundo, as_user):
    assert nombres(client.get("/artifacts", headers=as_user(COORD))) == ["Consulta Computación"]
    assert nombres(client.get("/artifacts", headers=as_user(COORD_ADM))) == ["Consulta Administración"]
    # Quien tiene las dos unidades no ve "todos los dominios", y sí ve el de las dos unidades.
    assert nombres(client.get("/artifacts", headers=as_user(AMBAS))) == [
        "Consulta Administración", "Consulta Computación", "Consulta mixta",
    ]
    assert len(nombres(client.get("/artifacts", headers=as_user(OPERADOR)))) == 4


def test_el_bloque_global_solo_lo_ve_el_alcance_global(client, mundo, as_user, admin):
    assert client.get("/artifacts", headers=as_user(COORD)).json()["global"] is None
    for headers in (as_user(OPERADOR), admin):
        bloque = client.get("/artifacts", headers=headers).json()["global"]
        assert bloque["daily_cap_usd"] > 0 and "spent_today_usd" in bloque


def test_crear_artefactos_dentro_del_alcance(client, mundo, units, as_user):
    base = {"name": "Nuevo", "modes": ["literal"]}
    headers = as_user(COORD)
    ok = client.post("/artifacts", json={**base, "access": {"unit_ids": [units.comp]}}, headers=headers)
    assert ok.status_code == 201 and ok.json()["key"]
    puntual = client.post("/artifacts", json={**base, "name": "Puntual", "access": {"domain_ids": ["dc"]}}, headers=headers)
    assert puntual.status_code == 201
    for acceso in (
        {"all_domains": True},
        {"unit_ids": [units.adm]},
        {"unit_ids": [units.comp, units.adm]},
        {"domain_ids": ["da"]},
        {"unit_ids": [units.comp], "domain_ids": ["da"]},
    ):
        response = client.post("/artifacts", json={**base, "name": "Otro", "access": acceso}, headers=headers)
        assert response.status_code == 403 and response.json()["code"] == "out_of_scope", acceso


def test_quien_tiene_dos_unidades_puede_combinarlas_pero_no_todos_los_dominios(client, mundo, units, as_user):
    headers = as_user(AMBAS)
    base = {"name": "Dos unidades", "modes": ["literal"]}
    assert client.post("/artifacts", json={**base, "access": {"unit_ids": [units.comp, units.adm]}}, headers=headers).status_code == 201
    response = client.post("/artifacts", json={**base, "name": "T", "access": {"all_domains": True}}, headers=headers)
    assert response.status_code == 403


def test_el_alcance_global_crea_cualquier_artefacto(client, mundo, as_user):
    response = client.post(
        "/artifacts", json={"name": "General", "modes": ["literal"], "access": {"all_domains": True}}, headers=as_user(OPERADOR)
    )
    assert response.status_code == 201


def test_modificar_un_artefacto_ajeno_es_404(client, mundo, as_user):
    ajeno, mixto, todos = mundo["adm"], mundo["mezcla"], mundo["todos"]
    headers = as_user(COORD)
    for art in (ajeno, mixto, todos):
        assert client.patch(f"/artifacts/{art.id}", json={"active": False}, headers=headers).status_code == 404
        assert client.post(f"/artifacts/{art.id}/key", headers=headers).status_code == 404
    propio = mundo["comp"]
    assert client.patch(f"/artifacts/{propio.id}", json={"active": False}, headers=headers).status_code == 200
    assert client.post(f"/artifacts/{propio.id}/key", headers=headers).status_code == 200


def test_no_se_puede_ampliar_el_acceso_de_un_artefacto_propio_a_otra_unidad(client, mundo, units, as_user):
    propio = mundo["comp"]
    response = client.patch(
        f"/artifacts/{propio.id}", json={"access": {"unit_ids": [units.comp, units.adm]}}, headers=as_user(COORD)
    )
    assert response.status_code == 403 and response.json()["code"] == "out_of_scope"
    response = client.patch(f"/artifacts/{propio.id}", json={"access": {"all_domains": True}}, headers=as_user(COORD))
    assert response.status_code == 403


# --- Uso ---


def _nombres_uso(body):
    return sorted(row["artifact"] if "artifact" in row else row.get("name", "") for row in body["by_artifact"])


def test_uso_solo_suma_los_artefactos_del_alcance(client, mundo, as_user):
    propio = client.get("/usage?period=today", headers=as_user(COORD)).json()
    assert propio["kpis"]["queries"]["value"] == 1
    assert [row["name"] for row in propio["by_artifact"]] == ["Consulta Computación"]
    todo = client.get("/usage?period=today", headers=as_user(OPERADOR)).json()
    assert todo["kpis"]["queries"]["value"] == 4 and len(todo["by_artifact"]) == 4


def test_un_artifact_id_ajeno_en_el_filtro_no_devuelve_nada_ajeno(client, mundo, as_user):
    ajeno = mundo["adm"].id
    body = client.get(f"/usage?period=today&artifact_id={ajeno}", headers=as_user(COORD)).json()
    assert body["kpis"]["queries"]["value"] == 0 and body["by_artifact"] == []
    listado = client.get(f"/usage/queries?period=today&artifact_id={ajeno}", headers=as_user(COORD)).json()
    assert listado["total"] == 0


def test_alcance_sin_ningun_artefacto_ve_ceros_y_no_todo(client, db, units, make_admin, as_user, make_artifact):
    make_artifact("De la otra unidad", units=[units.adm])
    make_admin("sin.artefactos@itcr.ac.cr", units=["Computación"])
    headers = as_user("sin.artefactos@itcr.ac.cr")
    assert client.get("/usage?period=today", headers=headers).json()["kpis"]["queries"]["value"] == 0
    assert client.get("/usage/queries?period=today", headers=headers).json()["total"] == 0
    assert client.get("/artifacts", headers=headers).json()["artifacts"] == []


def test_registro_detalle_y_csv_por_alcance(client, mundo, as_user):
    headers = as_user(COORD)
    listado = client.get("/usage/queries?period=today", headers=headers).json()
    assert [item["id"] for item in listado["items"]] == ["q-comp"]

    assert client.get("/usage/queries/q-comp", headers=headers).status_code == 200
    for ajeno in ("q-adm", "q-todos", "q-mezcla"):
        assert client.get(f"/usage/queries/{ajeno}", headers=headers).status_code == 404

    csv_propio = client.get("/usage/queries?period=today&format=csv&include_questions=true", headers=headers)
    filas = list(csv.DictReader(io.StringIO(csv_propio.text.lstrip("﻿"))))
    assert [fila["id"] for fila in filas] == ["q-comp"]
    assert "pregunta de adm" not in csv_propio.text


def test_consulta_sin_artefacto_solo_para_global(client, db, mundo, as_user):
    with db() as session:
        session.add(QueryLog(id="q-huerfana", artifact_id=None, created_at=day_start_utc() + timedelta(hours=9)))
        session.commit()
    assert client.get("/usage/queries/q-huerfana", headers=as_user(COORD)).status_code == 404
    assert client.get("/usage/queries/q-huerfana", headers=as_user(OPERADOR)).status_code == 200


def test_el_saldo_es_solo_global(client, mundo, as_user, admin, monkeypatch):
    from mia.api.routes import usage as usage_routes

    monkeypatch.setattr(usage_routes.balance_module, "get_balance", lambda session: {"available": False})
    response = client.get("/usage/balance", headers=as_user(COORD))
    assert response.status_code == 403 and response.json()["code"] == "global_only"
    assert client.get("/usage/balance", headers=as_user(OPERADOR)).status_code == 200
    assert client.get("/usage/balance", headers=admin).status_code == 200
