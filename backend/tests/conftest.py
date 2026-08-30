"""Shared pytest fixtures.

Tests run against a real Postgres instance (never SQLite) because the schema
uses Postgres-only features (JSONB, TIMESTAMPTZ). Start a local test database
with:

    docker run -d --name sign-test-pg -e POSTGRES_PASSWORD=postgres -p 5433:5432 postgres:16
    docker exec sign-test-pg psql -U postgres -c "CREATE DATABASE pumasi_sign_test"

The database URL is read from TEST_DATABASE_URL, defaulting to the container
above.
"""

import contextlib
import os
from collections.abc import Callable, Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app import models  # noqa: F401  (import registers all tables on Base.metadata)
from app.config import Settings
from app.db import Base, get_db
from app.main import create_app

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@localhost:5433/pumasi_sign_test",
)

ADMIN_EMAIL = "admin@pumasi.ai"
DEFAULT_USER_EMAIL = "user@pumasi.ai"

engine = create_engine(TEST_DATABASE_URL)
TestSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


@pytest.fixture(scope="session", autouse=True)
def _create_tables() -> Generator[None, None, None]:
    """Create all tables once for the test session, then drop them at the end."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def _truncate_tables() -> Generator[None, None, None]:
    """Empty every table between tests so each test starts from a clean slate."""
    yield
    with engine.begin() as connection:
        table_names = ", ".join(f'"{table.name}"' for table in reversed(Base.metadata.sorted_tables))
        if table_names:
            connection.execute(text(f"TRUNCATE TABLE {table_names} RESTART IDENTITY CASCADE"))


@pytest.fixture
def db() -> Generator[Session, None, None]:
    """Provide a database session bound to the test engine."""
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def make_client() -> Generator[Callable[[Settings | None], TestClient], None, None]:
    """Factory for a TestClient built from a custom Settings instance.

    Each call to the returned factory builds a fresh app via
    ``create_app(settings)`` (defaulting to a plain ``Settings()`` when
    ``settings`` is omitted) with ``get_db`` overridden to use the test
    database, and enters it as a context manager so lifespan events run.
    Tests that need non-default config (e.g. ``dev_auth_bypass=True``,
    ``session_secret=...``) call this directly; ``client`` below is just
    ``make_client(None)`` for tests that don't care about settings.
    """
    with contextlib.ExitStack() as stack:

        def _make(settings: Settings | None = None) -> TestClient:
            app = create_app(settings)

            def _get_test_db() -> Generator[Session, None, None]:
                session = TestSessionLocal()
                try:
                    yield session
                finally:
                    session.close()

            app.dependency_overrides[get_db] = _get_test_db
            return stack.enter_context(TestClient(app))

        yield _make


@pytest.fixture
def client(make_client: Callable[[Settings | None], TestClient]) -> TestClient:
    """Provide a FastAPI TestClient with get_db overridden to use the test database."""
    return make_client(None)


@pytest.fixture
def app_settings(tmp_path: Path) -> Settings:
    """Settings for admin_client/user_client: dev auth bypass + an isolated storage dir.

    Shared by admin_client and user_client within a test so both point at the
    same test database and the same file storage root.
    """
    return Settings(
        session_secret="test-session-secret",
        admin_emails=ADMIN_EMAIL,
        dev_auth_bypass=True,
        app_base_url="http://testserver",
        data_dir=str(tmp_path),
    )


@pytest.fixture
def admin_client(
    make_client: Callable[[Settings | None], TestClient],
    app_settings: Settings,
) -> TestClient:
    """A TestClient already logged in (via dev-login) as an admin user."""
    logged_in_client = make_client(app_settings)
    logged_in_client.post("/api/auth/dev-login", json={"email": ADMIN_EMAIL, "name": "Admin"})
    return logged_in_client


@pytest.fixture
def user_client(
    make_client: Callable[[Settings | None], TestClient],
    app_settings: Settings,
) -> TestClient:
    """A TestClient already logged in (via dev-login) as a plain, non-admin user."""
    logged_in_client = make_client(app_settings)
    logged_in_client.post("/api/auth/dev-login", json={"email": DEFAULT_USER_EMAIL, "name": "User"})
    return logged_in_client
