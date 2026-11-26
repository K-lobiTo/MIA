"""Cambiar o quitar el programa de un usuario de la Consulta (feature 023, historia 3)."""

import json
from datetime import timedelta

import pytest
from sqlalchemy import select

from mia.access.scope import Principal
from mia.api.main import app
from mia.api.security import require_admin
from mia.storage.models import ConsultaSession, ConsultaUser, Unit, _now


@pytest.fixture
def base(db):
    with db() as session:
        session.add_all([Unit(id="p1", name="Computación"), Unit(id="p2", name="Analítica")])
        session.add_all(
            [
                ConsultaUser(id="u1", username="ana", password_hash="hash-original", unit_id="p1", created_by="t"),
                ConsultaUser(id="u2", username="beto", password_hash="x", unit_id="p2", created_by="t"),
            ]
        )
        session.add(ConsultaSession(id="s1", user_id="u1", token_hash="t1", expires_at=_now() + timedelta(hours=1)))
        session.commit()
    return db


@pytest.fixture
def de_computacion():
    principal = Principal(email="coord@itcr.ac.cr", is_global=False, unit_ids=frozenset({"p1"}), source="entra")
    app.dependency_overrides[require_admin] = lambda: principal
    yield
    app.dependency_overrides.pop(require_admin, None)


def _usuario(db, id_="u1"):
    with db() as session:
        return session.get(ConsultaUser, id_)


def test_mover_a_otro_programa_no_toca_contrasena_estado_ni_sesiones(client, admin, base, capsys):
    response = client.patch("/consulta-users/u1", headers=admin, json={"unit_id": "p2"})

    assert response.status_code == 200 and response.json()["unit"] == {"id": "p2", "name": "Analítica"}
    usuario = _usuario(base)
    assert (usuario.unit_id, usuario.password_hash, usuario.active) == ("p2", "hash-original", True)
    with base() as session:
        assert session.scalars(select(ConsultaSession.id)).all() == ["s1"]
    linea = [json.loads(x) for x in capsys.readouterr().out.splitlines() if "consulta_user.update" in x][-1]
    assert "Analítica" in linea["detail"]


def test_null_lo_deja_sin_programa_y_ausente_no_cambia(client, admin, base):
    assert client.patch("/consulta-users/u1", headers=admin, json={"active": True}).json()["unit"]["id"] == "p1"

    assert client.patch("/consulta-users/u1", headers=admin, json={"unit_id": None}).json()["unit"] is None
    assert _usuario(base).unit_id is None


def test_un_programa_inexistente_responde_404_sin_cambiar_nada(client, admin, base):
    response = client.patch("/consulta-users/u1", headers=admin, json={"unit_id": "nada", "active": False})

    assert response.status_code == 404
    assert (_usuario(base).unit_id, _usuario(base).active) == ("p1", True)


def test_el_alcance_de_programa_no_saca_usuarios_de_sus_programas(client, base, de_computacion):
    assert client.patch("/consulta-users/u1", json={"unit_id": "p2"}).status_code == 403
    assert client.patch("/consulta-users/u1", json={"unit_id": None}).status_code == 403
    # Un usuario de otro programa ni siquiera se ve.
    assert client.patch("/consulta-users/u2", json={"unit_id": "p1"}).status_code == 404
    assert _usuario(base).unit_id == "p1" and _usuario(base, "u2").unit_id == "p2"


def test_despues_de_reasignar_a_sus_usuarios_el_programa_se_puede_eliminar(client, admin, base):
    assert client.delete("/units/p1", headers=admin).status_code == 409

    client.patch("/consulta-users/u1", headers=admin, json={"unit_id": "p2"})

    assert client.delete("/units/p1", headers=admin).status_code == 204
