from pathlib import Path

from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from alembic import command


def test_production_baseline_downgrades_to_initial_revision_on_sqlite(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "migration.db"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database_path.as_posix()}")

    command.upgrade(config, "head")
    command.downgrade(config, "20260829_0001")

    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    try:
        inspector = inspect(engine)
        assert "audit_logs" not in inspector.get_table_names()
        assert {
            "ck_warehouses_code_normalized",
            "ck_warehouses_coordinates_paired_and_ranged",
        }.isdisjoint(
            constraint["name"] for constraint in inspector.get_check_constraints("warehouses")
        )
        assert "ck_transactions_exactly_one_movement" not in {
            constraint["name"] for constraint in inspector.get_check_constraints("transactions")
        }
        with engine.connect() as connection:
            revision = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()
        assert revision == "20260829_0001"
    finally:
        engine.dispose()
