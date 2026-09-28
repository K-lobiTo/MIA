from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from mia.config import settings
from mia.storage.models import Base


def _normalize_url(url: str) -> str:
    """Neon y otros Postgres administrados entregan URLs `postgresql://`, que SQLAlchemy asocia al
    driver psycopg2; el proyecto instala psycopg 3."""
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url.removeprefix("postgresql://")
    return url


# pool_pre_ping: Neon suspende la base tras unos minutos sin uso y cierra las conexiones abiertas.
engine = create_engine(_normalize_url(settings.database_url), pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)


def init_db() -> None:
    Base.metadata.create_all(engine)


def get_session() -> Iterator[Session]:
    with SessionLocal() as session:
        yield session
