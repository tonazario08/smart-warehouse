"""Real PostgreSQL atomicity, rollback and paired-provenance evidence."""

from uuid import uuid4

import pytest
from sqlalchemy import event, func, select
from sqlalchemy.orm import Session

from app.audit.models import AuditLog
from app.core.errors import DomainError
from app.inventory.repository import InventoryRepository
from app.inventory.schemas import InventoryMovementCreate
from app.inventory.service import InventoryService
from app.models import (
    Category,
    Inbound,
    MovementProvenance,
    Outbound,
    Product,
    Stock,
    StockTransaction,
    StockTransfer,
    User,
    Warehouse,
)
from app.transfers.repository import TransferRepository
from app.transfers.schemas import TransferCreate
from app.transfers.service import TransferService

pytestmark = pytest.mark.postgres


def seed_transfer(session: Session, *, source=10, destination=2, active=True):
    actor = User(email="transfer@example.test", password_hash="fixture", role="warehouse")
    warehouses = [
        Warehouse(code=f"TRANSFER-{i}", name=f"Transfer {i}", address="Fixture")
        for i in range(1, 4)
    ]
    category = Category(name="Transfer category")
    product = Product(
        sku="TRANSFER-1", name="Transfer product", category=category, unit="each", is_active=active
    )
    other = Product(sku="TRANSFER-2", name="Other product", category=category, unit="each")
    session.add_all([actor, *warehouses, product, other])
    session.flush()
    if source is not None:
        session.add(Stock(warehouse_id=warehouses[0].id, product_id=product.id, quantity=source))
    if destination is not None:
        session.add(
            Stock(warehouse_id=warehouses[1].id, product_id=product.id, quantity=destination)
        )
    session.add_all(
        [
            Stock(warehouse_id=warehouses[2].id, product_id=product.id, quantity=91),
            Stock(warehouse_id=warehouses[0].id, product_id=other.id, quantity=47),
        ]
    )
    session.commit()
    return actor.id, warehouses[0].id, warehouses[1].id, product.id


def balances(session):
    session.expire_all()
    return {
        (row.warehouse_id, row.product_id): row.quantity for row in session.scalars(select(Stock))
    }


def row_counts(session):
    return {
        model.__tablename__: session.scalar(select(func.count()).select_from(model))
        for model in [
            StockTransfer,
            Inbound,
            Outbound,
            StockTransaction,
            MovementProvenance,
            AuditLog,
        ]
    }


def request_for(ids, quantity=3):
    actor, source, destination, product = ids
    return TransferCreate(
        source_warehouse_id=source,
        destination_warehouse_id=destination,
        product_id=product,
        quantity=quantity,
        reference="CK-01",
        note="Fixture",
    )


@pytest.mark.parametrize("active", [True, False])
def test_transfer_commits_one_paired_operation_and_historical_snapshots(postgres_session, active):
    session = postgres_session
    ids = seed_transfer(session, active=active)
    before = balances(session)
    result, replay = TransferService(TransferRepository(session)).create(
        ids[0], uuid4(), request_for(ids)
    )
    after = balances(session)
    assert after[(ids[1], ids[3])] == 7
    assert after[(ids[2], ids[3])] == 5
    assert sum(after.values()) == sum(before.values())
    assert {
        key: value
        for key, value in after.items()
        if key not in [(ids[1], ids[3]), (ids[2], ids[3])]
    } == {
        key: value
        for key, value in before.items()
        if key not in [(ids[1], ids[3]), (ids[2], ids[3])]
    }
    assert replay is False and result.id is not None
    assert (
        result.source_quantity_before,
        result.source_quantity_after,
        result.destination_quantity_before,
        result.destination_quantity_after,
    ) == (10, 7, 2, 5)
    assert row_counts(session) == {
        "stock_transfers": 1,
        "inbounds": 1,
        "outbounds": 1,
        "transactions": 2,
        "movement_provenance": 2,
        "audit_logs": 0,
    }
    for direction, warehouse_id, movement_id, transaction_id, purpose in [
        ("outbound", ids[1], result.outbound_id, result.outbound_transaction_id, "transfer_out"),
        ("inbound", ids[2], result.inbound_id, result.inbound_transaction_id, "transfer_in"),
    ]:
        transaction = session.get(StockTransaction, transaction_id)
        movement = session.get(Outbound if direction == "outbound" else Inbound, movement_id)
        assert (
            transaction.transaction_type,
            transaction.warehouse_id,
            transaction.product_id,
            transaction.quantity,
            transaction.created_by_id,
        ) == (direction, warehouse_id, ids[3], 3, ids[0])
        assert (
            movement.warehouse_id,
            movement.product_id,
            movement.quantity,
            movement.created_by_id,
        ) == (warehouse_id, ids[3], 3, ids[0])
        assert getattr(transaction, direction + "_id") == movement_id
        provenance = session.get(MovementProvenance, transaction_id)
        assert (provenance.purpose, provenance.transfer_id) == (purpose, result.id)
    assert session.get(Product, ids[3]).is_active is active


