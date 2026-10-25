"""Imágenes asociadas a documentos (feature 011).

Tabla nueva `document_images`: una imagen PNG o JPG por fila, guardada en la base (el disco de Railway no persiste) y
servida por GET /media/{public_id}, una ruta pública con identificador aleatorio. Solo es aditiva: no cambia ninguna
tabla ni fila existente. Reversible: `downgrade` borra la tabla (las imágenes se pierden: exportarlas antes si se
quieren conservar). Una API anterior a esta revisión no arranca sobre una base que ya la aplicó: antes de volver a
una versión anterior hay que correr `alembic downgrade 0005` (ver "Cuidado con las migraciones" en
docs/OPERACION.md).

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-24
"""
import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "document_images",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("document_id", sa.String(), nullable=False),
        sa.Column("public_id", sa.String(), nullable=False),
        sa.Column("content_type", sa.String(), nullable=False),
        sa.Column("content", sa.LargeBinary(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("caption", sa.String(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], name="fk_document_images_document_id_documents"),
        sa.PrimaryKeyConstraint("id", name="pk_document_images"),
        sa.UniqueConstraint("public_id", name="uq_document_images_public_id"),
    )
    op.create_index(
        "ix_document_images_document_id_position", "document_images", ["document_id", "position"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_document_images_document_id_position", table_name="document_images")
    op.drop_table("document_images")
