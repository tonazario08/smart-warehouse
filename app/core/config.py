"""Typed runtime configuration."""

from functools import lru_cache
from pathlib import Path
from typing import Literal, Self
from urllib.parse import urlsplit

from pydantic import EmailStr, Field, SecretStr, TypeAdapter, ValidationError, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

UNSAFE_JWT_PLACEHOLDERS = frozenset(
    {
        "change-me",
        "replace-with-a-long-random-secret",
        "local-development-secret-change-me",
    }
)
SUPPORTED_RUNTIME_DATABASE_DRIVER = "postgresql+psycopg"
SUPPORTED_TEST_DATABASE_DRIVERS = frozenset(
    {
        SUPPORTED_RUNTIME_DATABASE_DRIVER,
        "sqlite",
        "sqlite+pysqlite",
    }
)
EMAIL_ADDRESS = TypeAdapter(EmailStr)


class Settings(BaseSettings):
    """Application settings loaded from the environment or a local .env file."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", hide_input_in_errors=True)

    app_env: Literal["development", "test", "integration", "production"] = "development"
    app_name: str = "Smart Warehouse API"
    api_v1_prefix: str = "/api/v1"
    database_url: str
    jwt_secret_key: SecretStr
    jwt_algorithm: Literal["HS256"] = "HS256"
    jwt_expire_minutes: int = Field(default=30, ge=5, le=1440)
    password_recovery_enabled: bool = False
    password_recovery_origin: str | None = None
    password_recovery_from_email: str | None = None
    resend_api_key: SecretStr | None = None
    cors_origins: list[str] = Field(default_factory=list)
    forecast_catalog_root: Path | None = None
    forecast_allow_fixture: bool = False
    cold_start_catalog_root: Path | None = None
    cold_start_allow_fixture: bool = False
    replenishment_catalog_root: Path | None = None
    replenishment_allow_fixture: bool = False
    anomalies_allow_fixture: bool = False
    gis_catalog_root: Path | None = None
    gis_snapshot_id: str | None = None
    gis_allow_fixture: bool = False

    @model_validator(mode="after")
    def reject_unsafe_production_values(self) -> Self:
        """Validate runtime database and production JWT-secret safety constraints."""
        if self.cold_start_allow_fixture and self.app_env not in ("test", "integration"):
            raise ValueError("cold-start fixture serving requires a test environment")
        if self.forecast_allow_fixture and self.app_env not in ("test", "integration"):
            raise ValueError("forecast fixture serving requires a test environment")
        if self.replenishment_allow_fixture and self.app_env not in ("test", "integration"):
            raise ValueError("replenishment fixture serving requires a test environment")
        if self.anomalies_allow_fixture and self.app_env not in ("test", "integration"):
            raise ValueError("anomaly fixture serving requires a test environment")
        if self.gis_allow_fixture and self.app_env not in ("test", "integration"):
            raise ValueError("GIS fixture serving requires a test environment")
        try:
            database_url = make_url(self.database_url)
        except ArgumentError as error:
            raise ValueError("database URL must be a valid SQLAlchemy URL") from error

        allowed_drivers = (
            SUPPORTED_TEST_DATABASE_DRIVERS
            if self.app_env == "test"
            else {SUPPORTED_RUNTIME_DATABASE_DRIVER}
        )
        if database_url.drivername not in allowed_drivers:
            raise ValueError("database URL uses an unsupported synchronous driver")

        secret = self.jwt_secret_key.get_secret_value().strip()
        if self.app_env == "production" and (
            len(secret) < 32 or secret in UNSAFE_JWT_PLACEHOLDERS
        ):
            raise ValueError("production JWT secret must contain at least 32 characters")
        return self

    @property
    def password_recovery_configured(self) -> bool:
        return self.password_recovery_enabled and bool(
            self.password_recovery_origin and self.password_recovery_origin.strip()
            and self.password_recovery_from_email and self.password_recovery_from_email.strip()
            and self.resend_api_key and self.resend_api_key.get_secret_value().strip()
        )

    @model_validator(mode="after")
    def validate_password_recovery(self) -> Self:
        if not self.password_recovery_configured:
            return self
        assert self.password_recovery_origin is not None
        try:
            self.password_recovery_from_email = EMAIL_ADDRESS.validate_python(
                self.password_recovery_from_email
            )
        except ValidationError:
            raise ValueError("Password recovery requires a valid sender address.") from None
        try:
            origin = urlsplit(self.password_recovery_origin)
            port = origin.port
        except ValueError:
            raise ValueError("Password recovery origin must be a valid frontend origin.") from None
        is_test_origin = (
            self.app_env in {"test", "integration"} and origin.scheme == "http"
            and origin.hostname in {"localhost", "127.0.0.1"}
        )
        if (
            (origin.scheme != "https" and not is_test_origin) or not origin.hostname
            or origin.username is not None or origin.password is not None
            or port == 0 or any(char.isspace() for char in self.password_recovery_origin)
            or self.password_recovery_origin != f"{origin.scheme}://{origin.netloc}"
            or self.password_recovery_origin not in self.cors_origins
        ):
            raise ValueError("Password recovery origin must be a configured HTTPS frontend origin.")
        return self


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide immutable settings instance."""
    return Settings()
