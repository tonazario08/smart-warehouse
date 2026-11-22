"""Order analytics migration round trip in the existing guarded migration test database."""

import pytest
from sqlalchemy import inspect, text

from alembic import command
from tests.postgres.test_purchase_request_migration import purchase_migration_target  # noqa: F401

pytestmark = pytest.mark.postgres
PARENT = "20261113_0007"
HEAD = "20261122_0008"
TABLES = {"order_analytics_jobs", "order_analytics_order_checks", "order_analytics_key_states"}


def test_upgrade_and_downgrade_order_analytics(purchase_migration_target):  # noqa: F811
    config, engine = purchase_migration_target
    command.upgrade(config, PARENT)
    base_tables = set(inspect(engine).get_table_names())
    assert not TABLES & base_tables

    command.upgrade(config, HEAD)
    after_upgrade = inspect(engine)
    assert set(after_upgrade.get_table_names()) == base_tables | TABLES
    indexes = {i["name"] for i in after_upgrade.get_indexes("order_analytics_jobs")}
    assert indexes >= {"ix_order_analytics_job_due", "ix_order_analytics_job_key"}
    uniques = list(after_upgrade.get_unique_constraints("order_analytics_jobs"))
    assert any(i["column_names"] == ["purchase_request_id"] for i in uniques)
    assert after_upgrade.get_pk_constraint("order_analytics_key_states")["constrained_columns"] == [
        "warehouse_id",
        "product_id",
    ]
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM order_analytics_jobs")) == 0

    command.downgrade(config, PARENT)
    assert set(inspect(engine).get_table_names()) == base_tables
    command.upgrade(config, HEAD)
    assert set(inspect(engine).get_table_names()) == base_tables | TABLES
