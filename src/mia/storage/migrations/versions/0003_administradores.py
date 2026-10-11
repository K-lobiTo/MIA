"""Acceso al panel con cuentas del TEC: lista de administradores y su alcance por unidad.

Tablas nuevas: admins y admin_units. No cambia ninguna tabla existente.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-10
"""
import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "admins",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("is_global", sa.Boolean(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_admins"),
        sa.UniqueConstraint("email", name="uq_admins_email"),
    )
    op.create_table(
        "admin_units",
        sa.Column("admin_id", sa.String(), nullable=False),
        sa.Column("unit_id", sa.String(), nullable=False),
        sa.ForeignKeyConstraint(["admin_id"], ["admins.id"], name="fk_admin_units_admin_id_admins"),
        sa.ForeignKeyConstraint(["unit_id"], ["units.id"], name="fk_admin_units_unit_id_units"),
        sa.PrimaryKeyConstraint("admin_id", "unit_id", name="pk_admin_units"),
    )


def downgrade() -> None:
    op.drop_table("admin_units")
    op.drop_table("admins")
