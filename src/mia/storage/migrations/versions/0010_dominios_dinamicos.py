"""Dominios dinámicos (etiqueta).

Una columna nueva, solo aditiva: `domains.dynamic` (booleano no nulo, falso por defecto). Marca los dominios pensados para
cambiar de contenido cada periodo y tener solo información vigente (por ejemplo, Promoción). Es una etiqueta: no cambia la
búsqueda, los permisos ni la ingesta. No modifica ninguna fila existente. Reversible: `downgrade` quita la columna (se pierde
la marca). Una API anterior a esta revisión no arranca sobre una base que ya la aplicó: antes de volver a una versión
anterior hay que correr `alembic downgrade 0009` (ver "Cuidado con las migraciones" en docs/OPERACION.md).

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-06
"""

import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("domains", sa.Column("dynamic", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    with op.batch_alter_table("domains") as batch:
        batch.drop_column("dynamic")
