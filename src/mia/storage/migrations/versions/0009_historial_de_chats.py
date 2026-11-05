"""Usuarios de la Consulta e historial de chats (feature 015).

Cuatro tablas nuevas: `consulta_users` (usuarios con contraseña protegida), `consulta_sessions` (sesiones; el token solo se
guarda como hash), `conversations` y `conversation_turns` (las conversaciones guardadas de cada usuario y sus vueltas); y una
columna, `artifacts.require_login` (booleano no nulo, falso por defecto: el artefacto responde sin sesión como siempre). Solo
es aditiva: no cambia ninguna fila existente ni trae semillas (los usuarios los crea la administración desde el panel).
Reversible: `downgrade` quita las cuatro tablas y la columna (se pierden usuarios, sesiones y conversaciones). Una API anterior
a esta revisión no arranca sobre una base que ya la aplicó: antes de volver a una versión anterior hay que correr
`alembic downgrade 0008` (ver "Cuidado con las migraciones" en docs/OPERACION.md).

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-04
"""

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "consulta_users",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("username", sa.String(), nullable=False),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column("unit_id", sa.String(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("last_login_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["unit_id"], ["units.id"], name="fk_consulta_users_unit_id_units"),
        sa.PrimaryKeyConstraint("id", name="pk_consulta_users"),
        sa.UniqueConstraint("username", name="uq_consulta_users_username"),
    )
    op.create_table(
        "consulta_sessions",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("token_hash", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["consulta_users.id"],
            name="fk_consulta_sessions_user_id_consulta_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_consulta_sessions"),
    )
    op.create_index("ix_consulta_sessions_user_id", "consulta_sessions", ["user_id"])
    op.create_index(
        "ix_consulta_sessions_token_hash", "consulta_sessions", ["token_hash"], unique=True
    )
    op.create_index("ix_consulta_sessions_expires_at", "consulta_sessions", ["expires_at"])
    op.create_table(
        "conversations",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["consulta_users.id"],
            name="fk_conversations_user_id_consulta_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_conversations"),
    )
    op.create_index(
        "ix_conversations_user_id_updated_at", "conversations", ["user_id", "updated_at"]
    )
    op.create_index("ix_conversations_updated_at", "conversations", ["updated_at"])
    op.create_table(
        "conversation_turns",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("conversation_id", sa.String(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("sources", sa.Text(), nullable=False),
        sa.Column("mode", sa.String(), nullable=False),
        sa.Column("no_info", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.id"],
            name="fk_conversation_turns_conversation_id_conversations",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_conversation_turns"),
        sa.UniqueConstraint(
            "conversation_id", "position", name="uq_conversation_turns_conversation_id_position"
        ),
    )
    op.create_index(
        "ix_conversation_turns_conversation_id", "conversation_turns", ["conversation_id"]
    )
    op.add_column(
        "artifacts",
        sa.Column("require_login", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    with op.batch_alter_table("artifacts") as batch:
        batch.drop_column("require_login")
    op.drop_table("conversation_turns")
    op.drop_table("conversations")
    op.drop_table("consulta_sessions")
    op.drop_table("consulta_users")
