"""La memoria de conversación del artefacto (feature 014): rango, alcance, registro y /config."""

import json

import pytest

from mia.storage.models import Domain

COORD = "coord.comp@itcr.ac.cr"
COORD_ADM = "coord.adm@itcr.ac.cr"
OPERADOR = "operador@itcr.ac.cr"


@pytest.fixture
def mundo(db, units, make_admin, make_artifact):
    with db() as session:
        session.add_all(
            [
                Domain(id="dc", unit_id=units.comp, name="Currículum"),
                Domain(id="da", unit_id=units.adm, name="Currículum"),
            ]
        )
        session.commit()
    make_admin(COORD, units=["Computación"])
    make_admin(OPERADOR, global_=True)
    return {
        "comp": make_artifact("Consulta Computación", units=[units.comp]),
        "adm": make_artifact("Consulta Administración", units=[units.adm]),
    }


def _crear(client, headers, units, **extra):
    cuerpo = {
        "name": "Nueva",
        "access": {"all_domains": False, "unit_ids": [units.comp], "domain_ids": []},
        "modes": ["literal"],
        **extra,
    }
    return client.post("/artifacts", json=cuerpo, headers=headers)


def _artefacto(client, headers, artifact_id):
    return next(
        a
        for a in client.get("/artifacts", headers=headers).json()["artifacts"]
        if a["id"] == artifact_id
    )


def _lineas(capsys):
    return [json.loads(l) for l in capsys.readouterr().out.splitlines() if l.startswith("{")]


def test_los_artefactos_existentes_y_nuevos_nacen_con_memoria_cero(client, mundo, admin, units):
    assert _artefacto(client, admin, mundo["comp"].id)["context_turns"] == 0
    creado = _crear(client, admin, units)
    assert creado.status_code == 201 and creado.json()["context_turns"] == 0


def test_se_puede_crear_con_memoria_y_cambiar_despues(client, mundo, admin, units):
    creado = _crear(client, admin, units, context_turns=4).json()
    assert creado["context_turns"] == 4

    cambiado = client.patch(f"/artifacts/{creado['id']}", json={"context_turns": 7}, headers=admin)

    assert cambiado.status_code == 200 and cambiado.json()["context_turns"] == 7
    assert _artefacto(client, admin, creado["id"])["context_turns"] == 7
    # Editar otro campo no toca la memoria.
    client.patch(f"/artifacts/{creado['id']}", json={"description": "otra"}, headers=admin)
    assert _artefacto(client, admin, creado["id"])["context_turns"] == 7


@pytest.mark.parametrize("valor", [-1, 11, 2.5, "tres", None, [1]])
def test_un_valor_fuera_de_rango_o_no_numerico_da_422_y_no_cambia_nada(client, mundo, admin, valor):
    artefacto = mundo["comp"]
    cuerpo = {"context_turns": valor}

    respuesta = client.patch(f"/artifacts/{artefacto.id}", json=cuerpo, headers=admin)

    if valor is None:  # nulo equivale a "no se envía": no cambia nada
        assert respuesta.status_code == 200
    else:
        assert respuesta.status_code == 422
    assert _artefacto(client, admin, artefacto.id)["context_turns"] == 0


def test_crear_con_un_valor_invalido_da_422(client, mundo, admin, units):
    for valor in (-1, 11, 2.5, "x"):
        assert _crear(client, admin, units, context_turns=valor).status_code == 422


def test_una_cuenta_de_programa_lo_edita_en_su_programa_y_recibe_404_en_el_ajeno(
    client, mundo, as_user
):
    propio = client.patch(
        f"/artifacts/{mundo['comp'].id}", json={"context_turns": 3}, headers=as_user(COORD)
    )
    ajeno = client.patch(
        f"/artifacts/{mundo['adm'].id}", json={"context_turns": 3}, headers=as_user(COORD)
    )

    assert propio.status_code == 200 and propio.json()["context_turns"] == 3
    assert ajeno.status_code == 404


def test_un_cambio_deja_la_linea_con_el_valor_anterior_y_el_nuevo_y_otros_cambios_no(
    client, mundo, as_user, capsys
):
    capsys.readouterr()
    artefacto = mundo["comp"]
    headers = as_user(OPERADOR)

    client.patch(f"/artifacts/{artefacto.id}", json={"context_turns": 3}, headers=headers)
    client.patch(
        f"/artifacts/{artefacto.id}", json={"context_turns": 3}, headers=headers
    )  # mismo valor: sin cambio
    client.patch(f"/artifacts/{artefacto.id}", json={"description": "x"}, headers=headers)

    lineas = [l for l in _lineas(capsys) if l["action"] == "artifact.context_turns"]
    assert len(lineas) == 1
    assert (
        lineas[0]["actor"] == OPERADOR
        and lineas[0]["target"] == artefacto.id
        and lineas[0]["result"] == "ok"
    )
    assert lineas[0]["detail"] == "Consulta Computación: 0 -> 3"


def test_config_con_la_clave_del_artefacto_trae_la_memoria_y_rige_sin_reiniciar(
    client, mundo, admin
):
    artefacto = mundo["comp"]
    assert client.get("/config", headers=artefacto.headers).json()["artifact"]["context_turns"] == 0

    client.patch(f"/artifacts/{artefacto.id}", json={"context_turns": 5}, headers=admin)

    config = client.get("/config", headers=artefacto.headers).json()
    assert config["artifact"] == {
        "name": "Consulta Computación",
        "active": True,
        "context_turns": 5,
        "require_login": False,  # feature 015
    }


def test_config_sin_clave_no_cambia(client, mundo):
    assert "artifact" not in client.get("/config").json()
