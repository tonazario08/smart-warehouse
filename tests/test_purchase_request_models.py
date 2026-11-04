"""Portable workflow CHECK behavior; SQLite does not establish PG locking."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import CheckConstraint, UniqueConstraint, create_engine, delete, event, insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models import (
    Category,
    Outbound,
    Product,
    PurchaseRequest,
    StockTransaction,
    User,
    Warehouse,
)
from app.transfers.schemas import MovementProvenanceResponse

WORKFLOW_COLUMNS = {
    "purchase_request_id",
    "created_by_id",
    "idempotency_key",
    "request_fingerprint",
    "note",
    "decision_kind",
    "decided_by_id",
    "decided_at",
    "rejection_reason",
    "fulfilled_by_id",
    "fulfilled_at",
    "outbound_id",
    "outbound_transaction_id",
    "quantity_before",
    "quantity_after",
}
CHECKS = {
    "ck_pr_workflow_fingerprint",
    "ck_pr_workflow_note",
    "ck_pr_workflow_decision",
    "ck_pr_workflow_fulfillment",
    "ck_pr_workflow_balances",
}
UNIQUES = {
    "uq_purchase_request_workflows_actor_key",
    "uq_purchase_request_workflows_outbound",
    "uq_purchase_request_workflows_transaction",
}
NOW = datetime(2026, 10, 19, tzinfo=UTC)


def test_workflow_metadata_contract():
    import app.models as models

    assert "purchase_request_workflows" in Base.metadata.tables
    table = Base.metadata.tables["purchase_request_workflows"]
    assert models.PurchaseRequestWorkflow.__table__ is table
    assert set(table.columns.keys()) == WORKFLOW_COLUMNS
    assert [column.name for column in table.primary_key] == ["purchase_request_id"]
    assert {c.name for c in table.constraints if isinstance(c, CheckConstraint)} == CHECKS
    assert {c.name for c in table.constraints if isinstance(c, UniqueConstraint)} == UNIQUES
    assert len(table.foreign_keys) == 6
    assert all(key.ondelete == "RESTRICT" for key in table.foreign_keys)
    assert {
        index.name: tuple(c.name for c in index.columns)
        for index in PurchaseRequest.__table__.indexes
    } == {
        "ix_purchase_requests_owner_created_id": ("requested_by_id", "created_at", "id"),
        "ix_purchase_requests_created_id": ("created_at", "id"),
        "ix_purchase_requests_status_created_id": ("status", "created_at", "id"),
    }


def test_new_purpose_is_additive_without_response_field_changes():
    for purpose in (
        "legacy_unknown",
        "standard_inbound",
        "standard_outbound",
        "transfer_in",
        "transfer_out",
        "purchase_request_fulfillment",
    ):
        body = {"transaction_id": 4, "purpose": purpose, "transfer_id": None}
        assert MovementProvenanceResponse(**body).model_dump() == body


def seed_workflow_rows(session):
    """Use independent explicit IDs so the same constraints run on deployed PG."""
    session.execute(
        insert(User),
        [
            {
                "id": i,
                "email": f"m4-model-{i}@example.test",
                "password_hash": "fixture",
                "role": "client" if i == 1 else "admin",
            }
            for i in (1, 2)
        ],
    )
    session.execute(insert(Category), {"id": 1, "name": "M4 category"})
    session.execute(
        insert(Product),
        {"id": 1, "sku": "M4-MODEL", "name": "M4 product", "category_id": 1, "unit": "each"},
    )
    session.execute(
        insert(Warehouse),
        {"id": 1, "code": "M4-MODEL", "name": "M4 warehouse", "address": "M4 fixture"},
    )
    for i in (1, 2):
        session.execute(
            insert(PurchaseRequest),
            {
                "id": i,
                "request_number": f"PR-M4-{i}",
                "warehouse_id": 1,
                "product_id": 1,
                "quantity": 3,
                "status": "pending",
                "requested_by_id": 1,
            },
        )
        session.execute(
            insert(Outbound),
            {"id": i, "warehouse_id": 1, "product_id": 1, "quantity": 3, "created_by_id": 2},
        )
        session.execute(
            insert(StockTransaction),
            {
                "id": i,
                "transaction_type": "outbound",
                "warehouse_id": 1,
                "product_id": 1,
                "quantity": 3,
                "created_by_id": 2,
                "outbound_id": i,
            },
        )
    session.commit()


@pytest.fixture
def workflow_session():
    engine = create_engine("sqlite+pysqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    with Session(engine) as session:
        seed_workflow_rows(session)
        yield session
    engine.dispose()


def workflow_values(**changes):
    return {
        "purchase_request_id": 1,
        "created_by_id": 1,
        "idempotency_key": uuid4(),
        "request_fingerprint": "ab09" * 16,
        **changes,
    }


def approved_values(**changes):
    return workflow_values(decision_kind="approved", decided_by_id=2, decided_at=NOW, **changes)


def fulfilled_values(**changes):
    return approved_values(
        fulfilled_by_id=2,
        fulfilled_at=NOW,
        outbound_id=1,
        outbound_transaction_id=1,
        quantity_before=10,
        quantity_after=7,
        **changes,
    )


# Each case names the deployed CHECK it must violate. No service parity is inferred.
INVALID_WORKFLOWS = [
    (workflow_values(request_fingerprint=value), "ck_pr_workflow_fingerprint")
    for value in ("", "a" * 63, "a" * 65, "A" * 64, "g" * 64, "é" * 64)
] + [
    (workflow_values(note="n" * 2001), "ck_pr_workflow_note"),
    *[
        (workflow_values(**{field: value}), "ck_pr_workflow_decision")
        for field, value in (
            ("decision_kind", "approved"),
            ("decided_by_id", 2),
            ("decided_at", NOW),
            ("rejection_reason", "reason"),
        )
    ],
    *[
        ({**approved_values(), field: None}, "ck_pr_workflow_decision")
        for field in ("decision_kind", "decided_by_id", "decided_at")
    ],
    (approved_values(rejection_reason="unexpected"), "ck_pr_workflow_decision"),
    *[
        (
            {**approved_values(), "decision_kind": "rejected", "rejection_reason": reason},
            "ck_pr_workflow_decision",
        )
        for reason in (None, "", "   ", "\t\n", " reason ", "r" * 1001)
    ],
    *[
        (
            {**approved_values(), "decision_kind": "rejected", "rejection_reason": reason},
            "ck_pr_workflow_decision",
        )
        for reason in (
            "\treason\n",
            "\rreason\t",
            "\u00a0reason\u00a0",
            "\u2003reason\u202f",
            "\u3000",
            "\x1creason\x1f",
        )
    ],
    *[
        ({**fulfilled_values(), field: None}, "ck_pr_workflow_fulfillment")
        for field in (
            "fulfilled_by_id",
            "fulfilled_at",
            "outbound_id",
            "outbound_transaction_id",
            "quantity_before",
            "quantity_after",
        )
    ],
    *[
        (approved_values(**{field: value}), "ck_pr_workflow_fulfillment")
        for field, value in (
            ("fulfilled_by_id", 2),
            ("fulfilled_at", NOW),
            ("outbound_id", 1),
            ("outbound_transaction_id", 1),
            ("quantity_before", 10),
            ("quantity_after", 7),
        )
    ],
    (
        {**fulfilled_values(), "decision_kind": None, "decided_by_id": None, "decided_at": None},
        "ck_pr_workflow_fulfillment",
    ),
    (
        {**fulfilled_values(), "decision_kind": "rejected", "rejection_reason": "reason"},
        "ck_pr_workflow_fulfillment",
    ),
    *[
        (
            {**fulfilled_values(), "quantity_before": before, "quantity_after": after},
            "ck_pr_workflow_balances",
        )
        for before, after in (
            (10, -1),
            (10, 10),
            (10, 11),
            (0, 0),
            (2147483648, 7),
            (2147483648, 2147483647),
        )
    ],
]


@pytest.mark.parametrize("values,constraint", INVALID_WORKFLOWS)
def test_workflow_rejects_partial_groups_and_invalid_values(workflow_session, values, constraint):
    table = Base.metadata.tables["purchase_request_workflows"]
    with pytest.raises(IntegrityError):
        workflow_session.execute(insert(table), values)


@pytest.mark.parametrize(
    "values",
    [
        workflow_values(note="n" * 2000),
        approved_values(),
        {**approved_values(), "decision_kind": "rejected", "rejection_reason": "lý do"},
        {
            **approved_values(),
            "decision_kind": "rejected",
            "rejection_reason": "lý\t do\n thêm\u00a0nữa",
        },
        fulfilled_values(),
        {**fulfilled_values(), "quantity_before": 2147483647, "quantity_after": 0},
    ],
)
def test_valid_workflow_states_survive_roundtrip(workflow_session, values):
    table = Base.metadata.tables["purchase_request_workflows"]
    workflow_session.execute(insert(table), values)
    workflow_session.commit()
    row = workflow_session.execute(table.select()).mappings().one()
    assert row["request_fingerprint"] == "ab09" * 16
    assert row["idempotency_key"] == values["idempotency_key"]


@pytest.mark.parametrize("field", ["outbound_id", "outbound_transaction_id"])
def test_fulfillment_links_are_unique(workflow_session, field):
    table = Base.metadata.tables["purchase_request_workflows"]
    workflow_session.execute(insert(table), fulfilled_values())
    second = {
        **fulfilled_values(),
        "purchase_request_id": 2,
        "outbound_id": 2,
        "outbound_transaction_id": 2,
        field: 1,
    }
    with pytest.raises(IntegrityError):
        workflow_session.execute(insert(table), second)


def test_creation_key_is_actor_scoped_and_persisted(workflow_session):
    table = Base.metadata.tables["purchase_request_workflows"]
    key = uuid4()
    workflow_session.execute(insert(table), workflow_values(idempotency_key=key))
    workflow_session.commit()
    second = workflow_values(purchase_request_id=2, idempotency_key=key)
    with pytest.raises(IntegrityError):
        workflow_session.execute(insert(table), second)
    workflow_session.rollback()
    workflow_session.execute(insert(table), {**second, "created_by_id": 2})
    workflow_session.commit()
    assert len(workflow_session.execute(table.select()).all()) == 2


@pytest.mark.parametrize(
    "field,target",
    [
        ("purchase_request_id", PurchaseRequest),
        ("created_by_id", User),
        ("decided_by_id", User),
        ("fulfilled_by_id", User),
        ("outbound_id", Outbound),
        ("outbound_transaction_id", StockTransaction),
    ],
)
def test_foreign_keys_reject_missing_rows(workflow_session, field, target):
    table = Base.metadata.tables["purchase_request_workflows"]
    with pytest.raises(IntegrityError):
        workflow_session.execute(insert(table), {**fulfilled_values(), field: 999})


@pytest.mark.parametrize(
    "target,id", [(PurchaseRequest, 1), (User, 1), (User, 2), (Outbound, 1), (StockTransaction, 1)]
)
def test_workflow_references_restrict_delete(workflow_session, target, id):
    table = Base.metadata.tables["purchase_request_workflows"]
    workflow_session.execute(insert(table), fulfilled_values())
    workflow_session.commit()
    with pytest.raises(IntegrityError):
        workflow_session.execute(delete(target).where(target.id == id))
