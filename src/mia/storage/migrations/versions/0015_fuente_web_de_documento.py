"""Fuente web de los documentos (feature 022).

Dos columnas nuevas y un índice, solo aditivos: `documents.source_url` (texto, nula por defecto, con índice) guarda la
dirección final de la página de un documento web, y `documents.source_text` (texto largo, nula por defecto) guarda el texto
que se extrajo de ella, para poder revisarlo después (el disco de Railway no persiste). Las dos quedan nulas en los
documentos de los demás tipos. No modifica ninguna fila existente.
Reversible: `downgrade` quita el índice y las dos columnas (se pierde el texto guardado de los documentos web; los
fragmentos siguen en Qdrant, así que las respuestas no cambian). Una API anterior a esta revisión no arranca sobre una
base que ya la aplicó: antes de volver a una versión anterior hay que correr `alembic downgrade 0014` (ver "Cuidado con
las migraciones" en docs/OPERACION.md).

Revision ID: 0015
Revises: 0014
Create Date: 2026-11-20
"""

import sqlalchemy as sa
from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("source_url", sa.String(), nullable=True))
    op.add_column("documents", sa.Column("source_text", sa.Text(), nullable=True))
    op.create_index("ix_documents_source_url", "documents", ["source_url"])


def downgrade() -> None:
    op.drop_index("ix_documents_source_url", table_name="documents")
    with op.batch_alter_table("documents") as batch:
        batch.drop_column("source_text")
        batch.drop_column("source_url")
