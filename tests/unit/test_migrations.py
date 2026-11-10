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
    assert _revision(engine) == "0011"
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
        connection.execute(text("INSERT INTO domains (id, name, description, created_at, unit_id) VALUES ('d2', 'Currículum', '', '2026-10-08', 'u1')"))
        connection.execute(text("INSERT INTO domains (id, name, description, created_at, unit_id) VALUES ('d3', 'Currículum', '', '2026-10-08', 'u2')"))
        assert connection.execute(text("SELECT COUNT(*) FROM domains WHERE name = 'Currículum'")).scalar_one() == 2


def test_base_vacia_queda_en_la_ultima_revision(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/nueva.db")

    init_db(engine)

    assert TABLAS_NUEVAS <= set(inspect(engine).get_table_names())
    assert _revision(engine) == "0011"


def test_init_db_se_puede_correr_dos_veces(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/repetida.db")

    init_db(engine)
    init_db(engine)

    assert _revision(engine) == "0011"


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
        "id",
        "name",
        "kapso_number_id",
        "artifact_id",
        "active",
        "context_turns",
        "created_at",
        "updated_at",
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


def test_subir_a_la_cabeza_sobre_una_base_en_la_0005_no_pierde_datos(tmp_path):
    engine = _base_en(tmp_path, "0005")
    assert _revision(engine) == "0005"

    _hasta(engine, "head")

    assert _revision(engine) == "0011"
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

    assert _revision(engine) == "0011"
    assert {"bots", "bot_message_counts", "document_images"} <= set(
        inspect(engine).get_table_names()
    )


def test_la_migracion_0008_agrega_la_memoria_de_conversacion_sin_perder_datos(tmp_path):
    engine = _base_en(tmp_path, "0007")
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO units (id, name, description, created_at) VALUES ('u1', 'U', '', '2026-11-03')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO artifacts (id, name, description, key_hash, key_prefix, active, all_domains, modes, daily_cap_usd, "
                "created_at, updated_at) VALUES ('a1', 'Consulta', '', 'h1', 'mia_aaaa', 1, 0, 'literal', 0.5, '2026-11-03', '2026-11-03')"
            )
        )
        connection.execute(
            text(
                "INSERT INTO bots (id, name, kapso_number_id, artifact_id, active, created_at, updated_at) "
                "VALUES ('b1', 'Bot', '111', 'a1', 1, '2026-11-03', '2026-11-03')"
            )
        )
    assert "context_turns" not in {c["name"] for c in inspect(engine).get_columns("artifacts")}

    _hasta(engine, "head")

    columnas = {c["name"]: c for c in inspect(engine).get_columns("artifacts")}
    assert columnas["context_turns"]["nullable"] is False
    bots = {c["name"]: c for c in inspect(engine).get_columns("bots")}
    assert bots["context_turns"]["nullable"] is True
    assert _revision(engine) == "0011"
    with engine.connect() as connection:
        assert connection.execute(text("SELECT name, context_turns FROM artifacts")).one() == (
            "Consulta",
            0,
        )
        assert connection.execute(text("SELECT name, context_turns FROM bots")).one() == (
            "Bot",
            None,
        )
        assert connection.execute(text("SELECT filename FROM documents")).scalar_one() == "acta.pdf"


def test_bajar_a_la_0007_quita_las_dos_columnas_y_conserva_el_resto(tmp_path):
    engine = _base_en(tmp_path, "head")
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO artifacts (id, name, description, key_hash, key_prefix, active, all_domains, modes, daily_cap_usd, "
                "context_turns, created_at, updated_at) VALUES ('a1', 'Consulta', '', 'h1', 'mia_aaaa', 1, 0, 'literal', 0.5, 3, "
                "'2026-11-03', '2026-11-03')"
            )
        )

    _hasta(engine, "0007", accion="downgrade")

    assert _revision(engine) == "0007"
    assert "context_turns" not in {c["name"] for c in inspect(engine).get_columns("artifacts")}
    assert "context_turns" not in {c["name"] for c in inspect(engine).get_columns("bots")}
    with engine.connect() as connection:
        assert connection.execute(text("SELECT name FROM artifacts")).scalar_one() == "Consulta"
        assert connection.execute(text("SELECT COUNT(*) FROM documents")).scalar_one() == 1

    _hasta(engine, "head")  # y se puede volver a subir

    with engine.connect() as connection:
        assert connection.execute(text("SELECT context_turns FROM artifacts")).scalar_one() == 0


