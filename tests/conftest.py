import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("DATABASE_URL", "sqlite+pysqlite:///:memory:")
os.environ.setdefault("JWT_SECRET_KEY", "test-only-jwt-secret-with-at-least-32-characters")


@pytest.fixture
def unit_settings() -> Settings:
    """Return settings isolated from developer-specific environment files."""
    return Settings(
        app_env="test",
        database_url="sqlite+pysqlite:///:memory:",
        jwt_secret_key="test-only-jwt-secret-with-at-least-32-characters",
        cors_origins=[],
        _env_file=None,
    )


@pytest.fixture
def test_client(unit_settings: Settings) -> Iterator[TestClient]:
    """Provide an application client configured solely for unit tests."""
    from app.main import create_app

    with TestClient(create_app(unit_settings)) as client:
        yield client
