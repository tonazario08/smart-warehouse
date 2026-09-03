from pathlib import Path

from alembic.config import Config
from sqlalchemy import create_engine, inspect

from alembic import command


def test_initial_revision_upgrades_an_empty_database(tmp_path: Path) -> None:
    """The initial Alembic revision must create every approved domain table."""
    database_path = tmp_path / "warehouse.db"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database_path}")

    command.upgrade(config, "head")

    inspector = inspect(create_engine(f"sqlite:///{database_path}"))
    assert set(inspector.get_table_names()) == {
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
