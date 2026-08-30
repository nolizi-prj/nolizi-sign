"""Database engine, session factory, and declarative base."""

from collections.abc import Generator
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import Settings

settings = Settings()


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Lazily create (and cache) the SQLAlchemy engine from DATABASE_URL.

    Deferred until first use so importing this module — and anything that
    transitively imports it, e.g. `app.models` for Alembic autogenerate or
    for tests that build their own engine against TEST_DATABASE_URL — never
    requires DATABASE_URL to be set. Raises loudly rather than silently
    falling back to a hardcoded local URL, so a deployment with a missing
    DATABASE_URL fails fast at startup instead of quietly connecting
    somewhere unintended.
    """
    if not settings.database_url:
        raise RuntimeError("DATABASE_URL is not set")
    return create_engine(settings.database_url, pool_pre_ping=True)


def get_session_factory() -> sessionmaker[Session]:
    """Return a sessionmaker bound to the lazily-created engine."""
    return sessionmaker(bind=get_engine(), autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    """Yield a database session for a request, closing it afterward."""
    session_factory = get_session_factory()
    db = session_factory()
    try:
        yield db
    finally:
        db.close()
