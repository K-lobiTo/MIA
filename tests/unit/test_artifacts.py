from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from mia.access.keys import hash_key
from mia.config import settings
from mia.storage.models import Artifact, Domain, QueryLog, Unit


@pytest.fixture
def base(db):
    with db() as session:
        session.add_all([Unit(id="u1", name="Computación"), Unit(id="u2", name="Administración de Empresas")])
        session.flush()
        session.add_all(
            [
                Domain(id="d1", unit_id="u1", name="Currículum"),
                Domain(id="d2", unit_id="u1", name="Docentes"),
                Domain(id="d3", unit_id="u2", name="Currículum"),
            ]
        )
        session.commit()


def _crear(client, admin, **cambios):
    cuerpo = {
        "name": "Consulta administrativa Postgrados Computación",
        "description": "Personal de Computación",
        "access": {"all_domains": False, "unit_ids": ["u1"], "domain_ids": []},
        "modes": ["literal", "razonamiento"],
    }
    cuerpo.update(cambios)
    return client.post("/artifacts", json=cuerpo, headers=admin)


def test_todas_las_rutas_exigen_la_clave_de_administracion(client, admin, base):
    assert client.get("/artifacts").status_code == 401
    assert client.post("/artifacts", json={}).status_code == 401
    assert client.patch("/artifacts/x", json={}).status_code == 401
    assert client.post("/artifacts/x/key").status_code == 401


def test_crear_devuelve_la_clave_completa_una_sola_vez(client, admin, base):
    response = _crear(client, admin)

    assert response.status_code == 201
    body = response.json()
    assert body["key"].startswith("mia_") and body["key_prefix"] == body["key"][:8]
    assert body["active"] is True and body["modes"] == ["literal", "razonamiento"]
    assert body["daily_cap_usd"] == 0.5 and body["reasoning_daily_cap_usd"] is None
    assert body["access"] == {"all_domains": False, "unit_ids": ["u1"], "domain_ids": []}
    assert body["allowed_domain_count"] == 2

    listado = client.get("/artifacts", headers=admin).json()["artifacts"]
    assert len(listado) == 1 and "key" not in listado[0] and listado[0]["key_prefix"] == body["key"][:8]


def test_la_clave_se_guarda_solo_como_hash(client, admin, base, db):
    key = _crear(client, admin).json()["key"]

    with db() as session:
        artefacto = session.query(Artifact).one()
        assert artefacto.key_hash == hash_key(key)
        assert key not in (artefacto.key_hash, artefacto.key_prefix)


def test_nombre_repetido_responde_409(client, admin, base):
    _crear(client, admin)
    assert _crear(client, admin).status_code == 409


@pytest.mark.parametrize(
    "cambios",
    [
        {"access": {"all_domains": False, "unit_ids": [], "domain_ids": []}},
        {"modes": []},
        {"modes": ["inventado"]},
        {"daily_cap_usd": 0},
        {"daily_cap_usd": -1},
        {"daily_cap_usd": 1.0, "reasoning_daily_cap_usd": 2.0},
        {"reasoning_daily_cap_usd": 0},
        {"access": {"all_domains": False, "unit_ids": ["no-existe"], "domain_ids": []}},
        {"access": {"all_domains": False, "unit_ids": [], "domain_ids": ["no-existe"]}},
        {"name": "  "},
    ],
)
def test_configuraciones_invalidas_responden_422(client, admin, base, cambios):
    assert _crear(client, admin, **cambios).status_code == 422


def test_el_tope_por_defecto_es_050_y_se_puede_fijar_otro(client, admin, base):
    assert _crear(client, admin).json()["daily_cap_usd"] == 0.5
    otro = _crear(client, admin, name="Otro", daily_cap_usd=2.0, reasoning_daily_cap_usd=1.25).json()
    assert otro["daily_cap_usd"] == 2.0 and otro["reasoning_daily_cap_usd"] == 1.25


def test_acceso_a_todos_los_dominios_o_a_dominios_puntuales(client, admin, base):
    todos = _crear(client, admin, name="Todos", access={"all_domains": True, "unit_ids": [], "domain_ids": []})
    puntuales = _crear(
        client, admin, name="Puntuales", access={"all_domains": False, "unit_ids": [], "domain_ids": ["d1", "d3"]}
    )

    assert todos.json()["allowed_domain_count"] == 3
    assert puntuales.json()["allowed_domain_count"] == 2


