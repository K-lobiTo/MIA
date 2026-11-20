"""Ningún dato real de personas en el repositorio (feature 021, FR-017 y SC-007) y el aviso de la carga por carpeta."""

import importlib.util
import re
import subprocess
from pathlib import Path

import pytest

from tests.unit.csv_de_prueba import csv_bytes, csv_como_el_real, tabla_inventada

RAIZ = Path(__file__).resolve().parents[2]
CORREO = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")


def test_ningun_csv_esta_versionado_en_el_repositorio():
    try:
        salida = subprocess.run(["git", "ls-files", "*.csv"], cwd=RAIZ, capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("no hay un repositorio de git")

    assert salida.split() == []


def test_los_datos_de_los_generadores_son_inventados():
    textos = [
        csv_como_el_real().decode("cp1252"),
        csv_bytes(tabla_inventada(5), separador=",", codificacion="utf-8").decode(),
    ]
    for texto in textos:
        for correo in CORREO.findall(texto):
            assert correo.endswith("@ejemplo.test"), correo
        # Cédulas y celulares son solo ceros, nunca un número de verdad.
        assert not re.search(r"\b[1-9]-\d{4}-\d{4}\b", texto)
        assert not re.search(r"\b[2-8]\d{3}-\d{4}\b", texto)
    assert "0-0000-0000" in textos[0] and "0000-0000" in textos[0]


def _cargar_script():
    spec = importlib.util.spec_from_file_location("cargar_carpeta", RAIZ / "scripts" / "cargar_carpeta.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def test_cargar_carpeta_avisa_una_sola_vez_de_los_datos_personales_si_hay_csv(tmp_path, capsys):
    script = _cargar_script()
    (tmp_path / "a.csv").write_bytes(b"x")
    (tmp_path / "b.CSV").write_bytes(b"x")
    (tmp_path / "c.pdf").write_bytes(b"x")

    script.avisar_si_hay_csv(sorted(tmp_path.iterdir()))

    salida = capsys.readouterr().out
    assert salida.count("Aviso: hay archivos CSV en la carpeta.") == 1
    assert "cédulas, correos, teléfonos" in salida and "anonimiza" in salida


def test_cargar_carpeta_no_avisa_sin_csv(tmp_path, capsys):
    script = _cargar_script()
    (tmp_path / "c.pdf").write_bytes(b"x")

    script.avisar_si_hay_csv(sorted(tmp_path.iterdir()))

    assert capsys.readouterr().out == ""
