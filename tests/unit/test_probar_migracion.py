import importlib.util
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text

RAIZ_REPO = Path(__file__).resolve().parents[2]


def _cargar_script():
    spec = importlib.util.spec_from_file_location("probar_migracion", RAIZ_REPO / "scripts" / "probar_migracion.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


script = _cargar_script()

# La base tal como la dejó create_all antes de las migraciones, con datos (como la de producción).
ESQUEMA_ANTERIOR = [
    """CREATE TABLE domains (id VARCHAR NOT NULL, name VARCHAR NOT NULL, description VARCHAR NOT NULL,
        created_at DATETIME NOT NULL, PRIMARY KEY (id), UNIQUE (name))""",
    """CREATE TABLE documents (id VARCHAR NOT NULL, domain_id VARCHAR NOT NULL, filename VARCHAR NOT NULL,
        source_type VARCHAR NOT NULL, file_hash VARCHAR NOT NULL, status VARCHAR NOT NULL,
        uploaded_at DATETIME NOT NULL, PRIMARY KEY (id), FOREIGN KEY(domain_id) REFERENCES domains (id))""",
    "CREATE INDEX ix_documents_file_hash ON documents (file_hash)",
    "INSERT INTO domains VALUES ('d1', 'Memoria del Consejo', 'Actas', '2026-09-26 00:00:00')",
    "INSERT INTO documents VALUES ('doc1', 'd1', 'acta.pdf', 'pdf', 'h1', 'done', '2026-09-26 00:00:00')",
]


def _base_anterior(ruta) -> str:
    url = f"sqlite:///{ruta}"
    engine = create_engine(url)
    with engine.begin() as conexion:
        for sentencia in ESQUEMA_ANTERIOR:
            conexion.execute(text(sentencia))
    engine.dispose()
    return url


def test_migra_una_base_anterior_con_datos_y_todas_las_verificaciones_pasan(tmp_path, capsys):
    url = _base_anterior(tmp_path / "copia.db")

    resultado = script.probar(url)

    assert resultado.ok, [paso for paso in resultado.pasos if not paso[1]]
    nombres = [nombre for nombre, _, _ in resultado.pasos]
    assert "se conservan todos los datos" in nombres
    assert "se puede volver a la revisión 0001" in nombres and "se puede subir de nuevo a 0002" in nombres
    # Quedó migrada y con sus datos.
    engine = create_engine(url)
    with engine.connect() as conexion:
        assert conexion.execute(text("SELECT version_num FROM alembic_version")).scalar() == "0002"
        assert conexion.execute(text("SELECT name FROM domains")).scalar() == "Memoria del Consejo"
        assert conexion.execute(text("SELECT filename FROM documents")).scalar() == "acta.pdf"
    assert "Revisión: (ninguna" in capsys.readouterr().out


def test_la_prueba_de_nombres_no_deja_basura_en_la_base(tmp_path):
    url = _base_anterior(tmp_path / "copia.db")

    script.probar(url)

    engine = create_engine(url)
    with engine.connect() as conexion:
        assert conexion.execute(text("SELECT COUNT(*) FROM units")).scalar() == 0
        assert conexion.execute(text("SELECT COUNT(*) FROM domains")).scalar() == 1


def test_sin_ida_y_vuelta_deja_la_base_en_la_ultima_revision(tmp_path):
    url = _base_anterior(tmp_path / "copia.db")

    resultado = script.probar(url, ida_y_vuelta=False)

    assert resultado.ok
    assert not any("0001" in nombre for nombre, _, _ in resultado.pasos)


def test_una_base_vacia_tambien_migra(tmp_path):
    resultado = script.probar(f"sqlite:///{tmp_path}/vacia.db")

    assert resultado.ok
    assert "domains" in inspect(create_engine(f"sqlite:///{tmp_path}/vacia.db")).get_table_names()


def test_se_niega_a_correr_contra_la_base_de_produccion_sin_tocarla(tmp_path):
    url = _base_anterior(tmp_path / "produccion.db")

    resultado = script.probar(url, produccion=url)

    assert not resultado.ok and "NO es la de producción" in resultado.pasos[0][0]
    # No se migró nada.
    with create_engine(url).connect() as conexion:
        assert "alembic_version" not in inspect(conexion).get_table_names()
        assert "units" not in inspect(conexion).get_table_names()


@pytest.mark.parametrize(
    ("a", "b", "esperado"),
    [
        # Misma base con otra contraseña, con o sin el prefijo del driver: es la misma.
        ("postgresql://u:clave1@ep-prod.neon.tech/mia?sslmode=require", "postgresql+psycopg://u:otra@ep-prod.neon.tech/mia", True),
        # Una rama de Neon tiene otro servidor (endpoint): es otra base.
        ("postgresql://u:c@ep-rama-123.neon.tech/mia", "postgresql://u:c@ep-prod.neon.tech/mia", False),
        # Mismo servidor, otra base.
        ("postgresql://u:c@ep-prod.neon.tech/prueba", "postgresql://u:c@ep-prod.neon.tech/mia", False),
        ("sqlite:///a.db", "sqlite:///b.db", False),
    ],
)
def test_comparar_bases_ignora_la_clave_pero_no_el_servidor_ni_el_nombre(a, b, esperado):
    assert script.misma_base(a, b) is esperado


def test_la_linea_de_comandos_exige_confirmar_que_es_una_copia(tmp_path, monkeypatch, capsys):
    url = _base_anterior(tmp_path / "copia.db")
    monkeypatch.setattr(sys, "argv", ["probar_migracion.py", "--url", url])

    assert script.main() == 2
    assert "--es-una-copia" in capsys.readouterr().out
    with create_engine(url).connect() as conexion:
        assert "units" not in inspect(conexion).get_table_names()


def test_la_linea_de_comandos_se_niega_si_la_base_es_la_de_produccion(tmp_path, monkeypatch):
    url = _base_anterior(tmp_path / "produccion.db")
    entorno = tmp_path / ".env.produccion"
    entorno.write_text(f"DATABASE_URL={url}\n")
    monkeypatch.setattr(sys, "argv", ["probar_migracion.py", "--url", url, "--produccion", str(entorno), "--es-una-copia"])

    assert script.main() == 1
    with create_engine(url).connect() as conexion:
        assert "units" not in inspect(conexion).get_table_names()


def test_la_linea_de_comandos_con_una_copia_distinta_migra_y_termina_bien(tmp_path, monkeypatch, capsys):
    copia = _base_anterior(tmp_path / "copia.db")
    produccion = _base_anterior(tmp_path / "produccion.db")
    entorno = tmp_path / ".env.produccion"
    entorno.write_text(f"DATABASE_URL={produccion}\n")
    monkeypatch.setattr(sys, "argv", ["probar_migracion.py", "--url", copia, "--produccion", str(entorno), "--es-una-copia"])

    assert script.main() == 0
    assert "TODO BIEN" in capsys.readouterr().out
    with create_engine(produccion).connect() as conexion:  # la "producción" no se tocó
        assert "units" not in inspect(conexion).get_table_names()