def test_modificar_acceso_modos_topes_y_estado(client, admin, base):
    artefacto = _crear(client, admin).json()

    response = client.patch(
        f"/artifacts/{artefacto['id']}",
        json={
            "description": "Nueva",
            "access": {"all_domains": False, "unit_ids": ["u2"], "domain_ids": ["d1"]},
            "modes": ["literal"],
            "daily_cap_usd": 1.5,
            "reasoning_daily_cap_usd": 1.0,
            "active": False,
        },
        headers=admin,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["description"] == "Nueva" and body["modes"] == ["literal"] and body["active"] is False
    assert body["access"] == {"all_domains": False, "unit_ids": ["u2"], "domain_ids": ["d1"]}
    assert body["allowed_domain_count"] == 2
    assert body["daily_cap_usd"] == 1.5 and body["reasoning_daily_cap_usd"] == 1.0
    assert "key" not in body


def test_modificar_un_solo_campo_no_toca_los_demas(client, admin, base):
    artefacto = _crear(client, admin, daily_cap_usd=2.0, reasoning_daily_cap_usd=1.0).json()

    body = client.patch(f"/artifacts/{artefacto['id']}", json={"active": False}, headers=admin).json()

    assert body["active"] is False and body["modes"] == ["literal", "razonamiento"]
    assert body["daily_cap_usd"] == 2.0 and body["reasoning_daily_cap_usd"] == 1.0
    assert body["access"]["unit_ids"] == ["u1"]


def test_quitar_el_tope_de_razonamiento_con_null(client, admin, base):
    artefacto = _crear(client, admin, reasoning_daily_cap_usd=0.4).json()

    body = client.patch(f"/artifacts/{artefacto['id']}", json={"reasoning_daily_cap_usd": None}, headers=admin).json()

    assert body["reasoning_daily_cap_usd"] is None


def test_modificar_valida_contra_lo_que_ya_tenia(client, admin, base):
    artefacto = _crear(client, admin, daily_cap_usd=1.0).json()
    # El tope de razonamiento no puede superar el total que el artefacto ya tiene.
    response = client.patch(f"/artifacts/{artefacto['id']}", json={"reasoning_daily_cap_usd": 2.0}, headers=admin)
    assert response.status_code == 422
    assert client.patch(f"/artifacts/{artefacto['id']}", json={"modes": []}, headers=admin).status_code == 422
    assert client.patch("/artifacts/no-existe", json={"active": False}, headers=admin).status_code == 404


def test_regenerar_la_clave_invalida_la_anterior(client, admin, base):
    artefacto = _crear(client, admin).json()
    anterior = artefacto["key"]

    nueva = client.post(f"/artifacts/{artefacto['id']}/key", headers=admin)

    assert nueva.status_code == 200
    cuerpo = nueva.json()
    assert cuerpo["key"].startswith("mia_") and cuerpo["key"] != anterior
    assert cuerpo["key_prefix"] == cuerpo["key"][:8]
    assert client.get("/domains", headers={"X-Artifact-Key": anterior}).status_code == 401
    assert client.get("/domains", headers={"X-Artifact-Key": cuerpo["key"]}).status_code == 200
    assert client.post("/artifacts/no-existe/key", headers=admin).status_code == 404


def test_el_listado_cuenta_las_consultas_de_los_ultimos_7_dias(client, admin, base, db):
    artefacto = _crear(client, admin).json()
    ahora = datetime.now(UTC)
    with db() as session:
        for indice, dias in enumerate([0, 3, 6, 9, 30]):
            session.add(QueryLog(id=f"q{indice}", artifact_id=artefacto["id"], created_at=ahora - timedelta(days=dias, hours=1)))
        session.commit()

    listado = client.get("/artifacts", headers=admin).json()["artifacts"][0]

    assert listado["queries_last_7_days"] == 3


def test_el_listado_informa_los_modos_y_su_costo_medio(client, admin, base, db):
    artefacto = _crear(client, admin).json()
    ahora = datetime.now(UTC)
    with db() as session:
        session.add_all(
            [
                QueryLog(id="q1", artifact_id=artefacto["id"], created_at=ahora, mode="razonamiento", model="glm", outcome="answered", cost_usd=Decimal("0.02")),
                QueryLog(id="q2", artifact_id=artefacto["id"], created_at=ahora, mode="razonamiento", model="glm", outcome="no_info", cost_usd=Decimal("0.04")),
                # Sin resultados relevantes no se llamó al modelo: no cuenta para el costo medio.
                QueryLog(id="q5", artifact_id=artefacto["id"], created_at=ahora, mode="razonamiento", outcome="no_info", cost_usd=Decimal(0)),
                QueryLog(id="q3", artifact_id=artefacto["id"], created_at=ahora, mode="razonamiento", outcome="rejected_cap", cost_usd=Decimal(0)),
                QueryLog(id="q4", artifact_id=artefacto["id"], created_at=ahora - timedelta(days=20), mode="literal", outcome="answered", cost_usd=Decimal("0.5")),
            ]
        )
        session.commit()

    modos = {m["id"]: m for m in client.get("/artifacts", headers=admin).json()["modes"]}

    # Solo promedia las consultas que llegaron al modelo y de los últimos 7 días.
    assert modos["razonamiento"]["avg_cost_usd_7d"] == pytest.approx(0.03)
    assert modos["literal"]["avg_cost_usd_7d"] is None
    assert modos["literal"]["name"] == "Literal" and modos["razonamiento"]["name"] == "Con razonamiento"


# ----- Gasto de hoy frente a los topes (US4) -----


def _gasto(db, artefacto_id, costo, modo="literal"):
    with db() as session:
        session.add(QueryLog(id=f"g-{artefacto_id}-{modo}-{costo}", artifact_id=artefacto_id, mode=modo, outcome="answered",
                             model="m", cost_usd=Decimal(str(costo))))
        session.commit()


def test_el_listado_muestra_el_gasto_de_hoy_frente_a_los_topes(client, admin, base, db):
    artefacto = _crear(client, admin, daily_cap_usd=1.0, reasoning_daily_cap_usd=0.5).json()
    _gasto(db, artefacto["id"], 0.25, "literal")
    _gasto(db, artefacto["id"], 0.50, "razonamiento")

    hoy = client.get("/artifacts", headers=admin).json()["artifacts"][0]["today"]

    assert hoy["spent_usd"] == pytest.approx(0.75) and hoy["reasoning_spent_usd"] == pytest.approx(0.50)
    assert hoy["cap_reached"] is False and hoy["reasoning_cap_reached"] is True


def test_el_listado_marca_el_tope_total_alcanzado(client, admin, base, db):
    artefacto = _crear(client, admin, daily_cap_usd=0.5).json()
    _gasto(db, artefacto["id"], 0.5)

    hoy = client.get("/artifacts", headers=admin).json()["artifacts"][0]["today"]

    assert hoy["cap_reached"] is True and hoy["reasoning_cap_reached"] is False


def test_bloque_global_con_el_tope_de_la_api_y_la_suma_de_topes(client, admin, base, db, monkeypatch):
    monkeypatch.setattr(settings, "daily_cap_usd", 3.0)
    uno = _crear(client, admin, name="Uno", daily_cap_usd=1.0).json()
    _crear(client, admin, name="Dos", daily_cap_usd=1.5)
    _gasto(db, uno["id"], 0.4)

    bloque = client.get("/artifacts", headers=admin).json()["global"]

    assert bloque == {"daily_cap_usd": 3.0, "spent_today_usd": pytest.approx(0.4),
                      "sum_of_artifact_caps_usd": pytest.approx(2.5), "caps_exceed_global": False}


def test_avisa_cuando_la_suma_de_topes_supera_el_de_la_api(client, admin, base, monkeypatch):
    monkeypatch.setattr(settings, "daily_cap_usd", 2.0)
    _crear(client, admin, name="Uno", daily_cap_usd=1.5)
    _crear(client, admin, name="Dos", daily_cap_usd=1.0)

    assert client.get("/artifacts", headers=admin).json()["global"]["caps_exceed_global"] is True


def test_un_artefacto_desactivado_no_cuenta_en_la_suma_de_topes(client, admin, base, monkeypatch):
    monkeypatch.setattr(settings, "daily_cap_usd", 2.0)
    _crear(client, admin, name="Uno", daily_cap_usd=1.5)
    apagado = _crear(client, admin, name="Dos", daily_cap_usd=1.0).json()
    client.patch(f"/artifacts/{apagado['id']}", json={"active": False}, headers=admin)

    bloque = client.get("/artifacts", headers=admin).json()["global"]

    assert bloque["sum_of_artifact_caps_usd"] == pytest.approx(1.5) and bloque["caps_exceed_global"] is False
