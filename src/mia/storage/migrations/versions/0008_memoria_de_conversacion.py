"""Memoria de conversación (feature 014).

Dos columnas nuevas, solo aditivas: `artifacts.context_turns` (entero no nulo, 0 por defecto: las vueltas completas que el
artefacto recuerda y entrega al modelo; 0 es el comportamiento de siempre) y `bots.context_turns` (entero nulo: las vueltas
que recuerda el bot para la aclaración de programa; nulo es el valor por defecto de 2 vueltas). No cambia ninguna fila
existente. Reversible: `downgrade` quita las dos columnas (se pierden los dos números). Una API anterior a esta revisión no
arranca sobre una base que ya la aplicó: antes de volver a una versión anterior hay que correr `alembic downgrade 0007` (ver
"Cuidado con las migraciones" en docs/OPERACION.md).

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-03
"""

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "artifacts", sa.Column("context_turns", sa.Integer(), nullable=False, server_default="0")
    )
    op.add_column("bots", sa.Column("context_turns", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("bots") as batch:
        batch.drop_column("context_turns")
    with op.batch_alter_table("artifacts") as batch:
        batch.drop_column("context_turns")
