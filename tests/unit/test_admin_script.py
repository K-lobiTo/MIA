import importlib.util
from pathlib import Path

import pytest

from mia.access.admins import find_active_admin

RAIZ_REPO = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("admin_script", RAIZ_REPO / "scripts" / "admin.py")
script = importlib.util.module_from_spec(spec)
spec.loader.exec_module(script)


@pytest.fixture
def correr(db, units, capsys):
    def _correr(*argv):
        codigo = script.main(list(argv), session_factory=db)
        salida = capsys.readouterr()
        return codigo, salida.out, salida.err

    return _correr


def test_agregar_global_y_listar(correr):
    codigo, salida, _ = correr("agregar", "Operador@itcr.ac.cr", "--global")
    assert codigo == 0 and "operador@itcr.ac.cr" in salida and "global" in salida
    codigo, salida, _ = correr("listar")
    assert codigo == 0 and "operador@itcr.ac.cr" in salida and "global" in salida and "activo" in salida


def test_agregar_con_unidades(correr, db):
    correr("agregar", "a@itcr.ac.cr", "--unidad", "Computación", "--unidad", "Administración de Empresas")
    _, salida, _ = correr("listar")
    assert "Administración de Empresas, Computación" in salida
    with db() as session:
        assert len(find_active_admin(session, "a@itcr.ac.cr").unit_ids) == 2


def test_desactivar_y_reactivar(correr, db):
    correr("agregar", "a@itcr.ac.cr", "--unidad", "Computación")
    codigo, salida, _ = correr("desactivar", "a@itcr.ac.cr")
    assert codigo == 0 and "ya no puede entrar" in salida
    _, salida, _ = correr("listar")
    assert "inactivo" in salida
    with db() as session:
        assert find_active_admin(session, "a@itcr.ac.cr") is None
    correr("agregar", "a@itcr.ac.cr", "--unidad", "Computación")
    with db() as session:
        assert find_active_admin(session, "a@itcr.ac.cr") is not None


def test_unidad_inexistente_se_rechaza_sin_guardar(correr, db):
    codigo, _, error = correr("agregar", "a@itcr.ac.cr", "--unidad", "Derecho")
    assert codigo == 1 and "No existe la unidad 'Derecho'" in error
    _, salida, _ = correr("listar")
    assert "No hay administradores" in salida


def test_correo_invalido_y_sin_alcance_se_rechazan(correr):
    codigo, _, error = correr("agregar", "sin-arroba", "--global")
    assert codigo == 1 and "no parece un correo" in error
    codigo, _, error = correr("agregar", "a@itcr.ac.cr")
    assert codigo == 1 and "Indica el alcance" in error


def test_desactivar_un_correo_desconocido(correr):
    codigo, _, error = correr("desactivar", "nadie@itcr.ac.cr")
    assert codigo == 1 and "No hay ningún administrador" in error


def test_avisa_si_no_queda_ningun_global_activo(correr):
    correr("agregar", "g@itcr.ac.cr", "--global")
    correr("agregar", "c@itcr.ac.cr", "--unidad", "Computación")
    _, salida, _ = correr("desactivar", "c@itcr.ac.cr")
    assert "Aviso" not in salida
    _, salida, _ = correr("desactivar", "g@itcr.ac.cr")
    assert "ya no queda ningún administrador global activo" in salida and "ADMIN_KEY" in salida