def test_la_migracion_0009_crea_usuarios_sesiones_y_conversaciones_sin_perder_datos(tmp_path):
    engine = _base_en(tmp_path, "0008")
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO artifacts (id, name, description, key_hash, key_prefix, active, all_domains, modes, daily_cap_usd, "
                "context_turns, created_at, updated_at) VALUES ('a1', 'Consulta', '', 'h1', 'mia_aaaa', 1, 0, 'literal', 0.5, 3, "
                "'2026-11-04', '2026-11-04')"
            )
        )
    assert "consulta_users" not in set(inspect(engine).get_table_names())

    _hasta(engine, "head")

    tablas = set(inspect(engine).get_table_names())
    assert {"consulta_users", "consulta_sessions", "conversations", "conversation_turns"} <= tablas
    columnas = lambda t: {c["name"]: c for c in inspect(engine).get_columns(t)}
    assert {"id", "username", "password_hash", "unit_id", "active", "created_by", "created_at", "updated_at", "last_login_at"} == set(columnas("consulta_users"))
    assert columnas("consulta_users")["unit_id"]["nullable"] is True
    assert {"id", "user_id", "token_hash", "created_at", "last_seen_at", "expires_at"} == set(columnas("consulta_sessions"))
    assert {"id", "user_id", "title", "created_at", "updated_at"} == set(columnas("conversations"))
    assert {"id", "conversation_id", "position", "question", "answer", "sources", "mode", "no_info", "created_at"} == set(columnas("conversation_turns"))
    indices = {i["name"] for t in ("consulta_sessions", "conversations", "conversation_turns") for i in inspect(engine).get_indexes(t)}
    assert {"ix_consulta_sessions_token_hash", "ix_conversations_user_id_updated_at", "ix_conversation_turns_conversation_id"} <= indices
    require_login = columnas("artifacts")["require_login"]
    assert require_login["nullable"] is False
    assert _revision(engine) == "0011"
    with engine.connect() as connection:
        # El artefacto existente no cambia y nace sin exigir sesión.
        assert connection.execute(text("SELECT name, context_turns, require_login FROM artifacts")).one() == ("Consulta", 3, 0)
        assert connection.execute(text("SELECT filename FROM documents")).scalar_one() == "acta.pdf"


def test_bajar_a_la_0008_quita_lo_de_la_0009_y_conserva_el_resto(tmp_path):
    engine = _base_en(tmp_path, "head")
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO artifacts (id, name, description, key_hash, key_prefix, active, all_domains, modes, daily_cap_usd, "
                "context_turns, require_login, created_at, updated_at) VALUES ('a1', 'Consulta', '', 'h1', 'mia_aaaa', 1, 0, 'literal', 0.5, 3, 1, "
                "'2026-11-04', '2026-11-04')"
            )
        )

    _hasta(engine, "0008", accion="downgrade")

    tablas = set(inspect(engine).get_table_names())
    assert not ({"consulta_users", "consulta_sessions", "conversations", "conversation_turns"} & tablas)
    assert "require_login" not in {c["name"] for c in inspect(engine).get_columns("artifacts")}
    assert _revision(engine) == "0008"
    with engine.connect() as connection:
        assert connection.execute(text("SELECT name, context_turns FROM artifacts")).one() == ("Consulta", 3)

    _hasta(engine, "head")

    assert _revision(engine) == "0011"
    assert "conversations" in set(inspect(engine).get_table_names())


