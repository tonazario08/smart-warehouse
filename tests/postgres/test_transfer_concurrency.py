"""Independent sessions, real PostgreSQL waits and SQLSTATE retry boundaries."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event
from time import monotonic, sleep
from uuid import uuid4

import pytest
from sqlalchemy import event, select, text
from sqlalchemy.orm import Session

from app.core.errors import DomainError
from app.inventory.repository import InventoryRepository
from app.inventory.schemas import InventoryMovementCreate
from app.inventory.service import InventoryService
from app.models import Stock, User
from app.transfers.repository import TransferRepository
from app.transfers.service import TransferService

from .test_transfer_atomicity import balances, request_for, row_counts, seed_transfer

pytestmark = pytest.mark.postgres


def test_same_actor_replay_keeps_original_snapshots_after_later_stock_write(postgres_session):
    ids = seed_transfer(postgres_session)
    service = TransferService(TransferRepository(postgres_session))
    key = uuid4()
    first, _ = service.create(ids[0], key, request_for(ids))
    first_id = first.id
    InventoryService(InventoryRepository(postgres_session)).create_inbound(
        ids[0], InventoryMovementCreate(warehouse_id=ids[1], product_id=ids[3], quantity=5)
    )
    before = balances(postgres_session)
    repeated, replay = service.create(
        ids[0], key, request_for(ids).model_copy(update={"reference": "CK-01"})
    )
    assert replay and repeated.id == first_id
    assert repeated.source_quantity_before == 10 and repeated.source_quantity_after == 7
    assert balances(postgres_session) == before
    assert row_counts(postgres_session)["stock_transfers"] == 1
    with pytest.raises(DomainError) as exc:
        service.create(ids[0], key, request_for(ids, 1))
    assert exc.value.code == "IDEMPOTENCY_KEY_CONFLICT"
    assert balances(postgres_session) == before


def test_different_actor_same_key_and_failed_attempt_key_reuse(postgres_session):
    ids = seed_transfer(postgres_session, source=2)
    key = uuid4()
    service = TransferService(TransferRepository(postgres_session))
    with pytest.raises(DomainError):
        service.create(ids[0], key, request_for(ids))
    InventoryService(InventoryRepository(postgres_session)).create_inbound(
        ids[0], InventoryMovementCreate(warehouse_id=ids[1], product_id=ids[3], quantity=7)
    )
    first, replay = service.create(ids[0], key, request_for(ids))
    assert not replay
    first_id = first.id
    other = User(email="other-transfer@example.test", password_hash="fixture", role="warehouse")
    postgres_session.add(other)
    postgres_session.commit()
    second, replay = service.create(other.id, key, request_for(ids))
    assert not replay and second.id != first_id
    assert balances(postgres_session)[(ids[1], ids[3])] == 3


@pytest.mark.parametrize("scenario", ["duplicate", "opposite", "competing", "outbound", "inbound"])
def test_independent_session_serial_outcomes(postgres_session, postgres_engine, scenario):
    ids = seed_transfer(
        postgres_session, source=10, destination=10 if scenario == "opposite" else None
    )
    barrier = Barrier(2)
    key = uuid4()
    before = sum(balances(postgres_session).values())

    def run(index):
        with Session(postgres_engine) as session:
            barrier.wait(timeout=10)
            inventory = InventoryService(InventoryRepository(session))
            try:
                if scenario == "outbound" and index == 1:
                    inventory.create_outbound(
                        ids[0],
                        InventoryMovementCreate(warehouse_id=ids[1], product_id=ids[3], quantity=7),
                    )
                    return "ok", False
                if scenario == "inbound" and index == 1:
                    inventory.create_inbound(
                        ids[0],
                        InventoryMovementCreate(warehouse_id=ids[2], product_id=ids[3], quantity=4),
                    )
                    return "ok", False
                request = request_for(ids, 7 if scenario in ["competing", "outbound"] else 3)
                if scenario == "opposite" and index == 1:
                    request = request.model_copy(
                        update={"source_warehouse_id": ids[2], "destination_warehouse_id": ids[1]}
                    )
                if scenario == "competing" and index == 1:
                    request = request.model_copy(update={"destination_warehouse_id": ids[2] + 1})
                _, replay = TransferService(TransferRepository(session)).create(
                    ids[0], key if scenario == "duplicate" else uuid4(), request
                )
                return "ok", replay
            except DomainError as exc:
                return exc.code, False

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(run, index) for index in [0, 1]]
        results = [future.result(timeout=20) for future in futures]
    after = balances(postgres_session)
    assert all(value >= 0 for value in after.values())
    count = row_counts(postgres_session)
    if scenario == "duplicate":
        assert sorted(replay for _, replay in results) == [False, True]
        assert count["stock_transfers"] == 1 and count["transactions"] == 2
        assert after[(ids[1], ids[3])] == 7 and after[(ids[2], ids[3])] == 3
    elif scenario in ["competing", "outbound"]:
        assert sorted(code for code, _ in results) == ["INSUFFICIENT_STOCK", "ok"]
        assert after[(ids[1], ids[3])] == 3
        assert count["stock_transfers"] == (
            1 if scenario == "competing" else 1 if count["inbounds"] else 0
        )
    else:
        assert [code for code, _ in results] == ["ok", "ok"]
        assert count["stock_transfers"] == (2 if scenario == "opposite" else 1)
        if scenario == "inbound":
            assert after[(ids[2], ids[3])] == 7
    accepted_outbound = scenario == "outbound" and count["stock_transfers"] == 0
    assert sum(after.values()) == before + (
        4 if scenario == "inbound" else -7 if accepted_outbound else 0
    )
    assert count["movement_provenance"] == count["transactions"]


def test_transfer_observably_waits_and_uses_holder_committed_balance(
    postgres_session, postgres_engine
):
    ids = seed_transfer(postgres_session)
    holder = Session(postgres_engine)
    locked = holder.scalar(
        select(Stock)
        .where(Stock.warehouse_id == ids[1], Stock.product_id == ids[3])
        .with_for_update()
    )
    locked.quantity = 6
    holder.flush()
    started = Event()
    pid = []

    def run():
        with Session(postgres_engine) as session:
            pid.append(session.scalar(text("SELECT pg_backend_pid()")))
            started.set()
            try:
                TransferService(TransferRepository(session)).create(
                    ids[0], uuid4(), request_for(ids, 7)
                )
                return "unexpected success"
            except DomainError as exc:
                return exc.code

    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(run)
            assert started.wait(5)
            deadline = monotonic() + 2
            observed = False
            while monotonic() < deadline:
                with postgres_engine.connect() as observer:
                    observed = bool(
                        observer.scalar(
                            text("SELECT cardinality(pg_blocking_pids(:pid)) > 0"), {"pid": pid[0]}
                        )
                    )
                if observed:
                    break
                sleep(0.01)
            assert observed, "PostgreSQL must report a real blocking session"
            holder.commit()
            assert future.result(timeout=10) == "INSUFFICIENT_STOCK"
    finally:
        holder.close()
    assert balances(postgres_session)[(ids[1], ids[3])] == 6
    assert row_counts(postgres_session)["stock_transfers"] == 0


@pytest.mark.parametrize(
    "sqlstate,failures,expected_attempts",
    [
        ("40P01", 1, 2),
        ("40001", 2, 3),
        ("40P01", 3, 3),
        ("40001", 3, 3),
        ("55P03", 1, 1),
    ],
)
def test_actual_sqlstate_retries_roll_back_whole_attempt_and_are_bounded(
    postgres_session,
    monkeypatch,
    sqlstate,
    failures,
    expected_attempts,
):
    ids = seed_transfer(postgres_session)
    repository = TransferRepository(postgres_session)
    original = repository.add_leg
    attempts, advisory_queries = [], []

    def capture(_connection, _cursor, statement, _parameters, _context, _executemany):
        if "pg_advisory_xact_lock" in statement:
            advisory_queries.append(statement)

    def injected(**kwargs):
        if kwargs["direction"] == "outbound":
            attempts.append(1)
            if len(attempts) <= failures:
                postgres_session.execute(
                    text(
                        "DO $$ BEGIN RAISE EXCEPTION 'injected retry' USING ERRCODE='"
                        + sqlstate
                        + "'; END $$;"
                    )
                )
        return original(**kwargs)

    monkeypatch.setattr(repository, "add_leg", injected)
    event.listen(postgres_session.bind, "before_cursor_execute", capture)
    before = balances(postgres_session)
    try:
        if failures < 3 and sqlstate != "55P03":
            result, replay = TransferService(repository).create(ids[0], uuid4(), request_for(ids))
            assert not replay and result.source_quantity_before == 10
            assert balances(postgres_session)[(ids[1], ids[3])] == 7
        else:
            with pytest.raises(DomainError) as exc:
                TransferService(repository).create(ids[0], uuid4(), request_for(ids))
            assert exc.value.status_code == 503 and exc.value.code == "TRANSFER_RETRY_REQUIRED"
            assert balances(postgres_session) == before
            assert row_counts(postgres_session)["stock_transfers"] == 0
    finally:
        event.remove(postgres_session.bind, "before_cursor_execute", capture)
    assert len(attempts) == expected_attempts
    assert len(advisory_queries) == expected_attempts


def observe_blocked(engine, pid, timeout=2):
    deadline = monotonic() + timeout
    while monotonic() < deadline:
        with engine.connect() as observer:
            if observer.scalar(
                text("SELECT cardinality(pg_blocking_pids(:pid)) > 0"), {"pid": pid}
            ):
                return True
        sleep(0.01)
    return False


@pytest.mark.parametrize("scenario", ["first_destination", "first_inbound", "opposite"])
def test_controlled_overlapping_writers_observed_by_postgres(
    postgres_session,
    postgres_engine,
    monkeypatch,
    scenario,
):
    ids = seed_transfer(postgres_session, destination=2 if scenario == "opposite" else None)
    locked, release, contender_started = Event(), Event(), Event()
    original = TransferRepository.lock_stock
    traces = {"holder": [], "contender": []}
    contender_pid = []

    def held_destination(repository, warehouse_id, product_id):
        worker = repository.session.info["worker"]
        traces[worker].append((warehouse_id, product_id))
        row = original(repository, warehouse_id, product_id)
        if worker == "holder" and warehouse_id == ids[2]:
            locked.set()
            assert release.wait(10), "holder was never released"
        return row

    monkeypatch.setattr(TransferRepository, "lock_stock", held_destination)

    def run_holder():
        with Session(postgres_engine, info={"worker": "holder"}) as session:
            return (
                TransferService(TransferRepository(session))
                .create(ids[0], uuid4(), request_for(ids))[0]
                .id
            )

    def run_contender():
        with Session(postgres_engine, info={"worker": "contender"}) as session:
            contender_pid.append(session.scalar(text("SELECT pg_backend_pid()")))
            contender_started.set()
            if scenario == "first_inbound":
                return (
                    InventoryService(InventoryRepository(session))
                    .create_inbound(
                        ids[0],
                        InventoryMovementCreate(warehouse_id=ids[2], product_id=ids[3], quantity=4),
                    )
                    .id
                )
            request = request_for(ids, 4 if scenario == "first_destination" else 3)
            request = request.model_copy(
                update={
                    "source_warehouse_id": ids[2] + 1
                    if scenario == "first_destination"
                    else ids[2],
                    "destination_warehouse_id": ids[2]
                    if scenario == "first_destination"
                    else ids[1],
                }
            )
            return (
                TransferService(TransferRepository(session)).create(ids[0], uuid4(), request)[0].id
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        holder_future = pool.submit(run_holder)
        try:
            assert locked.wait(5), "first transfer never locked/inserted destination"
            contender_future = pool.submit(run_contender)
            assert contender_started.wait(5)
            assert observe_blocked(postgres_engine, contender_pid[0]), (
                "writers did not overlap in PostgreSQL"
            )
        finally:
            release.set()
        holder_future.result(timeout=15)
        contender_future.result(timeout=15)
    final = balances(postgres_session)
    assert final[(ids[1], ids[3])] == (10 if scenario == "opposite" else 7)
    assert final[(ids[2], ids[3])] == (2 if scenario == "opposite" else 7)
    if scenario == "first_destination":
        assert final[(ids[2] + 1, ids[3])] == 87
    rows = list(
        postgres_session.scalars(
            select(Stock).where(Stock.warehouse_id == ids[2], Stock.product_id == ids[3])
        )
    )
    assert len(rows) == 1
    expected_transfers = 1 if scenario == "first_inbound" else 2
    assert row_counts(postgres_session) == {
        "stock_transfers": expected_transfers,
        "inbounds": 2,
        "outbounds": expected_transfers,
        "transactions": 3 if scenario == "first_inbound" else 4,
        "movement_provenance": 3 if scenario == "first_inbound" else 4,
        "audit_logs": 0,
    }
    assert traces["holder"] == [(ids[1], ids[3]), (ids[2], ids[3])]
    if scenario == "opposite":
        assert traces["contender"] == traces["holder"]


def test_real_three_second_lock_timeout_returns_retry_required_without_effects(
    postgres_session,
    postgres_engine,
):
    ids = seed_transfer(postgres_session)
    before = balances(postgres_session)
    holder = Session(postgres_engine)
    holder.scalar(
        select(Stock)
        .where(Stock.warehouse_id == ids[1], Stock.product_id == ids[3])
        .with_for_update()
    )
    started, pid = Event(), []

    def run():
        with Session(postgres_engine) as session:
            pid.append(session.scalar(text("SELECT pg_backend_pid()")))
            started.set()
            beginning = monotonic()
            with pytest.raises(DomainError) as exc:
                TransferService(TransferRepository(session)).create(
                    ids[0], uuid4(), request_for(ids)
                )
            assert exc.value.status_code == 503 and exc.value.code == "TRANSFER_RETRY_REQUIRED"
            return monotonic() - beginning

    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(run)
            assert started.wait(5)
            assert observe_blocked(postgres_engine, pid[0])
            assert 2.5 <= future.result(timeout=8) <= 7
    finally:
        holder.rollback()
        holder.close()
    assert balances(postgres_session) == before
    assert all(value == 0 for value in row_counts(postgres_session).values())
