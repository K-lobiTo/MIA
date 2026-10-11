"""Reglas de alcance por unidad (sin HTTP)."""

import uuid

from mia.access.scope import (
    AUTOMATION,
    Principal,
    artifact_ids_in_scope,
    artifact_in_scope,
    can_grant_access,
    domain_in_scope,
    unit_in_scope,
)
from mia.storage.models import Artifact, Domain

GLOBAL = Principal(email="g@itcr.ac.cr", is_global=True)


def comp(units):
    return Principal(email="c@itcr.ac.cr", is_global=False, unit_ids=frozenset({units.comp}))


def _domain(db, unit_id, name="Dominio"):
    domain_id = str(uuid.uuid4())
    with db() as session:
        session.add(Domain(id=domain_id, unit_id=unit_id, name=name))
        session.commit()
    return domain_id


def test_global_y_automatizacion_ven_todo(db, units, make_artifact):
    domain = _domain(db, None)
    artifact = make_artifact(all_domains=True)
    with db() as session:
        assert unit_in_scope(GLOBAL, units.adm)
        assert domain_in_scope(AUTOMATION, session.get(Domain, domain))
        assert artifact_in_scope(session, GLOBAL, session.get(Artifact, artifact.id))
        assert artifact_ids_in_scope(session, GLOBAL) is None
    assert AUTOMATION.label == "automatizacion"


def test_unidad_ve_su_dominio_y_no_el_ajeno_ni_el_sin_unidad(db, units):
    propio = _domain(db, units.comp, "Propio")
    ajeno = _domain(db, units.adm, "Ajeno")
    sin_unidad = _domain(db, None, "Antiguo")
    principal = comp(units)
    with db() as session:
        assert domain_in_scope(principal, session.get(Domain, propio))
        assert not domain_in_scope(principal, session.get(Domain, ajeno))
        assert not domain_in_scope(principal, session.get(Domain, sin_unidad))
    assert unit_in_scope(principal, units.comp) and not unit_in_scope(principal, units.adm)
    assert not unit_in_scope(principal, None)


def test_artefacto_de_la_unidad_esta_en_alcance_y_los_demas_no(db, units, make_artifact):
    propio = make_artifact("Propio", units=[units.comp])
    ajeno = make_artifact("Ajeno", units=[units.adm])
    todos = make_artifact("Todos", all_domains=True)
    mezcla = make_artifact("Mezcla", units=[units.comp, units.adm])
    dominio_ajeno = _domain(db, units.adm)
    puntual_ajeno = make_artifact("Puntual ajeno", domains=[dominio_ajeno])
    dominio_propio = _domain(db, units.comp, "Otro")
    puntual_propio = make_artifact("Puntual propio", domains=[dominio_propio])
    sin_acceso = make_artifact("Sin acceso")
    principal = comp(units)
    with db() as session:
        ids = set(artifact_ids_in_scope(session, principal))
        assert ids == {propio.id, puntual_propio.id}
        for artifact in (ajeno, todos, mezcla, puntual_ajeno, sin_acceso):
            assert not artifact_in_scope(session, principal, session.get(Artifact, artifact.id))


def test_lista_vacia_significa_ninguno_y_none_todos(db, units):
    with db() as session:
        assert artifact_ids_in_scope(session, comp(units)) == []
        assert artifact_ids_in_scope(session, GLOBAL) is None


def test_dar_acceso_dentro_del_alcance(db, units):
    propio = _domain(db, units.comp, "Propio")
    ajeno = _domain(db, units.adm, "Ajeno")
    ambas = Principal(email="x@itcr.ac.cr", is_global=False, unit_ids=frozenset({units.comp, units.adm}))
    with db() as session:
        principal = comp(units)
        assert can_grant_access(session, principal, False, [units.comp], [propio])
        assert not can_grant_access(session, principal, True, [], [])
        assert not can_grant_access(session, principal, False, [units.adm], [])
        assert not can_grant_access(session, principal, False, [units.comp], [ajeno])
        assert can_grant_access(session, ambas, False, [units.comp, units.adm], [])
        assert not can_grant_access(session, ambas, True, [], [])
        assert can_grant_access(session, GLOBAL, True, [], [])
