"""Independent PG sessions with observed lock overlap, not sleep-only races."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event
from time import monotonic, sleep
from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.errors import DomainError
from app.inventory.repository import InventoryRepository
from app.inventory.schemas import InventoryMovementCreate
from app.inventory.service import InventoryService
from app.models import Product, PurchaseRequest, Stock, StockTransfer
from app.purchase_requests.repository import PurchaseRequestRepository
from app.purchase_requests.schemas import PurchaseRequestCreate, PurchaseRequestReject
from app.purchase_requests.service import PurchaseRequestService
from app.transfers.repository import TransferRepository
from app.transfers.schemas import TransferCreate
from app.transfers.service import TransferService

from .test_purchase_request_atomicity import actor, approved_request, service_for, stock_quantity
from .test_purchase_requests_api import body_for, effects, seed_purchase

pytestmark = pytest.mark.postgres


def observed_block(engine, pid):
    deadline = monotonic() + 2
    while monotonic() < deadline:
        with engine.connect() as connection:
            blockers = connection.scalar(text("SELECT pg_blocking_pids(:pid)"), {"pid": pid})
        if blockers:
            return blockers
        sleep(0.01)
    pytest.fail("PostgreSQL must report the intended held-lock overlap.")


@pytest.mark.parametrize("scenario", ["duplicate", "competing", "outbound", "transfer"])
def test_fulfillment_contends_with_real_writers(postgres_session, postgres_engine, scenario):
    ids = seed_purchase(postgres_session)
    first_id = approved_request(postgres_session, ids, 7)
    second_id = approved_request(postgres_session, ids, 7) if scenario == "competing" else first_id
    held, release, started = Event(), Event(), Event()
    pids, lock_trace = {}, []

    class HeldRepository(PurchaseRequestRepository):
        def lock_request(self, request_id):
            lock_trace.append("request")
            return super().lock_request(request_id)

        def get_requestable_product(self, product_id):
            lock_trace.append("product")
            return super().get_requestable_product(product_id)

        def lock_existing_stock(self, warehouse_id, product_id):
            row = super().lock_existing_stock(warehouse_id, product_id)
            lock_trace.append("stock")
            held.set()
            assert release.wait(8)
            return row

    def winner():
        with Session(postgres_engine) as session:
            pids[0] = session.scalar(text("SELECT pg_backend_pid()"))
            return PurchaseRequestService(HeldRepository(session)).fulfill(
                actor(session, ids, "warehouse"), first_id
            )

    def contender():
        with Session(postgres_engine) as session:
            pids[1] = session.scalar(text("SELECT pg_backend_pid()"))
            started.set()
            try:
                if scenario in ("duplicate", "competing"):
                    return service_for(session).fulfill(actor(session, ids, "admin"), second_id)
                if scenario == "outbound":
                    return InventoryService(InventoryRepository(session)).create_outbound(
                        ids["warehouse"],
                        InventoryMovementCreate(
                            warehouse_id=ids["source"], product_id=ids["product"], quantity=7
                        ),
                    )
                return TransferService(TransferRepository(session)).create(
                    ids["warehouse"],
                    uuid4(),
                    TransferCreate(
                        source_warehouse_id=ids["source"],
                        destination_warehouse_id=ids["destination"],
                        product_id=ids["product"],
                        quantity=7,
                    ),
                )
            except DomainError as exc:
                return exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(winner)
        try:
            assert held.wait(5)
            second = pool.submit(contender)
            assert started.wait(5)
            assert pids[0] in observed_block(postgres_engine, pids[1])
        finally:
            release.set()
        result, other = first.result(timeout=12), second.result(timeout=12)
    assert lock_trace == ["request", "product", "stock"]
    assert stock_quantity(postgres_session, ids) == 3
    assert effects(postgres_session)["outbounds"] == effects(postgres_session)["transactions"] == 1
    if scenario == "duplicate":
        assert other == result
    else:
        assert other == "INSUFFICIENT_STOCK"
    if scenario == "competing":
        assert (
            postgres_session.get(PurchaseRequest, second_id, populate_existing=True).status
            == "approved"
        )
    assert postgres_session.scalars(select(StockTransfer)).all() == []


@pytest.mark.parametrize("scenario", ["same", "conflict", "different_actor"])
def test_create_key_races_are_actor_scoped(postgres_session, postgres_engine, scenario):
    ids = seed_purchase(postgres_session)
    held, release, started = Event(), Event(), Event()
    key, pids = uuid4(), {}

    class HeldRepository(PurchaseRequestRepository):
        def lock_key(self, actor_id, key):
            super().lock_key(actor_id, key)
            held.set()
            assert release.wait(8)

    def run(first):
        with Session(postgres_engine) as session:
            pids[first] = session.scalar(text("SELECT pg_backend_pid()"))
            if not first:
                started.set()
            try:
                return PurchaseRequestService(
                    HeldRepository(session) if first else PurchaseRequestRepository(session)
                ).create(
                    actor(
                        session,
                        ids,
                        "other" if not first and scenario == "different_actor" else "client",
                    ),
                    key,
                    PurchaseRequestCreate(
                        **body_for(ids, quantity=4 if not first and scenario == "conflict" else 3)
                    ),
                )
            except DomainError as exc:
                return exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(run, True)
        try:
            assert held.wait(5)
            second = pool.submit(run, False)
            assert started.wait(5)
            if scenario == "different_actor":
                second_result = second.result(timeout=2)
                assert second_result[1] is False
            else:
                assert pids[True] in observed_block(postgres_engine, pids[False])
        finally:
            release.set()
        first_result, second_result = first.result(timeout=10), second.result(timeout=10)
    assert first_result[1] is False
    if scenario == "same":
        assert second_result == (first_result[0], True)
    elif scenario == "conflict":
        assert second_result == "IDEMPOTENCY_KEY_CONFLICT"
    else:
        assert second_result[0].id != first_result[0].id
    assert effects(postgres_session)["purchase_requests"] == (
        2 if scenario == "different_actor" else 1
    )
    assert stock_quantity(postgres_session, ids) == 10


def test_approve_reject_race_keeps_first_decision(postgres_session, postgres_engine):
    ids = seed_purchase(postgres_session)
    row, _ = service_for(postgres_session).create(
        actor(postgres_session, ids, "client"), uuid4(), PurchaseRequestCreate(**body_for(ids))
    )
    held, release, started = Event(), Event(), Event()
    pids = {}

    class HeldRepository(PurchaseRequestRepository):
        def lock_request(self, request_id):
            result = super().lock_request(request_id)
            held.set()
            assert release.wait(8)
            return result

    def run(first):
        with Session(postgres_engine) as session:
            pids[first] = session.scalar(text("SELECT pg_backend_pid()"))
            service = PurchaseRequestService(
                HeldRepository(session) if first else PurchaseRequestRepository(session)
            )
            if not first:
                started.set()
            try:
                if first:
                    return service.approve(actor(session, ids, "admin"), row.id)
                return service.reject(
                    actor(session, ids, "admin"),
                    row.id,
                    PurchaseRequestReject(rejection_reason="race"),
                )
            except DomainError as exc:
                return exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(run, True)
        try:
            assert held.wait(5)
            second = pool.submit(run, False)
            assert started.wait(5)
            assert pids[True] in observed_block(postgres_engine, pids[False])
        finally:
            release.set()
        result = first.result(timeout=10)
        assert second.result(timeout=10) == "PURCHASE_REQUEST_STATE_CONFLICT"
    assert (
        service_for(postgres_session).get(actor(postgres_session, ids, "admin"), row.id) == result
    )
    assert (
        stock_quantity(postgres_session, ids) == 10 and effects(postgres_session)["outbounds"] == 0
    )


@pytest.mark.parametrize("operation", ["create", "approve", "fulfill"])
def test_active_admission_serializes_deactivation(postgres_session, postgres_engine, operation):
    ids = seed_purchase(postgres_session)
    request_id = None
    if operation == "fulfill":
        request_id = approved_request(postgres_session, ids)
    elif operation == "approve":
        row, _ = service_for(postgres_session).create(
            actor(postgres_session, ids, "client"), uuid4(), PurchaseRequestCreate(**body_for(ids))
        )
        request_id = row.id
    held, release, started = Event(), Event(), Event()
    pids = {}

    class HeldRepository(PurchaseRequestRepository):
        def get_requestable_product(self, product_id):
            product = super().get_requestable_product(product_id)
            held.set()
            assert release.wait(8)
            return product

    def admitted():
        with Session(postgres_engine) as session:
            pids[0] = session.scalar(text("SELECT pg_backend_pid()"))
            service = PurchaseRequestService(HeldRepository(session))
            if operation == "create":
                return service.create(
                    actor(session, ids, "client"), uuid4(), PurchaseRequestCreate(**body_for(ids))
                )
            return getattr(service, operation)(actor(session, ids, "admin"), request_id)

    def deactivate():
        with postgres_engine.begin() as connection:
            pids[1] = connection.scalar(text("SELECT pg_backend_pid()"))
            started.set()
            connection.execute(
                text("UPDATE products SET is_active=false WHERE id=:id"), {"id": ids["product"]}
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(admitted)
        try:
            assert held.wait(5)
            second = pool.submit(deactivate)
            assert started.wait(5)
            assert pids[0] in observed_block(postgres_engine, pids[1])
        finally:
            release.set()
        first.result(timeout=10)
        second.result(timeout=10)
    assert not postgres_session.get(Product, ids["product"], populate_existing=True).is_active
    assert stock_quantity(postgres_session, ids) == (7 if operation == "fulfill" else 10)


def test_held_stock_lock_times_out_in_one_attempt(postgres_session, postgres_engine, monkeypatch):
    ids = seed_purchase(postgres_session)
    request_id = approved_request(postgres_session, ids)
    holder, started, pids, attempts = Session(postgres_engine), Event(), [], []
    holder.scalar(select(Stock).with_for_update())

    def run():
        with Session(postgres_engine) as session:
            pids.append(session.scalar(text("SELECT pg_backend_pid()")))
            repository = PurchaseRequestRepository(session)
            original = repository.lock_existing_stock

            def capture(*args):
                attempts.append(1)
                return original(*args)

            monkeypatch.setattr(repository, "lock_existing_stock", capture)
            started.set()
            before = monotonic()
            with pytest.raises(DomainError) as exc:
                PurchaseRequestService(repository).fulfill(
                    actor(session, ids, "warehouse"), request_id
                )
            assert (
                exc.value.code == "PURCHASE_REQUEST_RETRY_REQUIRED" and exc.value.status_code == 503
            )
            return monotonic() - before

    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(run)
            assert started.wait(5)
            observed_block(postgres_engine, pids[0])
            duration = future.result(timeout=8)
            assert 2.7 <= duration < 7
    finally:
        holder.rollback()
        holder.close()
    assert len(attempts) == 1
    assert (
        stock_quantity(postgres_session, ids) == 10 and effects(postgres_session)["outbounds"] == 0
    )


@pytest.mark.parametrize(
    "state,failures,expected",
    [("40P01", 1, 2), ("40001", 2, 3), ("40P01", 3, 3), ("40001", 3, 3), ("55P03", 1, 1)],
)
def test_injected_pg_sqlstates_retry_complete_attempts_only(
    postgres_session, monkeypatch, state, failures, expected
):
    session = postgres_session
    ids = seed_purchase(session)
    request_id = approved_request(session, ids)
    repository = PurchaseRequestRepository(session)
    original, calls, snapshots = repository.add_outbound, [], []

    def injected(*args):
        calls.append(1)
        snapshots.append(session.scalar(select(Stock.quantity)))
        if len(calls) <= failures:
            session.execute(
                text(
                    "DO $$ BEGIN RAISE EXCEPTION 'bounded retry injection' USING ERRCODE='"
                    + state
                    + "'; END $$;"
                )
            )
        return original(*args)

    monkeypatch.setattr(repository, "add_outbound", injected)
    service = PurchaseRequestService(repository)
    if failures < 3 and state != "55P03":
        result = service.fulfill(actor(session, ids, "warehouse"), request_id)
        assert result.fulfillment.quantity_before == 10 and stock_quantity(session, ids) == 7
    else:
        with pytest.raises(DomainError) as exc:
            service.fulfill(actor(session, ids, "warehouse"), request_id)
        assert exc.value.code == "PURCHASE_REQUEST_RETRY_REQUIRED"
        assert stock_quantity(session, ids) == 10 and effects(session)["outbounds"] == 0
    assert len(calls) == expected and snapshots == [7] * expected
    # RAISE SQLSTATE is a bounded retry-boundary test, not a naturally observed deadlock.