@pytest.mark.parametrize(
    "source,destination,active,code",
    [
        (None, None, True, "INSUFFICIENT_STOCK"),
        (2, None, False, "INSUFFICIENT_STOCK"),
        (10, 2_147_483_647, True, "STOCK_QUANTITY_LIMIT_EXCEEDED"),
    ],
)
def test_domain_rejection_rolls_back_speculative_stock_and_every_row(
    postgres_session,
    source,
    destination,
    active,
    code,
):
    session = postgres_session
    ids = seed_transfer(session, source=source, destination=destination, active=active)
    before = balances(session)
    with pytest.raises(DomainError) as exc:
        TransferService(TransferRepository(session)).create(ids[0], uuid4(), request_for(ids))
    assert exc.value.code == code
    assert balances(session) == before
    assert all(value == 0 for value in row_counts(session).values())


@pytest.mark.parametrize(
    "field,code",
    [
        ("product_id", "PRODUCT_NOT_FOUND"),
        ("source_warehouse_id", "WAREHOUSE_NOT_FOUND"),
        ("destination_warehouse_id", "WAREHOUSE_NOT_FOUND"),
    ],
)
def test_missing_references_are_rejected_without_stock_creation(postgres_session, field, code):
    ids = seed_transfer(postgres_session)
    before = balances(postgres_session)
    request = request_for(ids).model_copy(update={field: 2147483647})
    with pytest.raises(DomainError) as exc:
        TransferService(TransferRepository(postgres_session)).create(ids[0], uuid4(), request)
    assert exc.value.code == code
    assert balances(postgres_session) == before
    assert all(value == 0 for value in row_counts(postgres_session).values())


@pytest.mark.parametrize(
    "stage",
    [
        "source",
        "destination",
        "outbound",
        "inbound",
        "transaction_outbound",
        "transaction_inbound",
        "transfer",
        "provenance_transfer_out",
        "provenance_transfer_in",
        "commit",
    ],
)
def test_failure_after_each_write_stage_rolls_back_all_effects(postgres_session, stage):
    session = postgres_session
    ids = seed_transfer(session, destination=None)
    before = balances(session)

    def fail_at_stage(current, _context=None):
        for row in [*current.dirty, *current.new]:
            actual = None
            if isinstance(row, Stock):
                actual = "source" if row.warehouse_id == ids[1] else "destination"
            if isinstance(row, Outbound):
                actual = "outbound"
            if isinstance(row, Inbound):
                actual = "inbound"
            if isinstance(row, StockTransaction):
                actual = "transaction_" + row.transaction_type
            if isinstance(row, StockTransfer):
                actual = "transfer"
            if isinstance(row, MovementProvenance):
                actual = "provenance_" + row.purpose
            if actual == stage:
                raise RuntimeError("injected write failure")

    def fail_commit(_current):
        raise RuntimeError("injected write failure")

    event_name = "before_commit" if stage == "commit" else "after_flush"
    callback = fail_commit if stage == "commit" else fail_at_stage
    event.listen(session, event_name, callback)
    try:
        with pytest.raises(RuntimeError, match="injected write failure"):
            TransferService(TransferRepository(session)).create(ids[0], uuid4(), request_for(ids))
    finally:
        event.remove(session, event_name, callback)
    assert balances(session) == before
    assert all(value == 0 for value in row_counts(session).values())


def test_locked_stock_refreshes_a_previously_loaded_identity(postgres_session, postgres_engine):
    session = postgres_session
    ids = seed_transfer(session)
    loaded = session.scalar(
        select(Stock).where(Stock.warehouse_id == ids[1], Stock.product_id == ids[3])
    )
    assert loaded.quantity == 10
    with Session(postgres_engine) as other:
        other.scalar(select(Stock).where(Stock.id == loaded.id)).quantity = 6
        other.commit()
    result, _ = TransferService(TransferRepository(session)).create(
        ids[0], uuid4(), request_for(ids)
    )
    assert result.source_quantity_before == 6
    assert balances(session)[(ids[1], ids[3])] == 3


def test_ordinary_endpoints_add_neutral_provenance_in_their_own_transaction(postgres_session):
    ids = seed_transfer(postgres_session)
    service = InventoryService(InventoryRepository(postgres_session))
    request = InventoryMovementCreate(warehouse_id=ids[1], product_id=ids[3], quantity=1)
    service.create_inbound(ids[0], request)
    service.create_outbound(ids[0], request)
    assert [
        (row.purpose, row.transfer_id)
        for row in postgres_session.scalars(
            select(MovementProvenance).order_by(MovementProvenance.transaction_id)
        )
    ] == [("standard_inbound", None), ("standard_outbound", None)]
