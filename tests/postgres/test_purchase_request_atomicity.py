"""Real PG atomic effects and rollback; fault injections are explicitly bounded."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import event, select, update

from app.core.errors import DomainError
from app.models import (
    MovementProvenance,
    Outbound,
    Product,
    PurchaseRequest,
    PurchaseRequestWorkflow,
    Stock,
    StockTransaction,
    User,
    Warehouse,
)
from app.purchase_requests.repository import PurchaseRequestRepository
from app.purchase_requests.schemas import PurchaseRequestCreate, PurchaseRequestReject
from app.purchase_requests.service import PurchaseRequestService

from .test_purchase_requests_api import body_for, effects, seed_purchase

pytestmark = pytest.mark.postgres


def service_for(session):
    return PurchaseRequestService(PurchaseRequestRepository(session))


def actor(session, ids, role):
    return session.get(User, ids[role], populate_existing=True)


def approved_request(session, ids, quantity=3):
    body = PurchaseRequestCreate(**body_for(ids, quantity=quantity))
    row, _ = service_for(session).create(actor(session, ids, "client"), uuid4(), body)
    base = session.get(PurchaseRequest, row.id)
    workflow = session.get(PurchaseRequestWorkflow, row.id)
    base.status = "approved"
    workflow.decision_kind = "approved"
    workflow.decided_by_id = ids["admin"]
    workflow.decided_at = datetime(2026, 10, 19, tzinfo=UTC)
    session.commit()
    return row.id


def stock_quantity(session, ids):
    session.expire_all()
    return session.scalar(
        select(Stock.quantity).where(
            Stock.warehouse_id == ids["source"], Stock.product_id == ids["product"]
        )
    )


def test_fulfill_is_one_linked_commit(postgres_session):
    session = postgres_session
    ids = seed_purchase(session)
    request_id = approved_request(session, ids)
    service = service_for(session)
    commits = []
    event.listen(session, "after_commit", lambda _: commits.append(1))
    result = service.fulfill(actor(session, ids, "warehouse"), request_id)
    assert len(commits) == 1
    assert result.status == "fulfilled" and result.fulfillment.quantity_before == 10
    assert result.fulfillment.quantity_after == 7 and stock_quantity(session, ids) == 7
    assert effects(session) == {
        "purchase_requests": 1,
        "purchase_request_workflows": 1,
        "stocks": 1,
        "inbounds": 0,
        "outbounds": 1,
        "transactions": 1,
        "movement_provenance": 1,
    }
    fulfillment = result.fulfillment
    outbound = session.get(Outbound, fulfillment.outbound_id)
    transaction = session.get(StockTransaction, fulfillment.transaction_id)
    purpose = session.get(MovementProvenance, transaction.id)
    assert (
        outbound.warehouse_id,
        outbound.product_id,
        outbound.quantity,
        outbound.created_by_id,
        outbound.reference,
        outbound.note,
    ) == (ids["source"], ids["product"], 3, ids["warehouse"], result.request_number, "yêu cầu")
    assert (
        transaction.transaction_type,
        transaction.outbound_id,
        transaction.inbound_id,
        transaction.warehouse_id,
        transaction.product_id,
        transaction.quantity,
        transaction.created_by_id,
    ) == ("outbound", outbound.id, None, ids["source"], ids["product"], 3, ids["warehouse"])
    assert (purpose.purpose, purpose.transfer_id) == ("purchase_request_fulfillment", None)
    session.execute(update(Stock).values(quantity=41))
    session.execute(update(Product).values(is_active=False))
    session.commit()
    repeated = service.fulfill(actor(session, ids, "admin"), request_id)
    assert repeated == result and stock_quantity(session, ids) == 41
    assert effects(session)["outbounds"] == 1


@pytest.mark.parametrize("state", ["pending", "approved", "rejected", "fulfilled"])
@pytest.mark.parametrize("action", ["approve", "reject", "fulfill"])
def test_transition_matrix_and_immutable_repeats(postgres_session, state, action):
    session = postgres_session
    ids = seed_purchase(session)
    service = service_for(session)
    client = actor(session, ids, "client")
    key, body = uuid4(), PurchaseRequestCreate(**body_for(ids))
    created, _ = service.create(client, key, body)
    admin = actor(session, ids, "admin")
    current = created
    if state in ("approved", "fulfilled"):
        current = service.approve(admin, created.id)
    elif state == "rejected":
        current = service.reject(admin, created.id, PurchaseRequestReject(rejection_reason="lý do"))
    if state == "fulfilled":
        current = service.fulfill(actor(session, ids, "warehouse"), created.id)
    before = effects(session), stock_quantity(session, ids)
    allowed = (
        (action == "approve" and state != "rejected")
        or (action == "reject" and state in ("pending", "rejected"))
        or (action == "fulfill" and state in ("approved", "fulfilled"))
    )
    method = getattr(service, action)
    args = [actor(session, ids, "admin"), created.id]
    if action == "reject":
        args.append(PurchaseRequestReject(rejection_reason="  lý do  "))
    if allowed:
        result = method(*args)
        expected = (
            "fulfilled"
            if action == "fulfill" or state == "fulfilled"
            else ("approved" if action == "approve" else "rejected")
        )
        assert result.status == expected
        if state != "pending" and not (action == "fulfill" and state == "approved"):
            assert result == current
    else:
        with pytest.raises(DomainError) as exc:
            method(*args)
        assert exc.value.code == "PURCHASE_REQUEST_STATE_CONFLICT"
    if action != "fulfill" or state != "approved":
        assert (effects(session), stock_quantity(session, ids)) == before
    # Replay must reflect later status, not a stale creation snapshot.
    latest = service.get(actor(session, ids, "client"), created.id)
    replay, is_replay = service.create(actor(session, ids, "client"), key, body)
    assert is_replay and replay == latest
    if latest.status == "rejected":
        with pytest.raises(DomainError) as exc:
            service.reject(
                actor(session, ids, "admin"),
                created.id,
                PurchaseRequestReject(rejection_reason="different"),
            )
        assert exc.value.code == "PURCHASE_REQUEST_STATE_CONFLICT"


@pytest.mark.parametrize("stage", [1, 2, 3, 4, "before_commit"])
def test_each_write_failure_rolls_back(postgres_session, monkeypatch, stage):
    session = postgres_session
    ids = seed_purchase(session)
    request_id = approved_request(session, ids)
    before = effects(session), service_for(session).get(actor(session, ids, "admin"), request_id)
    repository = PurchaseRequestRepository(session)
    original, calls = repository.flush, []

    def injected():
        original()
        calls.append(1)
        if len(calls) == stage:
            raise RuntimeError("injected after flush")

    def fail_commit(_):
        raise RuntimeError("injected before commit")

    monkeypatch.setattr(repository, "flush", injected)
    if stage == "before_commit":
        event.listen(session, "before_commit", fail_commit)
    try:
        with pytest.raises(RuntimeError, match="injected"):
            PurchaseRequestService(repository).fulfill(actor(session, ids, "warehouse"), request_id)
    finally:
        if stage == "before_commit":
            event.remove(session, "before_commit", fail_commit)
    assert stock_quantity(session, ids) == 10
    assert effects(session) == before[0]
    assert service_for(session).get(actor(session, ids, "admin"), request_id) == before[1]


@pytest.mark.parametrize("operation", ["create", "approve", "reject"])
@pytest.mark.parametrize("stage", ["flush", "commit"])
def test_creation_and_decision_failures_leave_no_partial_state(
    postgres_session, monkeypatch, operation, stage
):
    session = postgres_session
    ids = seed_purchase(session)
    service = service_for(session)
    body = PurchaseRequestCreate(**body_for(ids))
    row = None
    if operation != "create":
        row, _ = service.create(actor(session, ids, "client"), uuid4(), body)
    before = effects(session)

    def fail(*args):
        raise RuntimeError("injected write failure")

    target = service.repository if stage == "flush" else session
    with monkeypatch.context() as patch:
        patch.setattr(target, stage, fail)
        with pytest.raises(RuntimeError, match="injected"):
            if operation == "create":
                service.create(actor(session, ids, "client"), uuid4(), body)
            elif operation == "approve":
                service.approve(actor(session, ids, "admin"), row.id)
            else:
                service.reject(
                    actor(session, ids, "admin"),
                    row.id,
                    PurchaseRequestReject(rejection_reason="reason"),
                )
    assert effects(session) == before and stock_quantity(session, ids) == 10
    if row is not None:
        assert service.get(actor(session, ids, "admin"), row.id) == row


@pytest.mark.parametrize("quantity,active", [(None, True), (2, True), (10, False)])
def test_missing_insufficient_or_inactive_fulfillment_has_no_effect(
    postgres_session, quantity, active
):
    session = postgres_session
    ids = seed_purchase(session, quantity=quantity)
    request_id = approved_request(session, ids)
    session.execute(update(Product).values(is_active=active))
    session.commit()
    before = effects(session)
    with pytest.raises(DomainError) as exc:
        service_for(session).fulfill(actor(session, ids, "warehouse"), request_id)
    assert exc.value.code == ("PRODUCT_NOT_REQUESTABLE" if not active else "INSUFFICIENT_STOCK")
    assert effects(session) == before and stock_quantity(session, ids) == quantity
    assert session.get(PurchaseRequest, request_id).status == "approved"


def test_preloaded_stock_identity_is_refreshed_under_lock(postgres_session, postgres_engine):
    session = postgres_session
    ids = seed_purchase(session)
    request_id = approved_request(session, ids, 7)
    stale = session.scalar(select(Stock))
    assert stale.quantity == 10
    with postgres_engine.begin() as writer:
        writer.execute(update(Stock).values(quantity=6))
    with pytest.raises(DomainError) as exc:
        service_for(session).fulfill(actor(session, ids, "warehouse"), request_id)
    assert exc.value.code == "INSUFFICIENT_STOCK" and stock_quantity(session, ids) == 6


@pytest.mark.parametrize(
    "role,operation",
    [("admin", "create"), ("warehouse", "approve"), ("client", "reject"), ("client", "fulfill")],
)
def test_service_permission_boundary_precedes_lookup(postgres_session, role, operation):
    session = postgres_session
    ids = seed_purchase(session)
    service = service_for(session)
    args = [actor(session, ids, role), 999]
    if operation == "create":
        args = [args[0], uuid4(), PurchaseRequestCreate(**body_for(ids))]
    elif operation == "reject":
        args.append(PurchaseRequestReject(rejection_reason="reason"))
    with pytest.raises(DomainError) as exc:
        getattr(service, operation)(*args)
    assert exc.value.status_code == 403


@pytest.mark.parametrize(
    "corruption",
    [
        "owner",
        "status",
        "quantity",
        "fingerprint",
        "balance",
        "outbound",
        "transaction",
        "purpose",
        "warehouse_bounds",
    ],
)
def test_corrupt_managed_state_is_rejected_without_writes(postgres_session, corruption):
    session = postgres_session
    ids = seed_purchase(session)
    request_id = approved_request(session, ids)
    service = service_for(session)
    complete = service.fulfill(actor(session, ids, "warehouse"), request_id)
    if corruption == "warehouse_bounds":
        session.add(
            Warehouse(id=-1, code="M4-CORRUPT", name="M4 corrupt reference", address="Fixture")
        )
        session.flush()
        session.execute(update(PurchaseRequest).values(warehouse_id=-1))
    elif corruption == "owner":
        session.execute(update(PurchaseRequestWorkflow).values(created_by_id=ids["other"]))
    elif corruption == "status":
        session.execute(update(PurchaseRequest).values(status="pending"))
    elif corruption == "quantity":
        session.execute(update(PurchaseRequest).values(quantity=4))
    elif corruption == "fingerprint":
        session.execute(update(PurchaseRequestWorkflow).values(request_fingerprint="f" * 64))
    elif corruption == "balance":
        session.execute(update(PurchaseRequestWorkflow).values(quantity_before=11))
    elif corruption == "outbound":
        session.execute(update(Outbound).values(quantity=4))
    elif corruption == "transaction":
        session.execute(update(StockTransaction).values(created_by_id=ids["admin"]))
    else:
        session.execute(update(MovementProvenance).values(purpose="standard_outbound"))
    session.commit()
    before = effects(session)
    for operation in ("get", "approve", "fulfill"):
        with pytest.raises(DomainError) as exc:
            getattr(service, operation)(actor(session, ids, "admin"), request_id)
        assert exc.value.code == "PURCHASE_REQUEST_STATE_CONFLICT"
    assert effects(session) == before and stock_quantity(session, ids) == 7
    assert (
        session.get(PurchaseRequestWorkflow, request_id).fulfilled_at
        == complete.fulfillment.fulfilled_at
    )


def test_new_approval_requires_active_product_but_decision_replay_does_not(postgres_session):
    session = postgres_session
    ids = seed_purchase(session)
    service = service_for(session)
    row, _ = service.create(
        actor(session, ids, "client"), uuid4(), PurchaseRequestCreate(**body_for(ids))
    )
    session.execute(update(Product).values(is_active=False))
    session.commit()
    with pytest.raises(DomainError) as exc:
        service.approve(actor(session, ids, "admin"), row.id)
    assert exc.value.code == "PRODUCT_NOT_REQUESTABLE"
    assert service.get(actor(session, ids, "admin"), row.id) == row
    # Rejection does not require stock/product admission.
    rejected = service.reject(
        actor(session, ids, "admin"), row.id, PurchaseRequestReject(rejection_reason="reason")
    )
    assert (
        service.reject(
            actor(session, ids, "admin"), row.id, PurchaseRequestReject(rejection_reason=" reason ")
        )
        == rejected
    )
    assert stock_quantity(session, ids) == 10


def test_rollback_connection_loss_never_retries_a_deadlock_identity(postgres_session, monkeypatch):
    from sqlalchemy.exc import OperationalError

    session = postgres_session
    ids = seed_purchase(session)
    request_id = approved_request(session, ids)
    repository = PurchaseRequestRepository(session)
    original, flushes = repository.flush, []

    class Deadlock(Exception):
        sqlstate = "40P01"

    class LostConnection(Exception):
        sqlstate = "08006"

    def fail_once():
        original()
        flushes.append(1)
        if len(flushes) == 1:
            raise OperationalError(None, None, Deadlock("bounded rollback boundary"))

    def lost_rollback():
        raise OperationalError(
            None, None, LostConnection("bounded lost rollback"), connection_invalidated=True
        )

    with monkeypatch.context() as patch:
        patch.setattr(repository, "flush", fail_once)
        patch.setattr(session, "rollback", lost_rollback)
        with pytest.raises(DomainError) as exc:
            PurchaseRequestService(repository).fulfill(actor(session, ids, "warehouse"), request_id)
        assert exc.value.code == "PURCHASE_REQUEST_RETRY_REQUIRED"
    assert len(flushes) == 1
    assert stock_quantity(session, ids) == 10 and effects(session)["outbounds"] == 0
