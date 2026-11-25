"""Exercise permanent order effects and provisional reads at the real API boundary."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import event, func, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.models import OrderAnalyticsJob, PurchaseRequest, PurchaseRequestWorkflow, User
from app.order_analytics.repository import get_order_sample, read_position
from app.purchase_requests.repository import PurchaseRequestRepository
from app.purchase_requests.service import PurchaseRequestService
from tests.postgres.test_purchase_requests_api import (
    BASE,
    create,
    headers_for,
    seed_purchase,
)

pytestmark = pytest.mark.postgres


def test_create_job_replay_conflict_rejected_input_and_rollback(
    postgres_client, postgres_session, unit_settings, monkeypatch
):
    ids = seed_purchase(postgres_session)
    auth = headers_for(ids, "client", unit_settings)
    key = uuid4()
    first = create(postgres_client, ids, auth, key)
    assert first.status_code == 201
    assert "analytics" not in first.json()
    job = postgres_session.scalar(select(OrderAnalyticsJob))
    assert (
        job.purchase_request_id,
        job.warehouse_id,
        job.product_id,
        job.status,
        job.attempts,
    ) == (first.json()["id"], ids["source"], ids["product"], "queued", 0)
    assert create(postgres_client, ids, auth, key).status_code == 200
    assert create(postgres_client, ids, auth, key, quantity=4).status_code == 409
    assert create(postgres_client, ids, auth, quantity=0).status_code == 422
    assert create(postgres_client, ids, auth, warehouse_id=999).status_code == 404

    def fail_after_enqueue(self, record):
        assert postgres_session.scalar(select(func.count(OrderAnalyticsJob.id))) == 2
        raise RuntimeError("controlled error after job enqueue")

    monkeypatch.setattr(PurchaseRequestService, "_project", fail_after_enqueue)
    with pytest.raises(RuntimeError, match="controlled error after job enqueue"):
        create(postgres_client, ids, auth)
    assert postgres_session.scalar(select(func.count(OrderAnalyticsJob.id))) == 1
    assert postgres_session.scalar(select(func.count(PurchaseRequest.id))) == 1
    assert (
        postgres_session.scalar(select(func.count(PurchaseRequestWorkflow.purchase_request_id)))
        == 1
    )


def test_pending_position_is_scoped_excludes_legacy_and_reconciles_lifecycle(
    postgres_client, postgres_session, unit_settings
):
    ids = seed_purchase(postgres_session)
    auth = {
        role: headers_for(ids, role, unit_settings) for role in ("client", "admin", "warehouse")
    }
    source, product = ids["source"], ids["product"]
    first = create(postgres_client, ids, auth["client"], quantity=3).json()["id"]
    second = create(postgres_client, ids, auth["client"], quantity=8).json()["id"]
    other = create(
        postgres_client, ids, auth["client"], warehouse_id=ids["destination"], quantity=9
    )
    assert other.status_code == 201
    postgres_session.add(
        PurchaseRequest(
            request_number="PR-LEGACY",
            warehouse_id=source,
            product_id=product,
            quantity=20,
            requested_by_id=ids["client"],
            status="pending",
        )
    )
    postgres_session.commit()

    def inspect_position(expected):
        row = read_position(postgres_session, source, product)
        assert (
            row.on_hand,
            row.pending_quantity,
            row.approved_quantity,
            row.total_quantity,
            row.order_count,
            row.projected_quantity,
        ) == expected

    inspect_position((10, 11, 0, 11, 2, -1))
    without_stock = read_position(postgres_session, ids["destination"], product)
    assert (
        without_stock.on_hand,
        without_stock.total_quantity,
        without_stock.projected_quantity,
    ) == (None, 9, None)
    assert (
        postgres_client.post(f"{BASE}/{first}/approve", headers=auth["admin"], json={}).status_code
        == 200
    )
    inspect_position((10, 8, 3, 11, 2, -1))
    assert (
        postgres_client.post(
            f"{BASE}/{second}/reject", headers=auth["admin"], json={"rejection_reason": "fixture"}
        ).status_code
        == 200
    )
    inspect_position((10, 0, 3, 3, 1, 7))
    assert (
        postgres_client.post(
            f"{BASE}/{first}/fulfill", headers=auth["warehouse"], json={}
        ).status_code
        == 200
    )
    inspect_position((7, 0, 0, 0, 0, 7))
    assert postgres_session.scalar(select(func.count(OrderAnalyticsJob.id))) == 3


def test_anomaly_sample_uses_original_creation_cutoff_and_managed_history(postgres_session):
    ids = seed_purchase(postgres_session)
    cutoff = datetime(2026, 11, 1, tzinfo=UTC)

    def make(q, days, decision_date, status="approved", *, warehouse=None, legacy=False):
        row = PurchaseRequest(
            request_number=f"PR-{q}",
            warehouse_id=warehouse or ids["source"],
            product_id=ids["product"],
            quantity=q,
            requested_by_id=ids["client"],
            status=status,
            created_at=cutoff - timedelta(days=days),
        )
        postgres_session.add(row)
        postgres_session.flush()
        if not legacy:
            postgres_session.add(
                PurchaseRequestWorkflow(
                    purchase_request_id=row.id,
                    created_by_id=ids["client"],
                    idempotency_key=uuid4(),
                    request_fingerprint="a" * 64,
                    decision_kind="approved" if decision_date else None,
                    decided_by_id=ids["admin"] if decision_date else None,
                    decided_at=decision_date,
                )
            )
        return row.id

    earlier = cutoff - timedelta(hours=1)
    make(10, 5, earlier)
    make(11, 4, earlier, "fulfilled")
    make(90, 3, cutoff + timedelta(hours=1))
    make(91, 3, cutoff)
    make(92, 3, None, "pending")
    make(93, 181, earlier)
    make(94, 3, earlier, warehouse=ids["destination"])
    make(95, 3, earlier, legacy=True)
    request_id = make(30, 0, None, "pending")
    make(96, 0, earlier)
    postgres_session.flush()
    sample = get_order_sample(postgres_session, request_id)
    assert (sample.quantity, sample.history) == (30, (10, 11))


@pytest.mark.parametrize(
    "sqlstate, committed", [("40P01", False), ("40001", False), ("08006", False), ("08006", True)]
)
def test_create_database_retry_keeps_exactly_one_job(
    postgres_client, postgres_session, unit_settings, monkeypatch, sqlstate, committed
):
    ids = seed_purchase(postgres_session)
    auth = headers_for(ids, "client", unit_settings)
    key = uuid4()
    commit = postgres_session.commit
    calls = 0

    def injected_commit():
        nonlocal calls
        calls += 1
        if calls != 1:
            return commit()

        class SimulatedDatabaseError(Exception):
            pass

        error = SimulatedDatabaseError("private diagnostic")
        error.sqlstate = sqlstate
        if committed:
            commit()
        raise OperationalError(None, None, error, connection_invalidated=(sqlstate == "08006"))

    with monkeypatch.context() as patch:
        patch.setattr(postgres_session, "commit", injected_commit)
        result = create(postgres_client, ids, auth, key)
    if sqlstate == "08006":
        assert result.status_code == 503
        result = create(postgres_client, ids, auth, key)
        assert result.status_code == (200 if committed else 201)
    else:
        assert result.status_code == 201
        assert calls == 2
    assert postgres_session.scalar(select(func.count(OrderAnalyticsJob.id))) == 1
    job = postgres_session.scalar(select(OrderAnalyticsJob))
    assert job.purchase_request_id == result.json()["id"]


def test_position_compares_stock_and_open_orders_in_one_statement_during_fulfill(
    postgres_client, postgres_session, postgres_engine, unit_settings
):
    ids = seed_purchase(postgres_session)
    auth = {role: headers_for(ids, role, unit_settings) for role in ("client", "admin")}
    created = create(postgres_client, ids, auth["client"], quantity=3)
    assert created.status_code == 201
    request_id = created.json()["id"]
    assert (
        postgres_client.post(
            f"{BASE}/{request_id}/approve", headers=auth["admin"], json={}
        ).status_code
        == 200
    )

    with postgres_engine.connect() as reader_connection, Session(reader_connection) as reader:
        before = read_position(reader, ids["source"], ids["product"])
        assert (before.on_hand, before.approved_quantity, before.projected_quantity) == (10, 3, 7)
        emitted = []

        def fulfill_on_read(_conn, _cursor, statement, _params, _context, _executemany):
            emitted.append(statement)
            if len(emitted) == 1:
                with Session(postgres_engine) as writer:
                    service = PurchaseRequestService(PurchaseRequestRepository(writer))
                    actor = writer.get(User, ids["warehouse"])
                    assert service.fulfill(actor, request_id).status == "fulfilled"

        event.listen(reader_connection, "before_cursor_execute", fulfill_on_read)
        after = read_position(reader, ids["source"], ids["product"])
        assert len(emitted) == 1
        assert (after.on_hand, after.approved_quantity, after.projected_quantity) == (7, 0, 7)
