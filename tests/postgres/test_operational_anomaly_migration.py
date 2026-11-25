"""Operational job migration must not manufacture jobs for old outbound vouchers."""

import pytest
from sqlalchemy import insert, inspect, text, update
from sqlalchemy.orm import Session

from alembic import command
from app.models import PurchaseRequest, PurchaseRequestWorkflow
from tests.postgres.test_purchase_request_migration import purchase_migration_target  # noqa: F401
from tests.test_purchase_request_models import fulfilled_values, seed_workflow_rows

pytestmark = pytest.mark.postgres

PARENT = "20261122_0009"
HEAD = "20261122_0010"
TABLE = "operational_anomaly_jobs"


def test_migration_preserves_preexisting_fulfillment_without_backfill(
    purchase_migration_target,  # noqa: F811
):
    config, engine = purchase_migration_target
    command.upgrade(config, PARENT)
    prior_tables = set(inspect(engine).get_table_names())
    assert TABLE not in prior_tables
    with Session(engine) as session:
        seed_workflow_rows(session)
        session.execute(
            update(PurchaseRequest).where(PurchaseRequest.id == 1).values(status="fulfilled")
        )
        session.execute(insert(PurchaseRequestWorkflow).values(**fulfilled_values()))
        session.commit()

    def preserved():
        with engine.connect() as conn:
            return conn.execute(
                text("""
                    SELECT purchase_requests.status, w.quantity_before, w.quantity_after,
                           w.outbound_id, w.outbound_transaction_id
                    FROM purchase_requests
                    JOIN purchase_request_workflows w ON w.purchase_request_id=purchase_requests.id
                    WHERE purchase_requests.id=1
                """)
            ).one()

    command.upgrade(config, HEAD)
    schema = inspect(engine)
    assert set(schema.get_table_names()) == prior_tables | {TABLE}
    assert {tuple(x["column_names"]) for x in schema.get_unique_constraints(TABLE)} == {
        ("transaction_id",),
        ("outbound_id",),
        ("purchase_request_id",),
    }
    assert preserved() == ("fulfilled", 10, 7, 1, 1)
    with engine.connect() as conn:
        assert conn.scalar(text("SELECT count(*) FROM operational_anomaly_jobs")) == 0

    command.downgrade(config, PARENT)
    assert set(inspect(engine).get_table_names()) == prior_tables
    assert preserved() == ("fulfilled", 10, 7, 1, 1)
