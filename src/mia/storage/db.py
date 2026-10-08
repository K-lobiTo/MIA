from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import Engine, create_engine, inspect
from sqlalchemy.orm import Session, sessionmaker

from mia.config import settings

MIGRATIONS_DIR = Path(__file__).parent / "migrations"
# Revisión que describe el esquema anterior a las migraciones (ver versions/0001).
BASELINE_REVISION = "0001"


def _normalize_url(url: str) -> str:
    """Neon y otros Postgres administrados entregan URLs `postgresql://`, que SQLAlchemy asocia al
    driver psycopg2; el proyecto instala psycopg 3."""
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url.removeprefix("postgresql://")
    return url


# pool_pre_ping: Neon suspende la base tras unos minutos sin uso y cierra las conexiones abiertas.
engine = create_engine(_normalize_url(settings.database_url), pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)


def init_db(target: Engine | None = None) -> None:
    """Lleva el esquema a la última revisión de Alembic.

    Una base creada antes de las migraciones (con `create_all`) tiene las tablas pero no
    `alembic_version`: se la marca en la revisión inicial sin ejecutarla, y después se aplican las
    siguientes. Se corre al arrancar la API; con una sola instancia no hay riesgo de dos migraciones
    simultáneas.
    """
    from alembic import command
    from alembic.config import Config

    target = target or engine
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    with target.begin() as connection:
        config.attributes["connection"] = connection
        tables = set(inspect(connection).get_table_names())
        if "domains" in tables and "alembic_version" not in tables:
            command.stamp(config, BASELINE_REVISION)
        command.upgrade(config, "head")


def get_session() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session
