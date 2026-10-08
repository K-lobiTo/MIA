from sqlalchemy import create_engine, inspect, text

from mia.storage.db import init_db

# Esquema y datos tal como los dejaba `create_all` antes de las migraciones (producción en Neon).
ESQUEMA_ANTERIOR = [
    """CREATE TABLE domains (
        id VARCHAR NOT NULL, name VARCHAR NOT NULL, description VARCHAR NOT NULL,
        created_at DATETIME NOT NULL, PRIMARY KEY (id), UNIQUE (name))""",
    """CREATE TABLE documents (
        id VARCHAR NOT NULL, domain_id VARCHAR NOT NULL, filename VARCHAR NOT NULL,
        source_type VARCHAR NOT NULL, file_hash VARCHAR NOT NULL, status VARCHAR NOT NULL,
        uploaded_at DATETIME NOT NULL, PRIMARY KEY (id), FOREIGN KEY(domain_id) REFERENCES domains (id))""",
    "CREATE INDEX ix_documents_file_hash ON documents (file_hash)",
    "INSERT INTO domains VALUES ('d1', 'Memoria del Consejo', 'Actas', '2026-09-26 00:00:00')",
    "INSERT INTO documents VALUES ('doc1', 'd1', 'acta.pdf', 'pdf', 'h1', 'done', '2026-09-26 00:00:00')",
]

TABLAS_NUEVAS = {"units", "folders", "artifacts", "artifact_units", "artifact_domains", "queries"}


def _revision(engine) -> str:
    with engine.connect() as connection:
        return connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()


def test_base_anterior_se_migra_sin_perder_datos(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/anterior.db")
    with engine.begin() as connection:
        for sentencia in ESQUEMA_ANTERIOR:
            connection.execute(text(sentencia))

    init_db(engine)

    inspector = inspect(engine)
    assert TABLAS_NUEVAS <= set(inspector.get_table_names())
    assert "unit_id" in {c["name"] for c in inspector.get_columns("domains")}
    assert "folder_id" in {c["name"] for c in inspector.get_columns("documents")}
    assert _revision(engine) == "0002"
    with engine.connect() as connection:
        assert connection.execute(text("SELECT name, unit_id FROM domains")).one() == (
            "Memoria del Consejo",
            None,
        )
        assert connection.execute(text("SELECT filename, status, folder_id FROM documents")).one() == (
            "acta.pdf",
            "done",
            None,
        )


def test_nombre_de_dominio_pasa_a_ser_unico_por_unidad(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/anterior.db")
    with engine.begin() as connection:
        for sentencia in ESQUEMA_ANTERIOR:
            connection.execute(text(sentencia))
    init_db(engine)

    with engine.begin() as connection:
        connection.execute(text("INSERT INTO units (id, name, description, created_at) VALUES ('u1', 'Computación', '', '2026-10-08'), ('u2', 'Administración de Empresas', '', '2026-10-08')"))
        # El mismo nombre en unidades distintas ya es posible (antes el nombre era único global).
        connection.execute(text("INSERT INTO domains VALUES ('d2', 'Currículum', '', '2026-10-08', 'u1')"))
        connection.execute(text("INSERT INTO domains VALUES ('d3', 'Currículum', '', '2026-10-08', 'u2')"))
        assert connection.execute(text("SELECT COUNT(*) FROM domains WHERE name = 'Currículum'")).scalar_one() == 2


def test_base_vacia_queda_en_la_ultima_revision(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/nueva.db")

    init_db(engine)

    assert TABLAS_NUEVAS <= set(inspect(engine).get_table_names())
    assert _revision(engine) == "0002"


def test_init_db_se_puede_correr_dos_veces(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/repetida.db")

    init_db(engine)
    init_db(engine)

    assert _revision(engine) == "0002"
