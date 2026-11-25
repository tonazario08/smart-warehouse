"""Order analytics sources and PostgreSQL writes; callers own transactions."""

from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from sqlalchemy import func, select, true, tuple_, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, aliased

from app.models.domain import Product, PurchaseRequest, PurchaseRequestWorkflow, Stock, Warehouse
from app.order_analytics.models import (
    OrderAnalyticsJob,
    OrderAnalyticsKeyState,
    OrderAnalyticsOrderCheck,
)
from app.order_analytics.rules import HISTORY_DAYS


@dataclass(frozen=True)
class Position:
    warehouse_id: int
    product_id: int
    sku: str
    unit: str
    on_hand: int | None
    pending_quantity: int
    approved_quantity: int
    total_quantity: int
    order_count: int

    @property
    def projected_quantity(self) -> int | None:
        return None if self.on_hand is None else self.on_hand - self.total_quantity


@dataclass(frozen=True)
class OrderSample:
    quantity: int
    history: tuple[int, ...]


def read_position(session: Session, warehouse_id: int, product_id: int) -> Position | None:
    """Stock and all open quantities come from the same database statement/snapshot."""
    on_hand = (
        select(Stock.quantity)
        .where(Stock.warehouse_id == warehouse_id, Stock.product_id == product_id)
        .scalar_subquery()
    )
    pending = PurchaseRequest.status == "pending"
    approved = PurchaseRequest.status == "approved"
    open_orders = (
        select(
            func.coalesce(func.sum(PurchaseRequest.quantity).filter(pending), 0).label(
                "pending_quantity"
            ),
            func.coalesce(func.sum(PurchaseRequest.quantity).filter(approved), 0).label(
                "approved_quantity"
            ),
            func.coalesce(func.sum(PurchaseRequest.quantity), 0).label("total_quantity"),
            func.count().label("order_count"),
        )
        .select_from(PurchaseRequest)
        .join(
            PurchaseRequestWorkflow,
            PurchaseRequestWorkflow.purchase_request_id == PurchaseRequest.id,
        )
        .where(
            PurchaseRequest.warehouse_id == warehouse_id,
            PurchaseRequest.product_id == product_id,
            pending | approved,
        )
        .subquery()
    )
    stmt = (
        select(
            Warehouse.id.label("warehouse_id"),
            Product.id.label("product_id"),
            Product.sku,
            Product.unit,
            on_hand.label("on_hand"),
            open_orders.c.pending_quantity,
            open_orders.c.approved_quantity,
            open_orders.c.total_quantity,
            open_orders.c.order_count,
        )
        .select_from(Warehouse)
        .join(Product, Product.id == product_id)
        .join(open_orders, true())
        .where(Warehouse.id == warehouse_id)
    )
    row = session.execute(stmt).mappings().one_or_none()
    return Position(**row) if row is not None else None


def get_order_sample(session: Session, purchase_request_id: int) -> OrderSample | None:
    target = aliased(PurchaseRequest)
    current = session.execute(
        select(target.quantity, target.created_at)
        .join(PurchaseRequestWorkflow, PurchaseRequestWorkflow.purchase_request_id == target.id)
        .where(target.id == purchase_request_id)
    ).one_or_none()
    if current is None:
        return None
    stmt = (
        select(PurchaseRequest.quantity)
        .join(target, target.id == purchase_request_id)
        .join(
            PurchaseRequestWorkflow,
            PurchaseRequestWorkflow.purchase_request_id == PurchaseRequest.id,
        )
        .where(
            PurchaseRequest.warehouse_id == target.warehouse_id,
            PurchaseRequest.product_id == target.product_id,
            PurchaseRequest.status.in_(("approved", "fulfilled")),
            PurchaseRequestWorkflow.decision_kind == "approved",
            PurchaseRequestWorkflow.decided_at < target.created_at,
            PurchaseRequest.created_at >= current.created_at - timedelta(days=HISTORY_DAYS),
            tuple_(PurchaseRequest.created_at, PurchaseRequest.id)
            < tuple_(target.created_at, target.id),
        )
        .order_by(PurchaseRequest.created_at, PurchaseRequest.id)
    )
    return OrderSample(current.quantity, tuple(session.scalars(stmt)))


