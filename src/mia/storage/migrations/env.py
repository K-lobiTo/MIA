from alembic import context
from sqlalchemy import create_engine

from mia.config import settings
from mia.storage.db import _normalize_url
from mia.storage.models import Base

config = context.config
target_metadata = Base.metadata


def _run(connection) -> None:
    # render_as_batch: SQLite no puede alterar restricciones, así que recrea la tabla.
    context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()


# init_db entrega una conexión ya abierta; desde la terminal (alembic upgrade head) se arma una
# con DATABASE_URL.
connection = config.attributes.get("connection")
if connection is not None:
    _run(connection)
else:
    engine = create_engine(_normalize_url(settings.database_url))
    with engine.begin() as connection:
        _run(connection)
