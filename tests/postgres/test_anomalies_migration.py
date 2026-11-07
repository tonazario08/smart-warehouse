import pytest
from sqlalchemy import inspect, text

from alembic import command
from tests.postgres.test_purchase_request_migration import purchase_migration_target  # noqa: F401

pytestmark = pytest.mark.postgres


def test_anomaly_upgrade_and_downgrade_preserves_existing_data(purchase_migration_target):  # noqa: F811
    config, engine = purchase_migration_target
    command.upgrade(config, "20261019_0004")
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO users (email, password_hash, role, is_active) "
                "VALUES ('m9@example.test','x','admin',true)"
            )
        )
    command.upgrade(config, "head")
    assert {"anomaly_runs", "anomaly_alerts", "anomaly_reviews"} <= set(
        inspect(engine).get_table_names()
    )
    command.downgrade(config, "20261019_0004")
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM users WHERE email='m9@example.test'")) == 1
    assert "anomaly_runs" not in inspect(engine).get_table_names()
    command.upgrade(config, "head")
