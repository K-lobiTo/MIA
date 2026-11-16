"""Nota de estado de los documentos (feature 018).

Una columna nueva, solo aditiva: `documents.status_note` (texto, nula por defecto). Guarda el motivo de un documento en
estado `error` (por ejemplo, un libro de Excel dañado) o un aviso de uno en estado `done` (por ejemplo, un libro recortado
por superar el tope de filas). Es un mensaje fijo y corto: nunca contiene contenido del documento. No modifica ninguna fila
existente (quedan con la nota nula).
Reversible: `downgrade` quita la columna (se pierden las notas). Una API anterior a esta revisión no arranca sobre una base
que ya la aplicó: antes de volver a una versión anterior hay que correr `alembic downgrade 0012` (ver "Cuidado con las
migraciones" en docs/OPERACION.md).

Revision ID: 0013
Revises: 0012
Create Date: 2026-11-15
"""

import sqlalchemy as sa
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("status_note", sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("documents") as batch:
        batch.drop_column("status_note")
