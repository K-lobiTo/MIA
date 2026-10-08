from decimal import Decimal

from mia.access.permissions import allowed_domain_ids, allowed_modes
from mia.storage.models import Artifact, ArtifactDomain, ArtifactUnit, Domain, Unit


def _sembrar(db):
    with db() as session:
        session.add_all([Unit(id="u1", name="Computación"), Unit(id="u2", name="Administración de Empresas")])
        session.flush()
        session.add_all(
            [
                Domain(id="d1", unit_id="u1", name="Currículum"),
                Domain(id="d2", unit_id="u1", name="Docentes"),
                Domain(id="d3", unit_id="u2", name="Currículum"),
                Domain(id="d4", unit_id=None, name="Suelto"),
            ]
        )
        session.commit()


def _artefacto(db, *, todos=False, unidades=(), dominios=(), activo=True, modos="literal"):
    with db() as session:
        session.add(
            Artifact(id="a", name="A", key_hash="h", key_prefix="mia_xxxx", active=activo, all_domains=todos,
                     modes=modos, daily_cap_usd=Decimal("0.5"))
        )
        session.flush()
        session.add_all([ArtifactUnit(artifact_id="a", unit_id=u) for u in unidades])
        session.add_all([ArtifactDomain(artifact_id="a", domain_id=d) for d in dominios])
        session.commit()
        return allowed_domain_ids(session, session.get(Artifact, "a")), session.get(Artifact, "a")


def test_todos_los_dominios_incluye_los_que_no_tienen_unidad(db):
    _sembrar(db)
    permitidos, _ = _artefacto(db, todos=True)
    assert permitidos == {"d1", "d2", "d3", "d4"}


def test_una_unidad_completa_incluye_sus_dominios(db):
    _sembrar(db)
    permitidos, _ = _artefacto(db, unidades=["u1"])
    assert permitidos == {"d1", "d2"}


def test_un_dominio_creado_despues_en_la_unidad_queda_permitido(db):
    _sembrar(db)
    permitidos, artefacto = _artefacto(db, unidades=["u1"])
    assert "d-nuevo" not in permitidos
    with db() as session:
        session.add(Domain(id="d-nuevo", unit_id="u1", name="Nuevo"))
        session.commit()
        assert "d-nuevo" in allowed_domain_ids(session, session.get(Artifact, artefacto.id))


def test_dominios_puntuales(db):
    _sembrar(db)
    permitidos, _ = _artefacto(db, dominios=["d3"])
    assert permitidos == {"d3"}


def test_unidades_y_dominios_combinados_sin_duplicados(db):
    _sembrar(db)
    permitidos, _ = _artefacto(db, unidades=["u1"], dominios=["d1", "d3"])
    assert permitidos == {"d1", "d2", "d3"}


def test_artefacto_desactivado_no_tiene_acceso(db):
    _sembrar(db)
    permitidos, _ = _artefacto(db, todos=True, activo=False)
    assert permitidos == set()


def test_modos_permitidos_en_orden_y_sin_valores_invalidos(db):
    _sembrar(db)
    _, artefacto = _artefacto(db, todos=True, modos="razonamiento,literal,inventado")
    assert allowed_modes(artefacto) == ["razonamiento", "literal"]
