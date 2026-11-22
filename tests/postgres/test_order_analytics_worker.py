"""Exercise the durable worker against disposable PostgreSQL and the real create API."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models import PurchaseRequest, PurchaseRequestWorkflow
from app.order_analytics import worker
from app.order_analytics.jobs import MAX_ATTEMPTS, claim_next, guard_claim
from tests.postgres.test_purchase_requests_api import create, headers_for, seed_purchase

pytestmark = pytest.mark.postgres


@pytest.fixture
def queued(postgres_session, postgres_client, postgres_url):
    ids = seed_purchase(postgres_session)
    settings = Settings(
        app_env="test",
        database_url=postgres_url,
        jwt_secret_key="test-only-jwt-secret-with-at-least-32-characters",
        cors_origins=[],
        _env_file=None,
    )
    response = create(postgres_client, ids, headers_for(ids, "client", settings), uuid4())
    assert response.status_code == 201
    return settings, response.json()["id"]


def _state(engine):
    with Session(engine) as session:
        return session.execute(text("SELECT * FROM order_analytics_jobs")).mappings().one()


def _expire(engine, attempts=None):
    with engine.begin() as connection:
        connection.execute(
            text("""
              UPDATE order_analytics_jobs
              SET lease_expires_at = clock_timestamp() - interval '1 second',
                  attempts = coalesce(CAST(:attempts AS integer), attempts)
            """),
            {"attempts": attempts},
        )


def _claim(engine):
    with Session(engine) as session, session.begin():
        return claim_next(session)


def test_worker_updates_three_steps_and_does_not_reclaim(queued, postgres_engine):
    settings, order_id = queued
    assert worker.run_once(postgres_engine, settings)
    assert not worker.run_once(postgres_engine, settings)
    job = _state(postgres_engine)
    assert job["status"] == "succeeded"
    assert job["attempts"] == 1
    assert job["claim_token"] is None
    with Session(postgres_engine) as session:
        check = (
            session.execute(
                text("SELECT * FROM order_analytics_order_checks WHERE purchase_request_id = :id"),
                {"id": order_id},
            )
            .mappings()
            .one()
        )
        assert check["status"] == "insufficient_data"
        assert check["reason_code"] == "INSUFFICIENT_HISTORY"
        key = session.execute(text("SELECT * FROM order_analytics_key_states")).mappings().one()
        assert key["forecast_reason_code"] == "BASELINE_NOT_FOUND"
        assert key["replenishment_reason_code"] == "OPERATIONAL_ROP_NOT_FOUND"


def test_partial_failure_preserves_order_check_and_retries(queued, postgres_engine, monkeypatch):
    settings, _ = queued
    previous = worker.update_forecast_context

    def fail(*_):
        raise RuntimeError("expected synthetic failure")

    monkeypatch.setattr(worker, "update_forecast_context", fail)
    assert worker.run_once(postgres_engine, settings)
    state = _state(postgres_engine)
    assert state["status"] == "queued"
    assert state["last_error_code"] == "FORECAST_CONTEXT_FAILED"
    assert (state["available_at"] - state["updated_at"]).total_seconds() == pytest.approx(30, abs=1)
    assert not worker.run_once(postgres_engine, settings)
    with postgres_engine.begin() as connection:
        assert connection.scalar(text("SELECT count(*) FROM order_analytics_order_checks")) == 1
        state = connection.execute(
            text("SELECT forecast_status, replenishment_status FROM order_analytics_key_states")
        ).one()
        assert state == ("failed", "insufficient_data")
        connection.execute(text("UPDATE order_analytics_jobs SET available_at = clock_timestamp()"))
    monkeypatch.setattr(worker, "update_forecast_context", previous)
    assert worker.run_once(postgres_engine, settings)
    assert _state(postgres_engine)["attempts"] == 2
    assert _state(postgres_engine)["status"] == "succeeded"
    with postgres_engine.begin() as connection:
        assert connection.scalar(text("SELECT count(*) FROM order_analytics_order_checks")) == 1


def test_reclaimed_worker_cannot_write_or_finish(queued, postgres_engine):
    settings, _ = queued
    claim_a = _claim(postgres_engine)
    _expire(postgres_engine, attempts=MAX_ATTEMPTS - 1)
    claim_b = _claim(postgres_engine)
    assert claim_b.attempts == MAX_ATTEMPTS
    assert claim_b.claim_token != claim_a.claim_token
    for action in (
        worker.update_order_check,
        worker.update_forecast_context,
        worker.update_replenishment_context,
    ):
        with pytest.raises(worker.ClaimLost):
            worker._guarded(
                postgres_engine,
                claim_a,
                lambda session, action=action: action(session, claim_a, settings),
            )
    with pytest.raises(worker.ClaimLost):
        worker._guarded(
            postgres_engine,
            claim_a,
            lambda session: worker.finish_guarded(session, claim_a, None),
        )
    with postgres_engine.connect() as connection:
        assert connection.scalar(text("SELECT count(*) FROM order_analytics_order_checks")) == 0
        assert connection.scalar(text("SELECT count(*) FROM order_analytics_key_states")) == 0
    assert _state(postgres_engine)["claim_token"] == claim_b.claim_token
    worker._guarded(
        postgres_engine,
        claim_b,
        lambda session: worker.update_order_check(session, claim_b, settings),
    )
    worker._guarded(
        postgres_engine, claim_b, lambda session: worker.finish_guarded(session, claim_b, None)
    )
    assert _state(postgres_engine)["status"] == "succeeded"


def test_guard_compares_against_wall_clock_inside_preexisting_transaction(queued, postgres_engine):
    claim = _claim(postgres_engine)
    with postgres_engine.begin() as connection:
        connection.execute(
            text("""
                UPDATE order_analytics_jobs
                SET lease_expires_at = clock_timestamp() + interval '1 second'
            """)
        )
    with Session(postgres_engine) as session, session.begin():
        assert session.scalar(text("SELECT lease_expires_at > now() FROM order_analytics_jobs"))
        session.execute(text("SELECT pg_sleep(1.1)"))
        assert session.scalar(text("SELECT lease_expires_at > now() FROM order_analytics_jobs"))
        assert not guard_claim(session, claim)


def test_clean_up_last_expired_claim_without_sixth_attempt(queued, postgres_engine):
    claim = _claim(postgres_engine)
    _expire(postgres_engine, attempts=MAX_ATTEMPTS)
    assert _claim(postgres_engine) is None
    state = _state(postgres_engine)
    assert (state["status"], state["last_error_code"], state["attempts"]) == (
        "failed",
        "LEASE_EXPIRED",
        MAX_ATTEMPTS,
    )
    assert state["completed_at"] is not None
    assert state["claim_token"] is None
    with pytest.raises(worker.ClaimLost):
        worker._guarded(postgres_engine, claim, lambda session: None)
    assert _claim(postgres_engine) is None


def test_40001_restarts_whole_snapshot_after_competing_write(queued, postgres_engine):
    claim = _claim(postgres_engine)
    seen = []

    def change_stock(session):
        seen.append(session.scalar(text("SELECT quantity FROM stocks")))
        if len(seen) == 1:
            with postgres_engine.begin() as competitor:
                competitor.execute(text("UPDATE stocks SET quantity = 20"))
        session.execute(text("UPDATE stocks SET quantity = :value"), {"value": seen[-1] + 1})

    worker._guarded(postgres_engine, claim, change_stock)
    assert seen == [10, 20]
    with postgres_engine.connect() as connection:
        assert connection.scalar(text("SELECT quantity FROM stocks")) == 21


def test_history_ignores_late_approvals_and_stays_stable_when_jobs_run_backward(
    postgres_session, postgres_engine, postgres_client, postgres_url
):
    ids = seed_purchase(postgres_session)
    settings = Settings(
        app_env="test",
        database_url=postgres_url,
        jwt_secret_key="test-only-jwt-secret-with-at-least-32-characters",
        cors_origins=[],
        _env_file=None,
    )
    target_time = datetime(2025, 1, 1, tzinfo=UTC)

    def history(quantity, *, age=10, decision_age=5, warehouse=None, managed=True):
        prior = PurchaseRequest(
            warehouse_id=ids["source"] if warehouse is None else warehouse,
            product_id=ids["product"],
            requested_by_id=ids["client"],
            status="approved",
            created_at=target_time - timedelta(days=age),
            request_number=str(uuid4()),
            quantity=quantity,
        )
        postgres_session.add(prior)
        postgres_session.flush()
        if managed:
            postgres_session.add(
                PurchaseRequestWorkflow(
                    purchase_request_id=prior.id,
                    created_by_id=ids["client"],
                    idempotency_key=uuid4(),
                    request_fingerprint="0" * 64,
                    decision_kind="approved",
                    decided_by_id=ids["admin"],
                    decided_at=target_time - timedelta(days=decision_age),
                )
            )
        return prior.id

    first_prior = history(5)
    for _ in range(7):
        history(5)
    history(1, decision_age=-1)
    history(1, age=181)
    history(1, warehouse=ids["destination"])
    history(1, managed=False)
    postgres_session.commit()

    headers = headers_for(ids, "client", settings)
    a = create(postgres_client, ids, headers, quantity=15)
    b = create(postgres_client, ids, headers, quantity=14)
    assert a.status_code == b.status_code == 201
    order_a, order_b = a.json()["id"], b.json()["id"]
    with postgres_engine.begin() as connection:
        connection.execute(
            text("""
                UPDATE purchase_requests SET created_at = :date
                WHERE id IN (:order_a, :order_b)
            """),
            {"date": target_time, "order_a": order_a, "order_b": order_b},
        )
        connection.execute(
            text("""
                UPDATE order_analytics_jobs
                SET available_at = clock_timestamp() + interval '1 hour'
                WHERE purchase_request_id = :order_a
            """),
            {"order_a": order_a},
        )
    assert worker.run_once(postgres_engine, settings)
    with postgres_engine.begin() as connection:
        assert (
            connection.execute(
                text("SELECT purchase_request_id FROM order_analytics_order_checks")
            ).scalar_one()
            == order_b
        )
        # An approved order now fulfilled must remain in the historical sample.
        connection.execute(
            text("UPDATE purchase_requests SET status = 'fulfilled' WHERE id = :id"),
            {"id": first_prior},
        )
        connection.execute(text("UPDATE order_analytics_jobs SET available_at = clock_timestamp()"))
    assert worker.run_once(postgres_engine, settings)
    with postgres_engine.begin() as connection:
        rows = connection.execute(
            text("""
                SELECT purchase_request_id, flagged, sample_count
                FROM order_analytics_order_checks ORDER BY purchase_request_id
            """)
        ).all()
        assert rows == [(order_a, True, 8), (order_b, False, 8)]
        connection.execute(
            text("""
            UPDATE order_analytics_jobs SET status = 'queued', available_at = clock_timestamp()
        """)
        )
    assert worker.run_once(postgres_engine, settings)
    assert worker.run_once(postgres_engine, settings)
    with postgres_engine.connect() as connection:
        assert (
            connection.execute(
                text("""
                SELECT purchase_request_id, flagged, sample_count
                FROM order_analytics_order_checks ORDER BY purchase_request_id
            """)
            ).all()
            == rows
        )


def test_terminal_step_errors_are_independent(queued, postgres_engine, monkeypatch):
    settings, _ = queued

    def fail(*_):
        raise RuntimeError("expected synthetic failure")

    monkeypatch.setattr(worker, "update_order_check", fail)
    monkeypatch.setattr(worker, "update_replenishment_context", fail)
    with postgres_engine.begin() as connection:
        connection.execute(
            text("UPDATE order_analytics_jobs SET attempts = :attempts"),
            {"attempts": MAX_ATTEMPTS - 1},
        )
    assert worker.run_once(postgres_engine, settings)
    job = _state(postgres_engine)
    assert (job["status"], job["attempts"], job["last_error_code"]) == (
        "failed",
        MAX_ATTEMPTS,
        "ORDER_CHECK_FAILED",
    )
    with postgres_engine.connect() as connection:
        assert connection.execute(
            text("SELECT status, reason_code FROM order_analytics_order_checks")
        ).one() == ("failed", "ORDER_CHECK_FAILED")
        assert connection.execute(
            text("SELECT forecast_status, replenishment_status FROM order_analytics_key_states")
        ).one() == ("insufficient_data", "failed")


def test_locked_final_expired_row_does_not_block_next_job(queued, postgres_engine, postgres_client):
    settings, order_id = queued
    with Session(postgres_engine) as session:
        order = session.get(PurchaseRequest, order_id)
        ids = {
            "source": order.warehouse_id,
            "product": order.product_id,
            "client": order.requested_by_id,
        }
    old = _claim(postgres_engine)
    _expire(postgres_engine, attempts=MAX_ATTEMPTS)
    response = create(postgres_client, ids, headers_for(ids, "client", settings), uuid4())
    assert response.status_code == 201
    second_order = response.json()["id"]

    # Keep the expired row locked while a second session attempts cleanup and claim.
    with postgres_engine.begin() as lock:
        lock.execute(
            text("SELECT id FROM order_analytics_jobs WHERE id = :id FOR UPDATE"), {"id": old.id}
        )
        with Session(postgres_engine) as session, session.begin():
            session.execute(text("SET LOCAL lock_timeout = '500ms'"))
            claimed = claim_next(session)
            assert claimed.purchase_request_id == second_order
        assert (
            lock.scalar(
                text("SELECT status FROM order_analytics_jobs WHERE id = :id"), {"id": old.id}
            )
            == "running"
        )

    assert _claim(postgres_engine) is None
    with postgres_engine.connect() as connection:
        expired = connection.execute(
            text(
                "SELECT status, last_error_code, attempts FROM order_analytics_jobs WHERE id = :id"
            ),
            {"id": old.id},
        ).one()
        assert expired == ("failed", "LEASE_EXPIRED", MAX_ATTEMPTS)
