"""El prompt propio de cada artefacto: alcance, límite, auditoría y que no llegue a los clientes."""

import json

import pytest

from mia.rag.llm import MAX_CUSTOM_PROMPT_CHARS
from mia.storage.models import Domain

COORD = "coord.comp@itcr.ac.cr"
OPERADOR = "operador@itcr.ac.cr"
TEXTO = "Responde centrándote en la información del propio programa."


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


def _artefacto(client, headers, artifact_id):
    return next(
        a for a in client.get("/artifacts", headers=headers).json()["artifacts"] if a["id"] == artifact_id
    )


def test_los_artefactos_nacen_sin_prompt_propio(client, mundo, admin):
    assert _artefacto(client, admin, mundo["comp"].id)["custom_prompt"] == ""


def test_se_puede_crear_con_prompt_y_cambiarlo_o_borrarlo(client, mundo, admin, units):
    creado = client.post(
        "/artifacts",
        json={
            "name": "Nueva",
            "access": {"all_domains": False, "unit_ids": [units.comp], "domain_ids": []},
            "modes": ["literal"],
            "custom_prompt": f"  {TEXTO}\n ",
        },
        headers=admin,
    )
    assert creado.status_code == 201 and creado.json()["custom_prompt"] == TEXTO

    ruta = f"/artifacts/{creado.json()['id']}"
    assert client.patch(ruta, json={"custom_prompt": "Otro texto."}, headers=admin).json()["custom_prompt"] == "Otro texto."
    # Editar otra cosa no toca el prompt.
    assert client.patch(ruta, json={"description": "x"}, headers=admin).json()["custom_prompt"] == "Otro texto."
    assert client.patch(ruta, json={"custom_prompt": ""}, headers=admin).json()["custom_prompt"] == ""


def test_el_prompt_tiene_un_largo_maximo(client, mundo, admin):
    ruta = f"/artifacts/{mundo['comp'].id}"
    assert client.patch(ruta, json={"custom_prompt": "a" * MAX_CUSTOM_PROMPT_CHARS}, headers=admin).status_code == 200
    assert client.patch(ruta, json={"custom_prompt": "a" * (MAX_CUSTOM_PROMPT_CHARS + 1)}, headers=admin).status_code == 422


def test_quien_administra_una_unidad_solo_cambia_el_prompt_de_lo_suyo(client, mundo, as_user):
    coord = as_user(COORD)
    assert client.patch(f"/artifacts/{mundo['comp'].id}", json={"custom_prompt": TEXTO}, headers=coord).status_code == 200
    ajeno = client.patch(f"/artifacts/{mundo['adm'].id}", json={"custom_prompt": TEXTO}, headers=coord)
    assert ajeno.status_code == 404


def test_el_cambio_queda_en_la_auditoria_sin_copiar_el_texto(client, mundo, admin, capsys):
    capsys.readouterr()
    client.patch(f"/artifacts/{mundo['comp'].id}", json={"custom_prompt": TEXTO}, headers=admin)
    lineas = [json.loads(l) for l in capsys.readouterr().out.splitlines() if l.startswith("{")]
    cambio = next(l for l in lineas if l.get("action") == "artifact.custom_prompt")
    assert f"0 -> {len(TEXTO)} caracteres" in json.dumps(cambio)
    assert TEXTO not in json.dumps(cambio)


def test_el_prompt_no_se_expone_a_la_aplicacion_de_consulta(client, mundo):
    respuesta = client.get("/config", headers=mundo["comp"].headers)
    assert respuesta.status_code == 200 and "custom_prompt" not in respuesta.text
