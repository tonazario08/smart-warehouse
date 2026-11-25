"""Verify that the private demo link migration does not rewrite historic alerts."""

import pytest
from sqlalchemy import inspect, text

from alembic import command
from tests.postgres.test_purchase_request_migration import purchase_migration_target  # noqa: F401

pytestmark = pytest.mark.postgres
PARENT = "20261122_0008"
HEAD = "20261122_0009"
TABLE = "anomaly_outbound_links"


def test_anomaly_outbound_link_migration_round_trip(purchase_migration_target):  # noqa: F811
    config, engine = purchase_migration_target
    command.upgrade(config, PARENT)
    original_tables = set(inspect(engine).get_table_names())
    assert TABLE not in original_tables
    with engine.begin() as conn:
        conn.execute(
            text("""
                WITH actor AS (
                    INSERT INTO users (email, password_hash, role, is_active)
                    VALUES ('anomaly-link-migration@example.test', 'fixture', 'admin', true)
                    RETURNING id
                ), run AS (
                    INSERT INTO anomaly_runs (run_id, digest, payload, imported_at, imported_by)
                    SELECT 'old-run', 'old-digest', '{}'::json, CURRENT_TIMESTAMP, id FROM actor
                    RETURNING run_id
                )
                INSERT INTO anomaly_alerts (id, run_id, source_record_key, payload,
                                            review_status, version)
                SELECT 'old-alert', run_id, 'old-source',
                       json_build_object('score', 0.8), 'confirmed', 2
                FROM run
            """)
        )

    def historic_alert():
        with engine.connect() as conn:
            return conn.execute(
                text("""
                    SELECT run_id, source_record_key, payload->>'score', review_status, version
                    FROM anomaly_alerts WHERE id='old-alert'
                """)
            ).one()

    command.upgrade(config, HEAD)
    schema = inspect(engine)
    assert set(schema.get_table_names()) == original_tables | {TABLE}
    assert schema.get_pk_constraint(TABLE)["constrained_columns"] == ["alert_id"]
    assert {
        (tuple(fk["constrained_columns"]), fk["referred_table"], fk["options"]["ondelete"])
        for fk in schema.get_foreign_keys(TABLE)
    } == {
        (("alert_id",), "anomaly_alerts", "RESTRICT"),
        (("transaction_id",), "transactions", "RESTRICT"),
        (("outbound_id",), "outbounds", "RESTRICT"),
    }
    assert historic_alert() == ("old-run", "old-source", "0.8", "confirmed", 2)
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM anomaly_outbound_links")) == 0

    command.downgrade(config, PARENT)
    assert set(inspect(engine).get_table_names()) == original_tables
    assert historic_alert() == ("old-run", "old-source", "0.8", "confirmed", 2)
