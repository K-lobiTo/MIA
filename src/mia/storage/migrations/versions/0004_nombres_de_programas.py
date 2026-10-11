"""Nombres de las dos divisiones de la memoria: ya no son dos "unidades" de lo mismo.

Computación pasa a llamarse "Unidad de Postgrados de Computación" y Administración de Empresas pasa a
"Área académica de Analítica de Negocios" (una carrera de computación y administración de empresas).
Solo cambia el nombre (y la descripción de la segunda, si no se había editado a mano): los ids no
cambian, así que artefactos, administradores y dominios siguen apuntando a las mismas filas. Es
idempotente: si el nombre nuevo ya existe, no toca nada.

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-11
"""
import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

COMPUTACION = ("Computación", "Unidad de Postgrados de Computación")
ANALITICA = ("Administración de Empresas", "Área académica de Analítica de Negocios")
DESCRIPCION_ANTERIOR = (
    "Posgrados de Administración de Empresas (hoy, la Maestría en Analítica de Negocios, compartida con Computación)"
)
DESCRIPCION_NUEVA = "Maestría en Analítica de Negocios, carrera de computación y administración de empresas"


def _renombrar(viejo: str, nuevo: str) -> None:
    connection = op.get_bind()
    existe = connection.execute(sa.text("SELECT 1 FROM units WHERE name = :nuevo"), {"nuevo": nuevo}).first()
    if existe is None:
        connection.execute(sa.text("UPDATE units SET name = :nuevo WHERE name = :viejo"), {"nuevo": nuevo, "viejo": viejo})


def upgrade() -> None:
    _renombrar(*COMPUTACION)
    _renombrar(*ANALITICA)
    op.get_bind().execute(
        sa.text("UPDATE units SET description = :nueva WHERE name = :nombre AND description = :anterior"),
        {"nueva": DESCRIPCION_NUEVA, "nombre": ANALITICA[1], "anterior": DESCRIPCION_ANTERIOR},
    )


def downgrade() -> None:
    op.get_bind().execute(
        sa.text("UPDATE units SET description = :anterior WHERE name = :nombre AND description = :nueva"),
        {"nueva": DESCRIPCION_NUEVA, "nombre": ANALITICA[1], "anterior": DESCRIPCION_ANTERIOR},
    )
    _renombrar(COMPUTACION[1], COMPUTACION[0])
    _renombrar(ANALITICA[1], ANALITICA[0])
