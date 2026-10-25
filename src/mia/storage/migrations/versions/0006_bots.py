"""Bots de WhatsApp y su consumo mensual de mensajes (feature 011).

Dos tablas nuevas: `bots` (el número de Kapso al que responde cada bot y el artefacto que tiene asignado) y
`bot_message_counts` (los mensajes recibidos y enviados por bot y mes, que se comparan con el tope mensual). Solo es
aditiva: no cambia ninguna tabla ni fila existente, y no trae semillas (el bot se registra desde el panel).
Reversible: `downgrade` borra las dos tablas (los bots registrados y el consumo se pierden: conviene anotar los
bots antes). Una API anterior a esta revisión no arranca sobre una base que ya la aplicó: antes de volver a una
versión anterior hay que correr `alembic downgrade 0005` (ver "Cuidado con las migraciones" en docs/OPERACION.md).

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-24
"""
import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "bots",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("kapso_number_id", sa.String(), nullable=False),
        sa.Column("artifact_id", sa.String(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["artifact_id"], ["artifacts.id"], name="fk_bots_artifact_id_artifacts"),
        sa.PrimaryKeyConstraint("id", name="pk_bots"),
        sa.UniqueConstraint("name", name="uq_bots_name"),
        sa.UniqueConstraint("kapso_number_id", name="uq_bots_kapso_number_id"),
    )
    op.create_table(
        "bot_message_counts",
        sa.Column("bot_id", sa.String(), nullable=False),
        sa.Column("month", sa.String(), nullable=False),
        sa.Column("received", sa.Integer(), nullable=False),
        sa.Column("sent", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["bot_id"], ["bots.id"], name="fk_bot_message_counts_bot_id_bots"),
        sa.PrimaryKeyConstraint("bot_id", "month", name="pk_bot_message_counts"),
    )


def downgrade() -> None:
    op.drop_table("bot_message_counts")
    op.drop_table("bots")
