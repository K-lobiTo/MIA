import importlib.util
from pathlib import Path

import pytest

RAIZ_REPO = Path(__file__).resolve().parents[2]


def _cargar_script():
    spec = importlib.util.spec_from_file_location("servicios", RAIZ_REPO / "scripts" / "servicios.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


servicios = _cargar_script()


def nombres(lista):
    return [s.nombre for s in lista]


def test_sin_nombres_se_eligen_los_cuatro_con_la_api_primero():
    assert nombres(servicios.seleccionar([])) == ["MIA", "mia-computacion", "mia-administracion", "mia-panel"]


def test_al_apagar_se_invierte_el_orden_y_la_api_queda_al_final():
    assert nombres(servicios.seleccionar([], invertir=True))[-1] == "MIA"


def test_se_respeta_el_orden_de_los_servicios_y_no_el_de_la_linea_de_comandos():
    assert nombres(servicios.seleccionar(["mia-panel", "MIA"])) == ["MIA", "mia-panel"]


def test_los_nombres_no_distinguen_mayusculas():
    assert nombres(servicios.seleccionar(["mia", "MIA-PANEL"])) == ["MIA", "mia-panel"]


def test_un_nombre_repetido_no_duplica_el_servicio():
    assert nombres(servicios.seleccionar(["mia-panel", "mia-panel"])) == ["mia-panel"]


def test_un_nombre_desconocido_da_un_error_con_los_validos():
    with pytest.raises(ValueError) as error:
        servicios.seleccionar(["otro"])
    assert "otro" in str(error.value) and "mia-computacion" in str(error.value)


def test_cada_servicio_tiene_su_direccion_https_sin_barra_final():
    for servicio in servicios.SERVICIOS:
        assert servicio.url.startswith("https://") and not servicio.url.endswith("/")


# --- Desplegar lo publicado (git) y no la carpeta local ---


def _repo_con_commit(tmp_path):
    import subprocess

    repo = tmp_path / "repo"
    repo.mkdir()
    ejecutar = lambda *a: subprocess.run(["git", *a], cwd=repo, check=True, capture_output=True)
    ejecutar("init", "-q", "-b", "main")
    ejecutar("config", "user.email", "t@t")
    ejecutar("config", "user.name", "t")
    (repo / "api.txt").write_text("version publicada")
    (repo / ".gitignore").write_text("secreto.env\n")
    ejecutar("add", ".")
    ejecutar("commit", "-q", "-m", "Version publicada")
    return repo


def test_exportar_ref_deja_solo_lo_versionado_de_esa_referencia(tmp_path):
    repo = _repo_con_commit(tmp_path)
    (repo / "api.txt").write_text("cambio sin commitear")
    (repo / "secreto.env").write_text("ADMIN_KEY=no-subir")
    (repo / "nuevo.txt").write_text("sin versionar")

    destino = tmp_path / "salida" / "codigo"
    destino.parent.mkdir()
    servicios.exportar_ref("main", destino, repo=repo)

    assert (destino / "api.txt").read_text() == "version publicada"
    assert not (destino / "secreto.env").exists() and not (destino / "nuevo.txt").exists()
    assert not (destino / ".git").exists()
    assert not (destino.parent / "codigo.tar").exists()


def test_resolver_ref_da_el_commit_y_su_asunto_y_falla_si_no_existe(tmp_path):
    repo = _repo_con_commit(tmp_path)
    commit, asunto = servicios.resolver_ref("main", repo=repo)
    assert len(commit) == 9 and asunto == "Version publicada"
    with pytest.raises(RuntimeError):
        servicios.resolver_ref("origin/no-existe", repo=repo)


def test_por_defecto_se_despliega_origin_main():
    assert servicios.REF_POR_DEFECTO == "origin/main"
