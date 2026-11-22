"""Operational outbox and lease invariants on disposable PostgreSQL."""

from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.anomalies.operational_jobs import claim_next, complete, enqueue, fail
from app.anomalies.operational_models import OperationalAnomalyJob
from app.models import Outbound, PurchaseRequest, StockTransaction, TransactionType
from tests.postgres.test_purchase_requests_api import seed_purchase

pytestmark = pytest.mark.postgres


def source(session):
    ids = seed_purchase(session)
    order = PurchaseRequest(
        warehouse_id=ids["source"],
        product_id=ids["product"],
        quantity=3,
        requested_by_id=ids["client"],
        request_number=str(uuid4()),
    )
    outbound = Outbound(
        warehouse_id=ids["source"],
        product_id=ids["product"],
        quantity=3,
        created_by_id=ids["warehouse"],
    )
    session.add_all([order, outbound])
    session.flush()
    txn = StockTransaction(
        transaction_type=TransactionType.OUTBOUND,
        warehouse_id=ids["source"],
        product_id=ids["product"],
        quantity=3,
        created_by_id=ids["warehouse"],
        outbound_id=outbound.id,
    )
    session.add(txn)
    session.flush()
    data = dict(
        transaction_id=txn.id,
        outbound_id=outbound.id,
        purchase_request_id=order.id,
        warehouse_id=ids["source"],
        product_id=ids["product"],
        quantity=3,
        unit="each",
        occurred_at=datetime.now(UTC),
        source_fingerprint="d" * 64,
    )
    session.commit()
    return data


def test_queue_commit_is_the_visibility_boundary(postgres_session, postgres_engine):
    data = source(postgres_session)
    assert enqueue(postgres_session, **data)
    with Session(postgres_engine) as worker, worker.begin():
        assert claim_next(worker, "a" * 64) is None
    postgres_session.rollback()
    assert enqueue(postgres_session, **data)
    assert not enqueue(postgres_session, **data)
    postgres_session.commit()
    with Session(postgres_engine) as worker, worker.begin():
        claim = claim_next(worker, None)
        assert claim is not None and claim.artifact_digest is None
        assert claim.transaction_id == data["transaction_id"]
        assert claim.outbound_id == data["outbound_id"]
        assert claim.unit == "each"
    with Session(postgres_engine) as worker, worker.begin():
        assert complete(worker, claim, {"state": "unavailable", "reason_code": "NO_APPROVED_MODEL"})
        assert not complete(worker, claim, {"state": "flagged"})
        assert claim_next(worker, "a" * 64) is None
    [job] = postgres_session.scalars(select(OperationalAnomalyJob))
    assert job.status == "succeeded" and job.attempts == 1
    assert job.result == {"state": "unavailable", "reason_code": "NO_APPROVED_MODEL"}


def test_retry_preserves_first_digest_and_stale_owner_cannot_publish(postgres_session):
    data = source(postgres_session)
    enqueue(postgres_session, **data)
    first = claim_next(postgres_session, "a" * 64, "c" * 64)
    assert first is not None
    assert not fail(postgres_session, replace(first, claim_token=uuid4()), "TRANSIENT")
    assert fail(postgres_session, first, "TRANSIENT")
    assert claim_next(postgres_session, "b" * 64) is None
    postgres_session.execute(
        text(
            "UPDATE operational_anomaly_jobs SET available_at=clock_timestamp()-interval '1 second'"
        )
    )
    second = claim_next(postgres_session, "b" * 64, "d" * 64)
    assert second is not None and second.artifact_digest == "a" * 64
    assert second.coverage_digest == "c" * 64
    assert second.source_fingerprint == data["source_fingerprint"]
    assert second.claim_token != first.claim_token and second.attempts == 2
    assert not complete(postgres_session, first, {"state": "flagged"})
    assert complete(postgres_session, second, {"state": "normal"})


def test_expired_final_lease_is_terminal(postgres_session):
    data = source(postgres_session)
    enqueue(postgres_session, **data)
    first = claim_next(postgres_session, "a" * 64)
    assert first is not None
    postgres_session.execute(
        text(
            "UPDATE operational_anomaly_jobs SET attempts=5,"
            " lease_expires_at=clock_timestamp()-interval '1 second'"
        )
    )
    assert not complete(postgres_session, first, {"state": "flagged"})
    assert claim_next(postgres_session, "b" * 64) is None
    [job] = postgres_session.scalars(select(OperationalAnomalyJob))
    assert job.status == "failed" and job.last_error_code == "LEASE_EXPIRED"
    assert job.result is None and job.claim_token is None and job.completed_at is not None


def test_locked_expired_claim_does_not_block_picker(postgres_session, postgres_engine):
    data = source(postgres_session)
    enqueue(postgres_session, **data)
    claim = claim_next(postgres_session, None)
    assert claim is not None
    postgres_session.commit()
    postgres_session.execute(
        text(
            "UPDATE operational_anomaly_jobs SET "
            "lease_expires_at=clock_timestamp()-interval '1 second'"
        )
    )
    with Session(postgres_engine) as worker, worker.begin():
        assert claim_next(worker, "b" * 64) is None
        assert not complete(worker, claim, {"state": "flagged"})
    postgres_session.commit()
    again = claim_next(postgres_session, "b" * 64, "d" * 64)
    assert again is not None and again.claim_token != claim.claim_token
    assert again.artifact_digest is None and again.coverage_digest is None
