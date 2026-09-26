import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.exc import ArgumentError
from sqlalchemy.orm import Session


@pytest.fixture(scope="session")
def postgres_url() -> str:
    """Return only a psycopg URL naming an explicitly disposable test database."""
    value = os.environ.get("TEST_DATABASE_URL", "")
    try:
        url = make_url(value)
    except (ArgumentError, TypeError, ValueError):
        pytest.fail("TEST_DATABASE_URL must name a database ending in _test", pytrace=False)

    if url.drivername != "postgresql+psycopg" or not (url.database or "").endswith("_test"):
        pytest.fail("TEST_DATABASE_URL must name a database ending in _test", pytrace=False)
    return value


@pytest.fixture(scope="session")
def postgres_engine(postgres_url: str) -> Iterator[Engine]:
    """Create an engine with stale-connection checks and dispose it after the test session."""
    engine = create_engine(postgres_url, pool_pre_ping=True)
    yield engine
    engine.dispose()


@pytest.fixture
def postgres_session(postgres_engine: Engine) -> Iterator[Session]:
    """Yield a database session, then clear every migrated Phase 1 data table."""
    with Session(postgres_engine) as session:
        try:
            yield session
        finally:
            session.rollback()

    with postgres_engine.begin() as connection:
        connection.execute(
            text(
                "TRUNCATE TABLE transactions, inbounds, outbounds, stocks, products, "
                "categories, suppliers, warehouses, route_logs, purchase_requests, regions, users "
                "RESTART IDENTITY CASCADE"
            )
        )


@pytest.fixture
def postgres_client(postgres_url: str, postgres_session: Session) -> Iterator[TestClient]:
    """Provide the real FastAPI app backed only by the disposable test session."""
    from app.core.config import Settings
    from app.db.session import get_session
    from app.main import create_app

    settings = Settings(
        app_env="test",
        database_url=postgres_url,
        jwt_secret_key="test-only-jwt-secret-with-at-least-32-characters",
        cors_origins=[],
        _env_file=None,
    )
    application = create_app(settings)
    original_overrides = application.dependency_overrides.copy()

    def override_get_session() -> Iterator[Session]:
        yield postgres_session

    application.dependency_overrides[get_session] = override_get_session
    try:
        with TestClient(application) as client:
            yield client
    finally:
        application.dependency_overrides.clear()
        application.dependency_overrides.update(original_overrides)
