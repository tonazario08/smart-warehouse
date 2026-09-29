from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session

from alembic import command
from app.models import Category, Product, Stock, Supplier, User, UserRole, Warehouse
from app.seed import (
    SeedSettings,
    create_engine_from_environment,
    load_seed_settings,
    seed_database,
)


def seed_environment(**overrides: str) -> dict[str, str]:
    values = {
        "DATABASE_URL": "postgresql+psycopg://seed:secret@localhost/warehouse_test",
        "SEED_ADMIN_EMAIL": " Admin@Example.com ",
        "SEED_ADMIN_PASSWORD": "admin-password-long",
        "SEED_WAREHOUSE_EMAIL": " Warehouse@Example.com ",
        "SEED_WAREHOUSE_PASSWORD": "warehouse-password-long",
        "SEED_CLIENT_EMAIL": " Client@Example.com ",
        "SEED_CLIENT_PASSWORD": "client-password-long",
    }
    return values | overrides


@pytest.mark.parametrize(
    "name",
    [
        "SEED_ADMIN_EMAIL",
        "SEED_ADMIN_PASSWORD",
        "SEED_WAREHOUSE_EMAIL",
        "SEED_WAREHOUSE_PASSWORD",
        "SEED_CLIENT_EMAIL",
        "SEED_CLIENT_PASSWORD",
    ],
)
@pytest.mark.parametrize("value", [None, "", " \t "])
def test_seed_settings_reject_missing_or_blank_privileged_credentials(
    name: str, value: str | None
) -> None:
    environment = seed_environment()
    if value is None:
        environment.pop(name)
    else:
        environment[name] = value

    with pytest.raises(ValueError, match=name):
        load_seed_settings(environment)


def test_seed_settings_require_database_url() -> None:
    environment = seed_environment(DATABASE_URL="  ")

    with pytest.raises(ValueError, match="DATABASE_URL"):
        load_seed_settings(environment)


@pytest.mark.parametrize("value", [None, "", " \t "])
def test_seed_engine_rejects_missing_or_blank_database_url(value: str | None) -> None:
    environment = {} if value is None else {"DATABASE_URL": value}

    with pytest.raises(ValueError, match="DATABASE_URL"):
        create_engine_from_environment(environment)


def test_seed_settings_normalize_emails_like_auth_requests() -> None:
    settings = load_seed_settings(seed_environment())

    assert settings.admin_email == "admin@example.com"
    assert settings.warehouse_email == "warehouse@example.com"
    assert settings.client_email == "client@example.com"


@pytest.mark.parametrize(
    ("password", "valid"),
    [("a" * 11, False), ("a" * 12, True), ("a" * 128, True), ("a" * 129, False)],
)
def test_seed_settings_enforce_auth_password_boundaries(password: str, valid: bool) -> None:
    environment = seed_environment(SEED_ADMIN_PASSWORD=password)

    if valid:
        assert load_seed_settings(environment).admin_password == password
    else:
        with pytest.raises(ValueError, match="SEED_ADMIN_PASSWORD"):
            load_seed_settings(environment)


def test_seed_failure_output_never_echoes_invalid_credentials(monkeypatch, capsys) -> None:
    from app import seed

    sentinel = "x-secret"
    for name, value in seed_environment(SEED_ADMIN_PASSWORD=sentinel).items():
        monkeypatch.setenv(name, value)

    assert seed.main() == 1
    captured = capsys.readouterr()
    output = captured.out + captured.err
    assert sentinel not in output
    assert "DATABASE_URL" not in output


def test_seed_is_idempotent_and_preserves_existing_user_credentials(tmp_path: Path) -> None:
    """Re-running the seed must not duplicate data or replace a user's password hash."""
    database_path = tmp_path / "seed.db"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database_path}")
    command.upgrade(config, "head")
    engine = create_engine(f"sqlite:///{database_path}")

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, _) -> None:
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    settings = SeedSettings(
        admin_email="admin@example.com",
        admin_password="admin-password",
        warehouse_email="warehouse@example.com",
        warehouse_password="warehouse-password",
        client_email="client@example.com",
        client_password="client-password",
    )

    with Session(engine) as session:
        seed_database(session, settings)
        admin = session.scalar(select(User).where(User.email == settings.admin_email))
        assert admin is not None
        original_password_hash = admin.password_hash

        seed_database(session, settings)

        assert session.scalar(select(func.count()).select_from(User)) == 3
        assert session.scalar(select(func.count()).select_from(Category)) == 1
        assert session.scalar(select(func.count()).select_from(Supplier)) == 1
        assert session.scalar(select(func.count()).select_from(Product)) == 1
        assert session.scalar(select(func.count()).select_from(Warehouse)) == 1
        assert session.scalar(select(func.count()).select_from(Stock)) == 1

        seeded_roles = set(session.scalars(select(User.role)))
        assert seeded_roles == {UserRole.ADMIN, UserRole.WAREHOUSE, UserRole.CLIENT}
        assert session.get(User, admin.id).password_hash == original_password_hash
