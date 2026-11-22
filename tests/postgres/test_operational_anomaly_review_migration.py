"""Model feedback is additive and has no historical backfill."""

import pytest
from sqlalchemy import inspect, text

from alembic import command
from tests.postgres.test_purchase_request_migration import purchase_migration_target  # noqa: F401

pytestmark = pytest.mark.postgres


def test_review_migration_only_adds_table(purchase_migration_target):  # noqa: F811
    config, engine = purchase_migration_target
    command.upgrade(config, "20261122_0010")
    before = set(inspect(engine).get_table_names())
    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO warehouses(code, name, address) VALUES ('TEST-R', 'Test R', 'Test')")
        )
        protected = conn.execute(text("SELECT id, code, name FROM warehouses")).all()
    command.upgrade(config, "20261122_0011")
    assert set(inspect(engine).get_table_names()) == before | {"operational_anomaly_reviews"}
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM operational_anomaly_reviews")) == 0
        assert conn.scalar(text("SELECT count(*) FROM operational_anomaly_jobs")) == 0
        assert conn.execute(text("SELECT id, code, name FROM warehouses")).all() == protected
    command.downgrade(config, "20261122_0010")
    assert set(inspect(engine).get_table_names()) == before
    with engine.connect() as conn:
        assert conn.execute(text("SELECT id, code, name FROM warehouses")).all() == protected
