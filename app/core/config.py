"""Typed runtime configuration."""

from functools import lru_cache
from typing import Literal, Self

from pydantic import Field, SecretStr, model_validator
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


class Settings(BaseSettings):
    """Application settings loaded from the environment or a local .env file."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: Literal["development", "test", "integration", "production"] = "development"
    app_name: str = "Smart Warehouse API"
    api_v1_prefix: str = "/api/v1"
    database_url: str
    jwt_secret_key: SecretStr
    jwt_algorithm: Literal["HS256"] = "HS256"
    jwt_expire_minutes: int = Field(default=30, ge=5, le=1440)
    cors_origins: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def reject_unsafe_production_values(self) -> Self:
        """Validate runtime database and production JWT-secret safety constraints."""
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

        secret = self.jwt_secret_key.get_secret_value()
        if self.app_env == "production" and (
            len(secret.strip()) < 32 or secret in UNSAFE_JWT_PLACEHOLDERS
        ):
            raise ValueError("production JWT secret must contain at least 32 characters")
        return self


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide immutable settings instance."""
    return Settings()
