"""Panel de administración: unidades, carpetas, artefactos y registro de consultas.

Tablas nuevas: units, folders, artifacts, artifact_units, artifact_domains, queries. Cambios en las
existentes: domains.unit_id (nullable, la reorganización la llena), nombre de dominio único por
unidad en vez de global, y documents.folder_id (nullable).

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-08
"""
import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def _domain_name_unique_name(bind) -> str:
    """Nombre de la restricción única de domains.name: `domains_name_key` en Postgres (nombre por
    defecto), y sin nombre en SQLite (en batch se le da `uq_domains_name`)."""
    for constraint in sa.inspect(bind).get_unique_constraints("domains"):
        if constraint["column_names"] == ["name"]:
            return constraint["name"] or "uq_domains_name"
    return "uq_domains_name"


def upgrade() -> None:
    bind = op.get_bind()

    op.create_table(
        "units",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_units"),
        sa.UniqueConstraint("name", name="uq_units_name"),
    )

    unique_name = _domain_name_unique_name(bind)
    with op.batch_alter_table(
        "domains", naming_convention={"uq": "uq_%(table_name)s_%(column_0_name)s"}
    ) as batch:
        batch.add_column(sa.Column("unit_id", sa.String(), nullable=True))
        batch.create_foreign_key("fk_domains_unit_id_units", "units", ["unit_id"], ["id"])
        batch.drop_constraint(unique_name, type_="unique")
        batch.create_unique_constraint("uq_domains_unit_id_name", ["unit_id", "name"])

    op.create_table(
        "folders",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("domain_id", sa.String(), nullable=False),
        sa.Column("parent_id", sa.String(), nullable=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["domain_id"], ["domains.id"], name="fk_folders_domain_id_domains"),
        sa.ForeignKeyConstraint(["parent_id"], ["folders.id"], name="fk_folders_parent_id_folders"),
        sa.PrimaryKeyConstraint("id", name="pk_folders"),
        sa.UniqueConstraint("domain_id", "parent_id", "name", name="uq_folders_domain_id_parent_id_name"),
    )

    with op.batch_alter_table("documents") as batch:
        batch.add_column(sa.Column("folder_id", sa.String(), nullable=True))
        batch.create_foreign_key("fk_documents_folder_id_folders", "folders", ["folder_id"], ["id"])

    op.create_table(
        "artifacts",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), nullable=False),
        sa.Column("key_hash", sa.String(), nullable=False),
        sa.Column("key_prefix", sa.String(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("all_domains", sa.Boolean(), nullable=False),
        sa.Column("modes", sa.String(), nullable=False),
        sa.Column("daily_cap_usd", sa.Numeric(10, 4), nullable=False),
        sa.Column("reasoning_daily_cap_usd", sa.Numeric(10, 4), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_artifacts"),
        sa.UniqueConstraint("name", name="uq_artifacts_name"),
        sa.UniqueConstraint("key_hash", name="uq_artifacts_key_hash"),
    )
    op.create_index("ix_artifacts_key_hash", "artifacts", ["key_hash"])

    op.create_table(
        "artifact_units",
        sa.Column("artifact_id", sa.String(), nullable=False),
        sa.Column("unit_id", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(
            ["artifact_id"], ["artifacts.id"], name="fk_artifact_units_artifact_id_artifacts"
        ),
        sa.ForeignKeyConstraint(["unit_id"], ["units.id"], name="fk_artifact_units_unit_id_units"),
        sa.PrimaryKeyConstraint("artifact_id", "unit_id", name="pk_artifact_units"),
    )
    op.create_table(
        "artifact_domains",
        sa.Column("artifact_id", sa.String(), nullable=False),
        sa.Column("domain_id", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(
            ["artifact_id"], ["artifacts.id"], name="fk_artifact_domains_artifact_id_artifacts"
        ),
        sa.ForeignKeyConstraint(
            ["domain_id"], ["domains.id"], name="fk_artifact_domains_domain_id_domains"
        ),
        sa.PrimaryKeyConstraint("artifact_id", "domain_id", name="pk_artifact_domains"),
    )

    op.create_table(
        "queries",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("artifact_id", sa.String(), nullable=True),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("domain_ids", sa.Text(), nullable=False),
        sa.Column("mode", sa.String(), nullable=False),
        sa.Column("model", sa.String(), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("reasoning_tokens", sa.Integer(), nullable=True),
        sa.Column("cost_usd", sa.Numeric(12, 6), nullable=False),
        sa.Column("cost_estimated", sa.Boolean(), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("outcome", sa.String(), nullable=False),
        sa.Column("reject_reason", sa.String(), nullable=True),
        sa.Column("sources", sa.Text(), nullable=False),
        sa.Column("rating", sa.String(), nullable=True),
        sa.Column("rating_comment", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["artifact_id"], ["artifacts.id"], name="fk_queries_artifact_id_artifacts"),
        sa.PrimaryKeyConstraint("id", name="pk_queries"),
    )
    op.create_index("ix_queries_created_at", "queries", ["created_at"])
    op.create_index("ix_queries_artifact_id_created_at", "queries", ["artifact_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_queries_artifact_id_created_at", table_name="queries")
    op.drop_index("ix_queries_created_at", table_name="queries")
    op.drop_table("queries")
    op.drop_table("artifact_domains")
    op.drop_table("artifact_units")
    op.drop_index("ix_artifacts_key_hash", table_name="artifacts")
    op.drop_table("artifacts")
    with op.batch_alter_table("documents") as batch:
        batch.drop_constraint("fk_documents_folder_id_folders", type_="foreignkey")
        batch.drop_column("folder_id")
    op.drop_table("folders")
    with op.batch_alter_table("domains") as batch:
        batch.drop_constraint("uq_domains_unit_id_name", type_="unique")
        batch.create_unique_constraint("uq_domains_name", ["name"])
        batch.drop_constraint("fk_domains_unit_id_units", type_="foreignkey")
        batch.drop_column("unit_id")
    op.drop_table("units")
