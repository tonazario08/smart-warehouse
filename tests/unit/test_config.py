import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_production_rejects_unsafe_jwt_secret() -> None:
    """Production configuration must reject a placeholder signing secret."""
    with pytest.raises(ValidationError):
        Settings(
            app_env="production",
            database_url="postgresql+psycopg://u:p@db/app",
            jwt_secret_key="change-me",
            cors_origins=["https://warehouse.example.com"],
            _env_file=None,
        )


@pytest.mark.parametrize(
    "secret",
    [
        "replace-with-a-long-random-secret",
        "local-development-secret-change-me",
    ],
)
def test_production_rejects_known_jwt_placeholders(secret: str) -> None:
    """Known public or development signing keys must not enable production startup."""
    with pytest.raises(ValidationError):
        Settings(
            app_env="production",
            database_url="postgresql+psycopg://u:p@db/app",
            jwt_secret_key=secret,
            cors_origins=["https://warehouse.example.com"],
            _env_file=None,
        )


@pytest.mark.parametrize(
    ("app_env", "database_url"),
    [
        ("development", ""),
        ("production", "not a database url"),
        ("development", "sqlite:///warehouse.db"),
        ("integration", "sqlite:///warehouse.db"),
        ("production", "sqlite:///warehouse.db"),
    ],
)
def test_non_test_settings_reject_invalid_or_sqlite_database_urls(
    app_env: str, database_url: str
) -> None:
    """Only explicit test settings may use SQLite; runtime settings require PostgreSQL."""
    with pytest.raises(ValidationError):
        Settings(
            app_env=app_env,
            database_url=database_url,
            jwt_secret_key="a-test-secret-that-is-longer-than-thirty-two-characters",
            _env_file=None,
        )


def test_test_settings_allow_sqlite_database_url() -> None:
    """The unit-test environment retains a self-contained SQLite option."""
    settings = Settings(
        app_env="test",
        database_url="sqlite+pysqlite:///:memory:",
        jwt_secret_key="a-test-secret-that-is-longer-than-thirty-two-characters",
        _env_file=None,
    )

    assert settings.database_url == "sqlite+pysqlite:///:memory:"


@pytest.mark.parametrize("app_env", ["development", "integration", "production"])
def test_runtime_settings_accept_postgresql_database_url(app_env: str) -> None:
    """Every runtime environment must support the configured PostgreSQL backend."""
    settings = Settings(
        app_env=app_env,
        database_url="postgresql+psycopg://user:password@db/warehouse",
        jwt_secret_key="a-test-secret-that-is-longer-than-thirty-two-characters",
        _env_file=None,
    )

    assert settings.database_url == "postgresql+psycopg://user:password@db/warehouse"


@pytest.mark.parametrize(
    "database_url",
    [
        "postgresql://user:password@db/warehouse",
        "postgresql+asyncpg://user:password@db/warehouse",
        "postgresql+unsupported://user:password@db/warehouse",
    ],
)
def test_runtime_settings_reject_unsupported_postgresql_drivers(database_url: str) -> None:
    """Runtime settings must fail before selecting unavailable or async PostgreSQL dialects."""
    with pytest.raises(ValidationError):
        Settings(
            app_env="production",
            database_url=database_url,
            jwt_secret_key="a-test-secret-that-is-longer-than-thirty-two-characters",
            _env_file=None,
        )


@pytest.mark.parametrize(
    "database_url",
    [
        "sqlite+aiosqlite:///:memory:",
        "sqlite+unsupported:///:memory:",
    ],
)
def test_test_settings_reject_async_or_unknown_sqlite_drivers(database_url: str) -> None:
    """Test settings must remain compatible with the synchronous SQLite session path."""
    with pytest.raises(ValidationError):
        Settings(
            app_env="test",
            database_url=database_url,
            jwt_secret_key="a-test-secret-that-is-longer-than-thirty-two-characters",
            _env_file=None,
        )
