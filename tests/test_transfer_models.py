"""SQLite verifies portable table constraints only, never PostgreSQL locking."""

from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, event, insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models import (
    Category,
    Inbound,
    MovementProvenance,
    Outbound,
    Product,
    StockTransaction,
    StockTransfer,
    User,
    Warehouse,
)


@pytest.fixture
def model_session():
    engine = create_engine("sqlite+pysqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    with Session(engine) as session:
        session.execute(
            insert(User),
            [
                {
                    "id": 1,
                    "email": "actor@example.test",
                    "password_hash": "fixture",
                    "role": "admin",
                },
                {
                    "id": 2,
                    "email": "other@example.test",
                    "password_hash": "fixture",
                    "role": "warehouse",
                },
            ],
        )
        session.execute(insert(Category), {"id": 1, "name": "Fixture category"})
        session.execute(
            insert(Product),
            {
                "id": 1,
                "sku": "TRANSFER",
                "name": "Fixture",
                "category_id": 1,
                "unit": "cái",
            },
        )
        session.execute(
            insert(Warehouse),
            [
                {"id": 1, "code": "SOURCE", "name": "Source", "address": "Fixture source"},
                {"id": 2, "code": "TARGET", "name": "Target", "address": "Fixture destination"},
            ],
        )
        for leg_id in [1, 2]:
            common = {"id": leg_id, "product_id": 1, "quantity": 3, "created_by_id": 1}
            session.execute(insert(Outbound), {**common, "warehouse_id": 1})
            session.execute(insert(Inbound), {**common, "warehouse_id": 2})
            session.execute(
                insert(StockTransaction),
                {
                    **common,
                    "id": 2 * leg_id - 1,
                    "transaction_type": "outbound",
                    "warehouse_id": 1,
                    "outbound_id": leg_id,
                },
            )
            session.execute(
                insert(StockTransaction),
                {
                    **common,
                    "id": 2 * leg_id,
                    "transaction_type": "inbound",
                    "warehouse_id": 2,
                    "inbound_id": leg_id,
                },
            )
        session.commit()
        yield session
    engine.dispose()


def transfer_values(**overrides):
    return {
        "source_warehouse_id": 1,
        "destination_warehouse_id": 2,
        "product_id": 1,
        "created_by_id": 1,
        "quantity": 3,
        "idempotency_key": uuid4(),
        "request_fingerprint": "a" * 64,
        "source_quantity_before": 10,
        "source_quantity_after": 7,
        "destination_quantity_before": 2,
        "destination_quantity_after": 5,
        "outbound_id": 1,
        "inbound_id": 1,
        "outbound_transaction_id": 1,
        "inbound_transaction_id": 2,
        **overrides,
    }


@pytest.mark.parametrize(
    "changes",
    [
        {"quantity": 0},
        {"quantity": -1},
        {"quantity": 2_147_483_648},
        {"destination_warehouse_id": 1},
        {"source_quantity_before": -1},
        {"source_quantity_after": -1},
        {"destination_quantity_before": -1},
        {"destination_quantity_after": -1},
        {"source_quantity_before": 2_147_483_648},
        {"source_quantity_after": 2_147_483_648},
        {"destination_quantity_before": 2_147_483_648},
        {"destination_quantity_after": 2_147_483_648},
    ],
)
def test_invalid_transfer_bounds_rejected(model_session, changes):
    with pytest.raises(IntegrityError):
        model_session.execute(insert(StockTransfer), transfer_values(**changes))
        model_session.commit()


@pytest.mark.parametrize(
    "link",
    [
        "outbound_id",
        "inbound_id",
        "outbound_transaction_id",
        "inbound_transaction_id",
    ],
)
def test_movement_links_cannot_be_reused(model_session, link):
    model_session.execute(insert(StockTransfer), transfer_values())
    second = transfer_values(
        outbound_id=2,
        inbound_id=2,
        outbound_transaction_id=3,
        inbound_transaction_id=4,
    )
    second[link] = {
        "outbound_id": 1,
        "inbound_id": 1,
        "outbound_transaction_id": 1,
        "inbound_transaction_id": 2,
    }[link]
    with pytest.raises(IntegrityError):
        model_session.execute(insert(StockTransfer), second)


def test_idempotency_is_actor_scoped_and_durable(model_session):
    key = UUID("839f681b-6fa6-4a1a-96fc-d37b4e3aa36d")
    model_session.execute(insert(StockTransfer), transfer_values(idempotency_key=key))
    model_session.commit()
    second = transfer_values(
        outbound_id=2,
        inbound_id=2,
        outbound_transaction_id=3,
        inbound_transaction_id=4,
        idempotency_key=key,
    )
    with pytest.raises(IntegrityError):
        model_session.execute(insert(StockTransfer), second)
    model_session.rollback()
    model_session.execute(insert(StockTransfer), {**second, "created_by_id": 2})
    model_session.commit()
    assert len(model_session.scalars(select(StockTransfer)).all()) == 2


@pytest.mark.parametrize(
    "purpose,transfer_id",
    [
        ("sales", None),
        ("transfer_in", None),
        ("transfer_out", None),
        ("legacy_unknown", 1),
        ("standard_inbound", 1),
        ("standard_outbound", 1),
    ],
)
def test_provenance_rejects_invented_purpose_and_link_inconsistency(
    model_session,
    purpose,
    transfer_id,
):
    model_session.execute(insert(StockTransfer), transfer_values(id=1))
    with pytest.raises(IntegrityError):
        model_session.execute(
            insert(MovementProvenance),
            {
                "transaction_id": 1,
                "purpose": purpose,
                "transfer_id": transfer_id,
            },
        )


def test_transfer_provenance_and_restrict_links(model_session):
    model_session.execute(insert(StockTransfer), transfer_values(id=1))
    model_session.execute(
        insert(MovementProvenance),
        [
            {"transaction_id": 1, "purpose": "transfer_out", "transfer_id": 1},
            {"transaction_id": 2, "purpose": "transfer_in", "transfer_id": 1},
        ],
    )
    model_session.commit()
    assert [
        (row.purpose, row.transfer_id)
        for row in model_session.scalars(
            select(MovementProvenance).order_by(MovementProvenance.transaction_id)
        )
    ] == [("transfer_out", 1), ("transfer_in", 1)]
    with pytest.raises(IntegrityError):
        model_session.delete(model_session.get(StockTransfer, 1))
        model_session.commit()
