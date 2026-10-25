import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError

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

TABLAS_NUEVAS = {
    "units", "folders", "artifacts", "artifact_units", "artifact_domains", "queries", "admins", "admin_units",
    "sigla_equivalences", "bots", "bot_message_counts", "document_images",
}


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
    assert _revision(engine) == "0007"
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
    assert _revision(engine) == "0007"


def test_init_db_se_puede_correr_dos_veces(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/repetida.db")

    init_db(engine)
    init_db(engine)

    assert _revision(engine) == "0007"


def test_migracion_0003_crea_administradores_sin_tocar_datos(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/anterior.db")
    with engine.begin() as connection:
        for sentencia in ESQUEMA_ANTERIOR:
            connection.execute(text(sentencia))

    init_db(engine)

    columnas = {c["name"] for c in inspect(engine).get_columns("admins")}
    assert columnas == {"id", "email", "is_global", "active", "created_at", "updated_at"}
    assert {c["name"] for c in inspect(engine).get_columns("admin_units")} == {"admin_id", "unit_id"}
    with engine.connect() as connection:
        assert connection.execute(text("SELECT COUNT(*) FROM documents")).scalar_one() == 1


def _hasta(engine, revision, accion="upgrade"):
    from alembic import command
    from alembic.config import Config

    from mia.storage.db import MIGRATIONS_DIR

    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        getattr(command, accion)(config, revision)


def _nombres(engine):
    with engine.connect() as connection:
        return dict(connection.execute(text("SELECT id, name FROM units")).all())


def test_migracion_0004_renombra_las_dos_divisiones_sin_cambiar_ids(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/nombres.db")
    _hasta(engine, "0003")
    with engine.begin() as connection:
        connection.execute(text(
            "INSERT INTO units (id, name, description, created_at) VALUES "
            "('u1', 'Computación', 'Posgrados', '2026-10-08'), "
            "('u2', 'Administración de Empresas', 'Posgrados de Administración de Empresas (hoy, la Maestría en "
            "Analítica de Negocios, compartida con Computación)', '2026-10-08'), "
            "('u3', 'Otra', 'x', '2026-10-08')"
        ))

    _hasta(engine, "head")

    assert _nombres(engine) == {
        "u1": "Unidad de Postgrados de Computación",
        "u2": "Área académica de Analítica de Negocios",
        "u3": "Otra",
    }
    with engine.connect() as connection:
        assert connection.execute(text("SELECT description FROM units WHERE id='u1'")).scalar_one() == "Posgrados"
        assert "carrera de computación y administración de empresas" in connection.execute(
            text("SELECT description FROM units WHERE id='u2'")
        ).scalar_one()

    _hasta(engine, "0003", "downgrade")
    assert _nombres(engine) == {"u1": "Computación", "u2": "Administración de Empresas", "u3": "Otra"}


def test_migracion_0004_respeta_la_descripcion_editada_y_los_nombres_ya_cambiados(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/respeta.db")
    _hasta(engine, "0003")
    with engine.begin() as connection:
        connection.execute(text(
            "INSERT INTO units (id, name, description, created_at) VALUES "
            "('u1', 'Computación', '', '2026-10-08'), "
            "('u2', 'Administración de Empresas', 'Descripción propia', '2026-10-08'), "
            "('u3', 'Unidad de Postgrados de Computación', '', '2026-10-08')"
        ))

    _hasta(engine, "head")

    nombres = _nombres(engine)
    # Ya existía el nombre nuevo de Computación (u3): no se duplica ni se rompe la restricción única.
    assert nombres["u1"] == "Computación" and nombres["u3"] == "Unidad de Postgrados de Computación"
    assert nombres["u2"] == "Área académica de Analítica de Negocios"
    with engine.connect() as connection:
        assert connection.execute(text("SELECT description FROM units WHERE id='u2'")).scalar_one() == "Descripción propia"


def test_migracion_0004_en_una_base_vacia_no_hace_nada(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/vacia.db")
    init_db(engine)
    assert _nombres(engine) == {}


# --- Feature 011: bots de WhatsApp (0006) e imágenes de documentos (0007) ---------------------------------------


def _base_en(tmp_path, revision):
    """Base SQLite con el esquema anterior a las migraciones, llevada hasta `revision` y con un documento."""
    engine = create_engine(f"sqlite:///{tmp_path}/b.db")
    with engine.begin() as connection:
        for sentencia in ESQUEMA_ANTERIOR:
            connection.execute(text(sentencia))
    from alembic import command
    from alembic.config import Config

    from mia.storage.db import BASELINE_REVISION, MIGRATIONS_DIR

    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.stamp(config, BASELINE_REVISION)  # como init_db con una base anterior a las migraciones
    _hasta(engine, revision)
    return engine


def test_la_migracion_0006_crea_bots_y_consumo_mensual(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/nueva.db")

    init_db(engine)

    inspector = inspect(engine)
    assert {c["name"] for c in inspector.get_columns("bots")} == {
        "id", "name", "kapso_number_id", "artifact_id", "active", "created_at", "updated_at",
    }
    assert {c["name"] for c in inspector.get_columns("bot_message_counts")} == {
        "bot_id", "month", "received", "sent", "updated_at",
    }
    assert inspector.get_pk_constraint("bot_message_counts")["constrained_columns"] == ["bot_id", "month"]
    with engine.connect() as connection:
        assert connection.execute(text("SELECT COUNT(*) FROM bots")).scalar_one() == 0


def test_el_nombre_y_el_numero_de_kapso_de_un_bot_son_unicos(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/nueva.db")
    init_db(engine)
    fila = "INSERT INTO bots (id, name, kapso_number_id, active, created_at, updated_at) VALUES ({}, {}, {}, 1, '2026-10-24', '2026-10-24')"

    with engine.begin() as connection:
        connection.execute(text(fila.format("'b1'", "'Atracción'", "'111'")))
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(text(fila.format("'b2'", "'Atracción'", "'222'")))
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(text(fila.format("'b3'", "'Otro'", "'111'")))


def test_la_migracion_0007_crea_las_imagenes_de_documentos(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/nueva.db")

    init_db(engine)

    inspector = inspect(engine)
    assert {c["name"] for c in inspector.get_columns("document_images")} == {
        "id", "document_id", "public_id", "content_type", "content", "size_bytes", "caption", "position",
        "created_by", "created_at", "updated_at",
    }
    assert [i["name"] for i in inspector.get_indexes("document_images")] == ["ix_document_images_document_id_position"]
    fila = (
        "INSERT INTO document_images (id, document_id, public_id, content_type, content, size_bytes, caption, position, "
        "created_by, created_at, updated_at) VALUES ('i1', :doc, :public, 'image/png', x'89504e47', 4, '', 0, "
        "'automatizacion', '2026-10-24', '2026-10-24')"
    )
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO domains (id, name, description, created_at) VALUES ('d9', 'D', '', '2026-10-24')"))
        connection.execute(text(
            "INSERT INTO documents (id, domain_id, filename, source_type, file_hash, status, uploaded_at) "
            "VALUES ('doc9', 'd9', 'a.pdf', 'pdf', 'h', 'done', '2026-10-24')"
        ))
        connection.execute(text(fila), {"doc": "doc9", "public": "p" * 32})
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(text(fila.replace("'i1'", "'i2'")), {"doc": "doc9", "public": "p" * 32})


def test_subir_a_la_0007_sobre_una_base_en_la_0005_no_pierde_datos(tmp_path):
    engine = _base_en(tmp_path, "0005")
    assert _revision(engine) == "0005"

    _hasta(engine, "head")

    assert _revision(engine) == "0007"
    with engine.connect() as connection:
        assert connection.execute(text("SELECT filename FROM documents")).scalar_one() == "acta.pdf"
        assert connection.execute(text("SELECT name FROM domains")).scalar_one() == "Memoria del Consejo"


def test_bajar_a_la_0005_borra_solo_las_tablas_nuevas_y_se_puede_volver_a_subir(tmp_path):
    engine = _base_en(tmp_path, "head")

    _hasta(engine, "0005", accion="downgrade")

    tablas = set(inspect(engine).get_table_names())
    assert not ({"bots", "bot_message_counts", "document_images"} & tablas)
    assert {"documents", "artifacts", "sigla_equivalences"} <= tablas
    assert _revision(engine) == "0005"
    with engine.connect() as connection:
        assert connection.execute(text("SELECT COUNT(*) FROM documents")).scalar_one() == 1

    _hasta(engine, "head")

    assert _revision(engine) == "0007"
    assert {"bots", "bot_message_counts", "document_images"} <= set(inspect(engine).get_table_names())
