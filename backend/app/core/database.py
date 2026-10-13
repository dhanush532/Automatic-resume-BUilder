from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    database_url = settings.sqlalchemy_database_url
    if not database_url:
        raise RuntimeError("DATABASE_URL is required for database-backed operations.")
    return create_engine(database_url, pool_pre_ping=True, connect_args={"connect_timeout": 5})


def get_db_session() -> Generator[Session, None, None]:
    session_factory = sessionmaker(bind=get_engine(), autoflush=False, autocommit=False)
    with session_factory() as session:
        yield session
