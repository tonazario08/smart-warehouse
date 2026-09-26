import pytest
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from alembic import command

pytestmark = pytest.mark.postgres


def test_migrations_build_expected_schema(
    postgres_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The PostgreSQL migration chain must create the complete Phase 1 schema."""
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", postgres_url)
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://wrong:wrong@localhost:55432/not_the_test_database",
    )
    command.downgrade(config, "base")
    command.upgrade(config, "head")

    engine = create_engine(postgres_url)
    try:
        tables = set(inspect(engine).get_table_names())
    finally:
        engine.dispose()

    assert tables == {
        "alembic_version",
        "categories",
        "inbounds",
        "outbounds",
        "products",
        "purchase_requests",
        "regions",
        "route_logs",
        "stocks",
        "suppliers",
        "transactions",
        "users",
        "warehouses",
    }
