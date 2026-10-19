"""Lista de equivalencias de siglas de la búsqueda híbrida (feature 010).

Tabla nueva `sigla_equivalences` con las semillas TFG y MGTI. Solo es aditiva: no cambia ninguna tabla ni fila
existente. Es idempotente (una semilla que ya existe no se repite) y reversible: `downgrade` borra solo esa
tabla (la lista editada en el panel se pierde, conviene guardarla antes con GET /equivalences). Una API anterior a
esta revisión no arranca sobre una base que ya la aplicó: antes de volver a una versión anterior hay que correr
`alembic downgrade 0004` (ver "Cuidado con las migraciones" en docs/OPERACION.md).

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-19
"""
import uuid
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

# (sigla normalizada, forma normalizada, sigla como se muestra, forma como se muestra). La forma de MGTI aparece
# en los documentos como "Gestión de Tecnologías de Información" y también con "de la": se siembran las dos
# porque la forma se busca como palabras consecutivas.
SEMILLAS = [
    ("tfg", "trabajo final de graduacion", "TFG", "Trabajo Final de Graduación"),
    ("mgti", "gestion de tecnologias de informacion", "MGTI", "Gestión de Tecnologías de Información"),
    ("mgti", "gestion de tecnologias de la informacion", "MGTI", "Gestión de Tecnologías de la Información"),
]


def upgrade() -> None:
    op.create_table(
        "sigla_equivalences",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("sigla", sa.String(), nullable=False),
        sa.Column("form", sa.String(), nullable=False),
        sa.Column("sigla_display", sa.String(), nullable=False),
        sa.Column("form_display", sa.String(), nullable=False),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_by", sa.String(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_sigla_equivalences"),
        sa.UniqueConstraint("sigla", "form", name="uq_sigla_equivalences_sigla"),
    )
    connection = op.get_bind()
    now = datetime.now(UTC).replace(tzinfo=None)
    for sigla, form, sigla_display, form_display in SEMILLAS:
        exists = connection.execute(
            sa.text("SELECT 1 FROM sigla_equivalences WHERE sigla = :sigla AND form = :form"),
            {"sigla": sigla, "form": form},
        ).first()
        if exists is None:
            connection.execute(
                sa.text(
                    "INSERT INTO sigla_equivalences "
                    "(id, sigla, form, sigla_display, form_display, created_by, created_at) "
                    "VALUES (:id, :sigla, :form, :sigla_display, :form_display, 'automatizacion', :created_at)"
                ),
                {
                    "id": str(uuid.uuid4()), "sigla": sigla, "form": form,
                    "sigla_display": sigla_display, "form_display": form_display, "created_at": now,
                },
            )


def downgrade() -> None:
    op.drop_table("sigla_equivalences")
