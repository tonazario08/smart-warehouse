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


def test_sqlite_delivery_migration_preserves_workflow_and_refuses_loss(tmp_path: Path) -> None:
    from sqlalchemy.exc import IntegrityError

    url = f"sqlite:///{(tmp_path / 'delivery.db').as_posix()}"
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "20261122_0011")
    engine = create_engine(url)
    def column_definitions():
        return [
            (column["name"], str(column["type"]), column["nullable"], column["default"])
            for column in inspect(engine).get_columns("purchase_request_workflows")
        ]

    old_columns = column_definitions()
    old_checks = {check["name"] for check in inspect(engine).get_check_constraints(
        "purchase_request_workflows"
    )}
    identity = ("000000000000000000000000000000a1", "a" * 64, "pre-0012 note")
    select_identity = text(
        "SELECT idempotency_key, request_fingerprint, note FROM purchase_request_workflows"
    )
    try:
        with engine.begin() as connection:
            for statement in (
                "INSERT INTO users (email, password_hash, role) "
                "VALUES ('sqlite-workflow@example.test', 'fixture', 'client')",
                "INSERT INTO categories (name) VALUES ('Fasteners')",
                "INSERT INTO products (sku, name, category_id, unit) "
                "VALUES ('BOLT-001', 'Bolt', 1, 'piece')",
                "INSERT INTO warehouses (code, name, address) "
                "VALUES ('HCM-01', 'Fixture', 'Synthetic test address')",
                "INSERT INTO purchase_requests "
                "(request_number, warehouse_id, product_id, quantity, status, requested_by_id) "
                "VALUES ('PR-FIXTURE', 1, 1, 1, 'pending', 1)",
            ):
                connection.execute(text(statement))
            connection.execute(
                text(
                    "INSERT INTO purchase_request_workflows (purchase_request_id, created_by_id, "
                    "idempotency_key, request_fingerprint, note) "
                    "VALUES (1, 1, :key, :fingerprint, :note)"
                ),
                dict(zip(("key", "fingerprint", "note"), identity, strict=True)),
            )
        command.upgrade(cfg, "head")
        with engine.connect() as connection:
            assert connection.execute(select_identity).one() == identity
            assert connection.execute(text(
                "SELECT delivery_address, delivery_latitude, delivery_longitude "
                "FROM purchase_request_workflows"
            )).one() == (None, None, None)
        with pytest.raises(IntegrityError, match="ck_pr_workflow_delivery_location"):
            with engine.begin() as connection:
                connection.execute(text(
                    "UPDATE purchase_request_workflows SET delivery_address = 'Partial'"
                ))
        with engine.begin() as connection:
            connection.execute(text(
                "UPDATE purchase_request_workflows SET delivery_address = 'Synthetic point', "
                "delivery_latitude = 10.77, delivery_longitude = 106.70"
            ))
        with pytest.raises(RuntimeError, match="Cannot downgrade with persisted"):
            command.downgrade(cfg, "20261122_0011")
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
                "20261122_0012"
            )
            assert connection.execute(select_identity).one() == identity
            assert connection.execute(text(
                "SELECT delivery_address, delivery_latitude, delivery_longitude "
                "FROM purchase_request_workflows"
            )).one() == ("Synthetic point", 10.77, 106.70)

        # Only this disposable test clears the snapshot to exercise the allowed branch.
        with engine.begin() as connection:
            connection.execute(text(
                "UPDATE purchase_request_workflows SET delivery_address = NULL, "
                "delivery_latitude = NULL, delivery_longitude = NULL"
            ))
        command.downgrade(cfg, "20261122_0011")
        assert column_definitions() == old_columns
        assert {
            check["name"] for check in inspect(engine).get_check_constraints(
                "purchase_request_workflows"
            )
        } == old_checks
        with engine.connect() as connection:
            assert connection.execute(select_identity).one() == identity
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
                "20261122_0011"
            )
    finally:
        engine.dispose()