def test_borrar_una_conversacion_arrastra_sus_vueltas_con_las_claves_foraneas_activas(tmp_path):
    engine = _base_en(tmp_path, "head")
    with engine.begin() as connection:
        connection.execute(text("PRAGMA foreign_keys=ON"))
        connection.execute(text("INSERT INTO consulta_users (id, username, password_hash, active, created_by, created_at, updated_at) VALUES ('u1', 'ana', 'x', 1, 't', '2026-11-04', '2026-11-04')"))
        connection.execute(text("INSERT INTO conversations (id, user_id, title, created_at, updated_at) VALUES ('c1', 'u1', 't', '2026-11-04', '2026-11-04')"))
        connection.execute(text("INSERT INTO conversation_turns (id, conversation_id, position, question, answer, sources, mode, no_info, created_at) VALUES ('t1', 'c1', 1, 'p', 'r', '[]', 'literal', 0, '2026-11-04')"))
        connection.execute(text("DELETE FROM conversations WHERE id = 'c1'"))
        assert connection.execute(text("SELECT COUNT(*) FROM conversation_turns")).scalar_one() == 0


def test_la_migracion_0010_agrega_dominios_dinamicos_sin_cambiar_los_existentes(tmp_path):
    engine = _base_en(tmp_path, "0009")
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO units (id, name, description, created_at) VALUES ('u1', 'Computación', '', '2026-11-05')"))
        connection.execute(text("INSERT INTO domains (id, unit_id, name, description, created_at) VALUES ('dp', 'u1', 'Promoción', '', '2026-11-05')"))
    assert "dynamic" not in {c["name"] for c in inspect(engine).get_columns("domains")}

    _hasta(engine, "head")

    dynamic = {c["name"]: c for c in inspect(engine).get_columns("domains")}["dynamic"]
    assert dynamic["nullable"] is False
    assert _revision(engine) == "0011"
    with engine.connect() as connection:
        # El dominio existente sigue siendo persistente.
        assert connection.execute(text("SELECT name, dynamic FROM domains WHERE id = 'dp'")).one() == ("Promoción", 0)

    _hasta(engine, "0009", accion="downgrade")

    assert "dynamic" not in {c["name"] for c in inspect(engine).get_columns("domains")}
    with engine.connect() as connection:
        assert connection.execute(text("SELECT name FROM domains WHERE id = 'dp'")).scalar_one() == "Promoción"


def test_la_migracion_0011_agrega_el_prompt_del_artefacto_vacio_y_es_reversible(tmp_path):
    engine = _base_en(tmp_path, "0010")
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO artifacts (id, name, description, key_hash, key_prefix, active, all_domains, modes, daily_cap_usd, "
                "context_turns, require_login, created_at, updated_at) VALUES ('a1', 'Consulta', '', 'h1', 'mia_aaaa', 1, 0, 'literal', 0.5, 0, 0, "
                "'2026-11-10', '2026-11-10')"
            )
        )
    assert "custom_prompt" not in {c["name"] for c in inspect(engine).get_columns("artifacts")}

    _hasta(engine, "head")

    columna = {c["name"]: c for c in inspect(engine).get_columns("artifacts")}["custom_prompt"]
    assert columna["nullable"] is False
    assert _revision(engine) == "0011"
    with engine.connect() as connection:
        # El artefacto existente queda sin prompt propio: responde como siempre.
        assert connection.execute(text("SELECT custom_prompt FROM artifacts WHERE id = 'a1'")).scalar_one() == ""

    _hasta(engine, "0010", accion="downgrade")

    assert "custom_prompt" not in {c["name"] for c in inspect(engine).get_columns("artifacts")}
    with engine.connect() as connection:
        assert connection.execute(text("SELECT name FROM artifacts WHERE id = 'a1'")).scalar_one() == "Consulta"
