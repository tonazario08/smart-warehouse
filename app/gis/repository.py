"""Read-only stock and movement views for GIS."""

from datetime import datetime

from sqlalchemy import DateTime, and_, case, func, or_, select, true
from sqlalchemy.orm import Session

from app.models import (
    MovementProvenance,
    Product,
    Stock,
    StockTransaction,
    TransactionType,
    Warehouse,
)

MAX_WAREHOUSES = 100


class GISRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def _statement_time(self):
        timestamp_type = DateTime(timezone=True)
        if self.session.get_bind().dialect.name == "postgresql":
            return func.statement_timestamp(type_=timestamp_type)
        return func.current_timestamp(type_=timestamp_type)

    def warehouse(self, warehouse_id: int) -> Warehouse | None:
        return self.session.get(Warehouse, warehouse_id)

    def product(self, product_id: int) -> Product | None:
        return self.session.get(Product, product_id)

    def warehouse_options(self, product_id: int):
        statement = (
            select(Product, Warehouse, Stock.quantity, self._statement_time())
            .select_from(Product)
            .outerjoin(Warehouse, true())
            .outerjoin(
                Stock, and_(Stock.product_id == Product.id, Stock.warehouse_id == Warehouse.id)
            )
            .where(Product.id == product_id, Product.is_active.is_(True))
            .order_by(Warehouse.id)
            .limit(MAX_WAREHOUSES + 1)
        )
        return self.session.execute(statement).all()

    def heatmap(self, product_id: int, start: datetime, end: datetime):
        purpose = MovementProvenance.purpose
        movement_type = StockTransaction.transaction_type
        outbound = movement_type == TransactionType.OUTBOUND
        inbound = movement_type == TransactionType.INBOUND
        bucket = case(
            (and_(outbound, purpose == "purchase_request_fulfillment"), "fulfillment"),
            (and_(inbound, purpose == "transfer_in"), "transfer_in"),
            (and_(outbound, purpose == "transfer_out"), "transfer_out"),
            (and_(outbound, purpose == "standard_outbound"), "standard_outbound"),
            (outbound, "unclassified_outbound"),
        )
        totals = (
            select(
                StockTransaction.warehouse_id,
                bucket.label("bucket"),
                func.sum(StockTransaction.quantity).label("quantity"),
                func.count(StockTransaction.id).label("transaction_count"),
            )
            .select_from(StockTransaction)
            .outerjoin(
                MovementProvenance, MovementProvenance.transaction_id == StockTransaction.id
            )
            .where(
                StockTransaction.product_id == product_id,
                StockTransaction.created_at >= start,
                StockTransaction.created_at < end,
                or_(outbound, and_(inbound, purpose == "transfer_in")),
            )
            .group_by(StockTransaction.warehouse_id, bucket)
            .subquery()
        )
        statement = (
            select(
                Product,
                Warehouse,
                self._statement_time(),
                totals.c.bucket,
                totals.c.quantity,
                totals.c.transaction_count,
            )
            .select_from(Product)
            .outerjoin(Warehouse, true())
            .outerjoin(totals, totals.c.warehouse_id == Warehouse.id)
            .where(Product.id == product_id, Product.is_active.is_(True))
            .order_by(Warehouse.id, totals.c.bucket)
        )
        return self.session.execute(statement).all()