def get_key_state(
    session: Session, warehouse_id: int, product_id: int
) -> OrderAnalyticsKeyState | None:
    return session.get(OrderAnalyticsKeyState, (warehouse_id, product_id))


def get_latest_job(
    session: Session, warehouse_id: int, product_id: int
) -> OrderAnalyticsJob | None:
    return session.scalar(
        select(OrderAnalyticsJob)
        .where(
            OrderAnalyticsJob.warehouse_id == warehouse_id,
            OrderAnalyticsJob.product_id == product_id,
        )
        .order_by(OrderAnalyticsJob.id.desc())
        .limit(1)
    )


def has_pending_job(session: Session, warehouse_id: int, product_id: int) -> bool:
    stmt = select(
        select(OrderAnalyticsJob.id)
        .where(
            OrderAnalyticsJob.warehouse_id == warehouse_id,
            OrderAnalyticsJob.product_id == product_id,
            OrderAnalyticsJob.status.in_(("queued", "running")),
        )
        .exists()
    )
    return bool(session.scalar(stmt))


def query_order_checks(
    session: Session,
    *,
    purchase_request_id: int | None = None,
    warehouse_id: int | None = None,
    product_id: int | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[Any], int]:
    where = []
    for field, value in (
        (OrderAnalyticsJob.purchase_request_id, purchase_request_id),
        (OrderAnalyticsJob.warehouse_id, warehouse_id),
        (OrderAnalyticsJob.product_id, product_id),
    ):
        if value is not None:
            where.append(field == value)
    base = (
        select(PurchaseRequest, OrderAnalyticsJob, OrderAnalyticsOrderCheck)
        .select_from(OrderAnalyticsJob)
        .join(PurchaseRequest, PurchaseRequest.id == OrderAnalyticsJob.purchase_request_id)
        .outerjoin(
            OrderAnalyticsOrderCheck,
            OrderAnalyticsOrderCheck.purchase_request_id == PurchaseRequest.id,
        )
        .where(*where)
    )
    total = session.scalar(select(func.count()).select_from(OrderAnalyticsJob).where(*where)) or 0
    stmt = (
        base.order_by(PurchaseRequest.created_at.desc(), PurchaseRequest.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return list(session.execute(stmt)), total


def write_order_check(session: Session, purchase_request_id: int, **attrs: Any) -> None:
    """Call only inside a live claim-guard transaction."""
    attrs["computed_at"] = func.clock_timestamp()
    stmt = insert(OrderAnalyticsOrderCheck).values(purchase_request_id=purchase_request_id, **attrs)
    session.execute(
        stmt.on_conflict_do_update(
            index_elements=[OrderAnalyticsOrderCheck.purchase_request_id], set_=attrs
        )
    )


def write_key_state(
    session: Session,
    warehouse_id: int,
    product_id: int,
    seen_version: int | None,
    **attrs: Any,
) -> bool:
    """Compare and swap a key row after a matching live claim guard."""
    attrs.update(computed_at=func.clock_timestamp(), updated_at=func.clock_timestamp())
    if seen_version is None:
        stmt = (
            insert(OrderAnalyticsKeyState)
            .values(warehouse_id=warehouse_id, product_id=product_id, row_version=1, **attrs)
            .on_conflict_do_nothing(
                index_elements=[
                    OrderAnalyticsKeyState.warehouse_id,
                    OrderAnalyticsKeyState.product_id,
                ]
            )
        )
    else:
        stmt = (
            update(OrderAnalyticsKeyState)
            .where(
                OrderAnalyticsKeyState.warehouse_id == warehouse_id,
                OrderAnalyticsKeyState.product_id == product_id,
                OrderAnalyticsKeyState.row_version == seen_version,
            )
            .values(row_version=seen_version + 1, **attrs)
        )
    return (
        session.execute(stmt.returning(OrderAnalyticsKeyState.row_version)).scalar_one_or_none()
        is not None
    )
