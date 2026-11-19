"""Plantillas de respuesta del modo plantilla (feature 020).

Una tabla nueva, `response_templates` (las plantillas del artefacto y las personales, con unicidad del nombre por dueño y un
`CHECK` de coherencia entre su tipo y sus claves), y dos columnas nulas en `conversation_turns` (`template_id` y
`template_name`, sin clave foránea: la conversación recuerda qué plantilla usó aunque se elimine). Solo es aditiva: no cambia
ninguna fila existente ni trae semillas.
Reversible: `downgrade` quita las dos columnas y la tabla (se pierden todas las plantillas). Una API anterior a esta revisión
no arranca sobre una base que ya la aplicó: antes de volver a una versión anterior hay que correr `alembic downgrade 0013`
(ver "Cuidado con las migraciones" en docs/OPERACION.md).

Revision ID: 0014
Revises: 0013
Create Date: 2026-11-18
"""

import sqlalchemy as sa
from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "response_templates",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("scope", sa.String(), nullable=False),
        sa.Column("owner_key", sa.String(), nullable=False),
        sa.Column("artifact_id", sa.String(), nullable=True),
        sa.Column("user_id", sa.String(), nullable=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("name_key", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(
            "(scope = 'artifact' AND artifact_id IS NOT NULL AND user_id IS NULL) "
            "OR (scope = 'personal' AND user_id IS NOT NULL)",
            name="ck_response_templates_scope_coherente",
        ),
        sa.ForeignKeyConstraint(
            ["artifact_id"],
            ["artifacts.id"],
            name="fk_response_templates_artifact_id_artifacts",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["consulta_users.id"],
            name="fk_response_templates_user_id_consulta_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_response_templates"),
        sa.UniqueConstraint("owner_key", "name_key", name="uq_response_templates_owner_key_name_key"),
    )
    op.create_index("ix_response_templates_artifact_id", "response_templates", ["artifact_id"])
    op.create_index("ix_response_templates_user_id", "response_templates", ["user_id"])
    with op.batch_alter_table("conversation_turns") as batch:
        batch.add_column(sa.Column("template_id", sa.String(), nullable=True))
        batch.add_column(sa.Column("template_name", sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("conversation_turns") as batch:
        batch.drop_column("template_name")
        batch.drop_column("template_id")
    op.drop_index("ix_response_templates_user_id", table_name="response_templates")
    op.drop_index("ix_response_templates_artifact_id", table_name="response_templates")
    op.drop_table("response_templates")
