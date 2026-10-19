"""Lista de equivalencias de siglas (feature 010): migración 0005, caché de lectura y rutas /equivalences."""

import json
from unittest.mock import patch

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from mia.config import settings
from mia.rag import equivalences as equivalences_module
from mia.rag.equivalences import get_equivalences, invalidate_equivalences
from mia.rag.lexical import Equivalence
from mia.storage.db import MIGRATIONS_DIR, init_db
from mia.storage.models import SiglaEquivalence

COORD = "coord.comp@itcr.ac.cr"
OPERADOR = "operador@itcr.ac.cr"


@pytest.fixture(autouse=True)
def cache_limpia():
    invalidate_equivalences()
    yield
    invalidate_equivalences()


def _revision(engine):
    with engine.connect() as connection:
        return connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()


def _alembic(engine, accion, destino):
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        getattr(command, accion)(config, destino)


# --- Migración 0005 -------------------------------------------------------------------------------------


def test_la_migracion_crea_la_tabla_con_las_semillas(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/m.db")
    init_db(engine)
    assert _revision(engine) == "0005"
    assert "sigla_equivalences" in inspect(engine).get_table_names()
    with Session(engine) as session:
        filas = {(r.sigla, r.form): r for r in session.scalars(select(SiglaEquivalence))}
    assert set(filas) == {
        ("tfg", "trabajo final de graduacion"),
        ("mgti", "gestion de tecnologias de informacion"),
        ("mgti", "gestion de tecnologias de la informacion"),
    }
    assert all(r.created_by == "automatizacion" for r in filas.values())
    assert filas[("tfg", "trabajo final de graduacion")].form_display == "Trabajo Final de Graduación"


def test_la_migracion_es_idempotente_y_el_par_repetido_viola_la_restriccion(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/m.db")
    init_db(engine)
    init_db(engine)
    with Session(engine) as session:
        assert len(list(session.scalars(select(SiglaEquivalence)))) == 3
        session.add(
            SiglaEquivalence(
                id="x", sigla="tfg", form="trabajo final de graduacion", sigla_display="TFG",
                form_display="otra", created_by="prueba",
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()


def test_downgrade_borra_solo_esa_tabla_y_no_toca_las_demas(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/m.db")
    init_db(engine)
    antes = set(inspect(engine).get_table_names())
    _alembic(engine, "downgrade", "0004")
    assert _revision(engine) == "0004"
    assert antes - set(inspect(engine).get_table_names()) == {"sigla_equivalences"}
    # Y se puede volver a subir.
    init_db(engine)
    assert _revision(engine) == "0005"


# --- Lectura con caché -------------------------------------------------------------------------------------


def test_la_lectura_devuelve_las_formas_normalizadas_y_usa_la_cache(db, monkeypatch):
    monkeypatch.setattr(settings, "hybrid_equivalences_ttl_seconds", 60)
    with db() as session:
        lista = get_equivalences(session)
        assert Equivalence("tfg", "trabajo final de graduacion") in lista
        session.add(
            SiglaEquivalence(
                id="n", sigla="pln", form="procesamiento de lenguaje natural", sigla_display="PLN",
                form_display="Procesamiento de Lenguaje Natural", created_by="prueba",
            )
        )
        session.commit()
        # Dentro del TTL no vuelve a consultar la base.
        assert Equivalence("pln", "procesamiento de lenguaje natural") not in get_equivalences(session)
        invalidate_equivalences()
        assert Equivalence("pln", "procesamiento de lenguaje natural") in get_equivalences(session)


def test_la_cache_vence_con_el_tiempo(db, monkeypatch):
    monkeypatch.setattr(settings, "hybrid_equivalences_ttl_seconds", 60)
    reloj = {"t": 100.0}
    monkeypatch.setattr(equivalences_module, "_now", lambda: reloj["t"])
    with db() as session:
        get_equivalences(session)
        session.add(
            SiglaEquivalence(
                id="n", sigla="pln", form="procesamiento de lenguaje natural", sigla_display="PLN",
                form_display="x", created_by="prueba",
            )
        )
        session.commit()
        reloj["t"] += 30
        assert len(get_equivalences(session)) == 3
        reloj["t"] += 31
        assert len(get_equivalences(session)) == 4


def test_con_ttl_cero_siempre_consulta(db, monkeypatch):
    monkeypatch.setattr(settings, "hybrid_equivalences_ttl_seconds", 0)
    with db() as session:
        get_equivalences(session)
        session.add(
            SiglaEquivalence(
                id="n", sigla="pln", form="procesamiento de lenguaje natural", sigla_display="PLN",
                form_display="x", created_by="prueba",
            )
        )
        session.commit()
        assert len(get_equivalences(session)) == 4


# --- Rutas ------------------------------------------------------------------------------------------------------


@pytest.fixture
def personas(db, units, make_admin):
    make_admin(COORD, units=["Computación"])
    make_admin(OPERADOR, global_=True)


def _crear(client, headers, sigla="PLN", form="Procesamiento de Lenguaje Natural"):
    return client.post("/equivalences", json={"sigla": sigla, "form": form}, headers=headers)


def test_la_lectura_exige_credencial_y_la_ven_todos_los_alcances(client, personas, as_user, admin):
    assert client.get("/equivalences").status_code == 401
    for headers in (as_user(COORD), as_user(OPERADOR), admin):
        respuesta = client.get("/equivalences", headers=headers)
        assert respuesta.status_code == 200
        lista = respuesta.json()["equivalences"]
        assert (lista[0]["sigla"], lista[0]["form"]) == ("MGTI", "Gestión de Tecnologías de Información")
        assert {e["sigla"] for e in lista} == {"MGTI", "TFG"}
        assert set(lista[0]) >= {"id", "sigla", "form", "created_by", "created_at", "updated_by", "updated_at"}


def test_crear_editar_y_borrar_son_solo_del_alcance_global(client, personas, as_user, capsys):
    coord = as_user(COORD)
    assert _crear(client, coord).status_code == 403
    assert _crear(client, coord).json()["code"] == "global_only"
    creada = _crear(client, as_user(OPERADOR)).json()
    assert client.patch(f"/equivalences/{creada['id']}", json={"form": "Otra forma"}, headers=coord).status_code == 403
    assert client.delete(f"/equivalences/{creada['id']}", headers=coord).status_code == 403
    lineas = [json.loads(l) for l in capsys.readouterr().out.splitlines() if l.startswith("{")]
    rechazados = [l for l in lineas if l["result"] == "rechazado"]
    assert {l["action"] for l in rechazados} == {"equivalence.create", "equivalence.update", "equivalence.delete"}


def test_crear_registra_autor_fecha_y_audita(client, personas, as_user, admin, capsys):
    respuesta = _crear(client, as_user(OPERADOR), sigla="p.l.n.", form="  Procesamiento   de Lenguaje Natural ")
    assert respuesta.status_code == 201
    cuerpo = respuesta.json()
    assert cuerpo["sigla"] == "p.l.n." and cuerpo["form"] == "Procesamiento   de Lenguaje Natural"
    assert cuerpo["created_by"] == OPERADOR and cuerpo["created_at"] and cuerpo["updated_by"] is None
    por_script = _crear(client, admin, sigla="TIC", form="Tecnologías de Información y Comunicación").json()
    assert por_script["created_by"] == "automatizacion"
    lineas = [json.loads(l) for l in capsys.readouterr().out.splitlines() if l.startswith("{")]
    assert [l["action"] for l in lineas if l["result"] == "ok"] == ["equivalence.create", "equivalence.create"]
    assert lineas[0]["actor"] == OPERADOR


def test_editar_registra_quien_y_cuando_y_borrar_da_204(client, personas, as_user):
    operador = as_user(OPERADOR)
    creada = _crear(client, operador).json()
    editada = client.patch(f"/equivalences/{creada['id']}", json={"form": "Procesamiento del Lenguaje"}, headers=operador)
    assert editada.status_code == 200
    assert editada.json()["form"] == "Procesamiento del Lenguaje" and editada.json()["sigla"] == "PLN"
    assert editada.json()["updated_by"] == OPERADOR and editada.json()["updated_at"]
    assert client.delete(f"/equivalences/{creada['id']}", headers=operador).status_code == 204
    assert client.delete(f"/equivalences/{creada['id']}", headers=operador).status_code == 404
    assert client.patch(f"/equivalences/{creada['id']}", json={"form": "x y z"}, headers=operador).status_code == 404


@pytest.mark.parametrize(
    ("sigla", "form", "campo"),
    [
        ("", "Procesamiento de lenguaje", "sigla"),
        ("   ", "Procesamiento de lenguaje", "sigla"),
        ("PL", "Procesamiento de lenguaje", "sigla"),
        ("P" * 21, "Procesamiento de lenguaje", "sigla"),
        ("PLN!", "Procesamiento de lenguaje", "sigla"),
        ("PLN", "", "forma"),
        ("PLN", "ab", "forma"),
        ("PLN", "de la en", "forma"),
        ("PLN", "x" * 121, "forma"),
        ("PLN", "pln", "forma"),
        ("PLN", "P.L.N.", "forma"),
    ],
)
def test_validacion_de_la_sigla_y_la_forma(client, personas, as_user, sigla, form, campo):
    respuesta = _crear(client, as_user(OPERADOR), sigla=sigla, form=form)
    assert respuesta.status_code == 422
    assert respuesta.json()["detail"].startswith(campo)


def test_un_par_repetido_da_409_aunque_cambien_mayusculas_tildes_o_espacios(client, personas, as_user):
    operador = as_user(OPERADOR)
    respuesta = _crear(client, operador, sigla="t.f.g", form="TRABAJO  final de   Graduación")
    assert respuesta.status_code == 409
    assert "TFG" in respuesta.json()["detail"] and "Trabajo Final de Graduación" in respuesta.json()["detail"]
    otra = _crear(client, operador, sigla="TFG", form="Tesis de grado").json()
    chocar = client.patch(
        f"/equivalences/{otra['id']}", json={"form": "trabajo final de graduacion"}, headers=operador
    )
    assert chocar.status_code == 409
    # Editarse a sí misma con los mismos valores no es un choque.
    assert client.patch(f"/equivalences/{otra['id']}", json={"form": "Tesis de grado"}, headers=operador).status_code == 200
    assert client.patch(f"/equivalences/{otra['id']}", json={}, headers=operador).status_code == 422


def test_cada_escritura_invalida_la_cache_de_la_consulta(client, personas, as_user, db, monkeypatch):
    monkeypatch.setattr(settings, "hybrid_equivalences_ttl_seconds", 600)
    with db() as session:
        assert len(get_equivalences(session)) == 3
    creada = _crear(client, as_user(OPERADOR)).json()
    with db() as session:
        assert Equivalence("pln", "procesamiento de lenguaje natural") in get_equivalences(session)
    client.delete(f"/equivalences/{creada['id']}", headers=as_user(OPERADOR))
    with db() as session:
        assert Equivalence("pln", "procesamiento de lenguaje natural") not in get_equivalences(session)


def test_la_lista_se_puede_editar_con_la_opcion_apagada(client, personas, as_user, monkeypatch):
    monkeypatch.setattr(settings, "query_hybrid_search", "off")
    with patch("mia.api.routes.equivalences.invalidate_equivalences") as invalidar:
        assert _crear(client, as_user(OPERADOR)).status_code == 201
    invalidar.assert_called_once()
