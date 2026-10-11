"""Lista de administradores (sin HTTP)."""

import pytest

from mia.access.admins import (
    add_admin,
    deactivate_admin,
    find_active_admin,
    has_active_global,
    list_admins,
    normalize_email,
)
from mia.storage.models import Admin, AdminUnit


def test_normaliza_mayusculas_y_espacios():
    assert normalize_email("  Persona@ITCR.ac.cr ") == "persona@itcr.ac.cr"


@pytest.mark.parametrize("texto", ["sin-arroba", "@itcr.ac.cr", "persona@", "dos palabras@itcr.ac.cr", ""])
def test_rechaza_correos_invalidos(texto):
    with pytest.raises(ValueError):
        normalize_email(texto)


def test_sin_alcance_o_con_alcance_doble_se_rechaza(db, units):
    with db() as session:
        with pytest.raises(ValueError, match="alcance"):
            add_admin(session, "a@itcr.ac.cr", is_global=False, unit_names=[])
        with pytest.raises(ValueError, match="no ambos"):
            add_admin(session, "a@itcr.ac.cr", is_global=True, unit_names=["Computación"])
        assert list_admins(session) == []


def test_unidad_inexistente_no_guarda_nada(db, units):
    with db() as session:
        with pytest.raises(ValueError, match="No existe la unidad 'Derecho'"):
            add_admin(session, "a@itcr.ac.cr", is_global=False, unit_names=["Computación", "Derecho"])
        assert list_admins(session) == []


def test_agregar_de_nuevo_actualiza_el_alcance_y_reactiva(db, units):
    with db() as session:
        add_admin(session, "A@itcr.ac.cr", is_global=False, unit_names=["Computación"])
        deactivate_admin(session, "a@itcr.ac.cr")
        assert find_active_admin(session, "a@itcr.ac.cr") is None
        add_admin(session, "a@ITCR.ac.cr", is_global=False, unit_names=["Administración de Empresas"])
        [info] = list_admins(session)
        assert info.active and info.units == ["Administración de Empresas"]
        principal = find_active_admin(session, "A@itcr.ac.cr")
        assert principal.unit_ids == frozenset({units.adm}) and not principal.is_global


def test_desactivar_conserva_el_registro(db, units):
    with db() as session:
        add_admin(session, "a@itcr.ac.cr", is_global=False, unit_names=["Computación"])
        deactivate_admin(session, "a@itcr.ac.cr")
        [info] = list_admins(session)
        assert not info.active and info.units == ["Computación"]
        with pytest.raises(ValueError, match="No hay ningún administrador"):
            deactivate_admin(session, "otra@itcr.ac.cr")


def test_global_no_guarda_unidades_y_pasa_a_unidades_las_reemplaza(db, units):
    with db() as session:
        add_admin(session, "g@itcr.ac.cr", is_global=True, unit_names=[])
        assert session.query(AdminUnit).count() == 0
        assert find_active_admin(session, "g@itcr.ac.cr").is_global
        assert has_active_global(session)
        add_admin(session, "g@itcr.ac.cr", is_global=False, unit_names=["Computación"])
        assert not find_active_admin(session, "g@itcr.ac.cr").is_global
        assert not has_active_global(session)
        assert session.query(Admin).count() == 1
