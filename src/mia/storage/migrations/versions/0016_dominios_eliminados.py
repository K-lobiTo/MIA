"""Nombres de los dominios eliminados (feature 023).

Una tabla nueva, solo aditiva: `deleted_domains` guarda el id y el nombre ("Programa / Dominio") de cada dominio que se
elimina, para que el módulo Uso siga nombrándolo en las consultas ya registradas. No modifica ninguna tabla existente.
Reversible: `downgrade` quita la tabla (el historial vuelve a mostrar el id del dominio). Una API anterior a esta
revisión no arranca sobre una base que ya la aplicó: antes de volver a una versión anterior hay que correr
`alembic downgrade 0015` (ver "Cuidado con las migraciones" en docs/OPERACION.md).

Revision ID: 0016
Revises: 0015
Create Date: 2026-11-26
"""

import sqlalchemy as sa
from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "deleted_domains",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("label", sa.String(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_deleted_domains")),
    )


def downgrade() -> None:
    op.drop_table("deleted_domains")
