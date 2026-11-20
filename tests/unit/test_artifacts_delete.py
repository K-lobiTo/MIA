"""Eliminar un artefacto desde el panel: DELETE /artifacts/{id}."""

import json
import uuid
from decimal import Decimal

import pytest

from mia.storage.models import (
    Artifact,
    ArtifactDomain,
    ArtifactUnit,
    Bot,
    Domain,
    QueryLog,
    ResponseTemplate,
)
from tests.unit.chat_de_prueba import iniciar_sesion
from tests.unit.plantillas_de_prueba import plantilla_del_artefacto, plantilla_personal


@pytest.fixture
def artefacto(db, modes_config, make_artifact, units):
    with db() as session:
        session.add(Domain(id="d1", unit_id=units.comp, name="Currículum"))
        session.commit()
    art = make_artifact("Consulta", units=[units.comp], domains=["d1"], modes="literal,razonamiento,plantilla")
    return art


def _filas(db, modelo, **filtros):
    with db() as session:
        return session.query(modelo).filter_by(**filtros).count()


def test_elimina_el_artefacto_su_acceso_y_su_clave_deja_de_funcionar(client, db, admin, artefacto):
    assert client.get("/config", headers=artefacto.headers).status_code == 200

    respuesta = client.delete(f"/artifacts/{artefacto.id}", headers=admin)

    assert respuesta.status_code == 204
    assert _filas(db, Artifact, id=artefacto.id) == 0
    assert _filas(db, ArtifactUnit, artifact_id=artefacto.id) == 0
    assert _filas(db, ArtifactDomain, artifact_id=artefacto.id) == 0
    assert client.get("/config", headers=artefacto.headers).status_code == 401
    nombres = [a["name"] for a in client.get("/artifacts", headers=admin).json()["artifacts"]]
    assert "Consulta" not in nombres


def test_conserva_el_registro_de_consultas_sin_artefacto(client, db, admin, artefacto):
    with db() as session:
        session.add(QueryLog(id=str(uuid.uuid4()), artifact_id=artefacto.id, question="p", mode="razonamiento",
                             outcome="answered", cost_usd=Decimal("0.05"), model="m"))
        session.commit()

    client.delete(f"/artifacts/{artefacto.id}", headers=admin)

    with db() as session:
        (consulta,) = session.query(QueryLog).all()
        assert consulta.artifact_id is None and consulta.cost_usd == Decimal("0.05")
    # El gasto de hoy de toda la API sigue contando esa consulta.
    from mia.access.caps import spent_today

    with db() as session:
        assert spent_today(session) == Decimal("0.05")


def test_elimina_sus_plantillas_y_las_personales_limitadas_a_el_pero_no_las_de_todos(client, db, admin, artefacto, make_artifact):
    otro = make_artifact("Otro", modes="literal,razonamiento,plantilla")
    ana = iniciar_sesion(db)["uid"]
    plantilla_del_artefacto(db, artefacto.id, "Del artefacto")
    plantilla_personal(db, ana, "Solo aqui", artifact_id=artefacto.id)
    para_todos = plantilla_personal(db, ana, "Para todos")
    plantilla_del_artefacto(db, otro.id, "Del otro")

    client.delete(f"/artifacts/{artefacto.id}", headers=admin)

    with db() as session:
        assert sorted(t.name for t in session.query(ResponseTemplate)) == ["Del otro", "Para todos"]
        assert session.get(ResponseTemplate, para_todos) is not None


def test_con_un_bot_asignado_se_rechaza_y_no_se_borra_nada(client, db, admin, artefacto):
    with db() as session:
        session.add(Bot(id=str(uuid.uuid4()), name="Bot", kapso_number_id="111", artifact_id=artefacto.id, active=True))
        session.commit()
    plantilla_del_artefacto(db, artefacto.id)

    respuesta = client.delete(f"/artifacts/{artefacto.id}", headers=admin)

    assert respuesta.status_code == 409
    assert "1 bot" in respuesta.json()["detail"] and "módulo Bots" in respuesta.json()["detail"]
    assert _filas(db, Artifact, id=artefacto.id) == 1 and _filas(db, ResponseTemplate) == 1


def test_inexistente_responde_404_y_exige_administracion(client, admin, artefacto):
    assert client.delete("/artifacts/no-existe", headers=admin).status_code == 404
    assert client.delete(f"/artifacts/{artefacto.id}").status_code == 401
    assert client.delete(f"/artifacts/{artefacto.id}", headers=artefacto.headers).status_code == 401


def test_una_cuenta_de_otro_programa_recibe_404_y_una_con_alcance_si_puede(client, db, make_admin, as_user, units, make_artifact, modes_config):
    ajeno = make_artifact("Ajeno", units=[units.adm])
    propio = make_artifact("Propio", units=[units.comp])
    make_admin("coord.comp@itcr.ac.cr", units=["Computación"])
    headers = as_user("coord.comp@itcr.ac.cr")

    assert client.delete(f"/artifacts/{ajeno.id}", headers=headers).status_code == 404
    assert _filas(db, Artifact, id=ajeno.id) == 1
    assert client.delete(f"/artifacts/{propio.id}", headers=headers).status_code == 204


def test_queda_en_el_registro_de_administracion_sin_datos_sensibles(client, admin, artefacto, capsys):
    client.delete(f"/artifacts/{artefacto.id}", headers=admin)

    lineas = [json.loads(linea) for linea in capsys.readouterr().out.splitlines() if linea.startswith("{")]
    (linea,) = [x for x in lineas if x["action"] == "artifact.delete"]
    assert linea["target"] == artefacto.id and linea["detail"] == "Consulta" and linea["result"] == "ok"
    assert artefacto.key not in json.dumps(linea)


def test_se_puede_crear_otro_con_el_mismo_nombre(client, admin, artefacto):
    client.delete(f"/artifacts/{artefacto.id}", headers=admin)

    nuevo = client.post("/artifacts", json={"name": "Consulta", "access": {"all_domains": True}, "modes": ["literal"]}, headers=admin)

    assert nuevo.status_code == 201

