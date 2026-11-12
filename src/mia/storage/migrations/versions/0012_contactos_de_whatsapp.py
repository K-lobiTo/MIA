"""Contactos de quienes escriben al bot de WhatsApp (feature 017).

Una tabla nueva y dedicada, solo aditiva: `whatsapp_contacts` (el teléfono de la persona, el bot al que escribió y, si los
entregó, su nombre y su correo, con el estado de la invitación). No cambia ninguna tabla ni fila existente y no trae
semillas. Es la única tabla con teléfonos (excepción deliberada a FR-027 y SC-010 de la feature 011).
Reversible: `downgrade` borra la tabla (SE PIERDEN los contactos: conviene descargar el CSV desde el panel antes). Una API
anterior a esta revisión no arranca sobre una base que ya la aplicó: antes de volver a una versión anterior hay que correr
`alembic downgrade 0011` (ver "Cuidado con las migraciones" en docs/OPERACION.md).

Revision ID: 0012
Revises: 0011
Create Date: 2026-11-12
"""

import sqlalchemy as sa
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "whatsapp_contacts",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("bot_id", sa.String(), nullable=False),
        sa.Column("phone", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("email_retried", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["bot_id"], ["bots.id"], name="fk_whatsapp_contacts_bot_id_bots"),
        sa.PrimaryKeyConstraint("id", name="pk_whatsapp_contacts"),
        sa.UniqueConstraint("bot_id", "phone", name="uq_whatsapp_contacts_bot_id_phone"),
    )
    op.create_index("ix_whatsapp_contacts_status", "whatsapp_contacts", ["status"])
    op.create_index("ix_whatsapp_contacts_created_at", "whatsapp_contacts", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_whatsapp_contacts_created_at", table_name="whatsapp_contacts")
    op.drop_index("ix_whatsapp_contacts_status", table_name="whatsapp_contacts")
    op.drop_table("whatsapp_contacts")
