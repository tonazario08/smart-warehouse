from pathlib import Path

import pytest
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


def test_production_baseline_rejects_normalization_collisions_before_mutation(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "migration-collisions.db"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database_path.as_posix()}")
    command.upgrade(config, "20260829_0001")
    engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO users (email, password_hash, role, is_active) VALUES "
                    "('Client@Example.com', 'hash-1', 'client', true), "
                    "(' client@example.com ', 'hash-2', 'client', true)"
                )
            )
            connection.execute(text("INSERT INTO categories (name) VALUES ('Fasteners')"))
            connection.execute(
                text(
                    "INSERT INTO products (sku, name, category_id, unit) VALUES "
                    "('bolt-001', 'Bolt', 1, 'piece'), "
                    "(' BOLT-001 ', 'Nut', 1, 'piece')"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO warehouses (code, name, address) VALUES "
                    "('hcm-01', 'Central', '1 Nguyen Hue'), "
                    "(' HCM-01 ', 'Overflow', '2 Nguyen Hue')"
                )
            )

        with pytest.raises(
            RuntimeError,
            match=r"users\.email, products\.sku, warehouses\.code",
        ):
            command.upgrade(config, "head")

        with engine.connect() as connection:
            revision = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()
            emails = connection.execute(text("SELECT email FROM users ORDER BY id")).scalars().all()
        assert revision == "20260829_0001"
        assert emails == ["Client@Example.com", " client@example.com "]
    finally:
        engine.dispose()
