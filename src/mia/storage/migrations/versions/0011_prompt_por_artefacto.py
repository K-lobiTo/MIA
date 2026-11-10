"""Prompt propio de cada artefacto.

Una columna nueva, solo aditiva: `artifacts.custom_prompt` (texto no nulo, vacío por defecto). Es una instrucción adicional
que se anexa a la del modo de respuesta en cada consulta de ese artefacto, para ajustar su enfoque (por ejemplo, centrarse
en la información del propio programa). Vacío es el comportamiento de siempre. No modifica ninguna fila existente.
Reversible: `downgrade` quita la columna (se pierden los textos). Una API anterior a esta revisión no arranca sobre una base
que ya la aplicó: antes de volver a una versión anterior hay que correr `alembic downgrade 0010` (ver "Cuidado con las
migraciones" en docs/OPERACION.md).

Revision ID: 0011
Revises: 0010
Create Date: 2026-11-10
"""

import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("artifacts", sa.Column("custom_prompt", sa.Text(), nullable=False, server_default=""))


def downgrade() -> None:
    with op.batch_alter_table("artifacts") as batch:
        batch.drop_column("custom_prompt")
