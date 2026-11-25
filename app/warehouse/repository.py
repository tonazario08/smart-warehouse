"""Persistence operations for warehouses without transaction ownership."""

from sqlalchemy import exists, func, or_, select
from sqlalchemy.orm import Session

from app.core.pagination import PageParams
from app.models import (
    Inbound,
    Outbound,
    PurchaseRequest,
    RouteLog,
    Stock,
    StockTransaction,
    Warehouse,
)


class WarehouseRepository:
    """Query, stage, and delete warehouse records."""

    def __init__(self, session: Session) -> None:
        self.session = session

    @staticmethod
    def _search_filter(search: str | None):
        if not search or not search.strip():
            return ()
        pattern = f"%{search.strip()}%"
        return (
            or_(
                Warehouse.code.ilike(pattern),
                Warehouse.name.ilike(pattern),
                Warehouse.address.ilike(pattern),
            ),
        )

    def list(self, params: PageParams, search: str | None = None) -> list[Warehouse]:
        statement = (
            select(Warehouse)
            .where(*self._search_filter(search))
            .order_by(Warehouse.id)
            .offset(params.offset)
            .limit(params.page_size)
        )
        return list(self.session.scalars(statement).all())

    def count(self, search: str | None = None) -> int:
        statement = select(func.count()).select_from(Warehouse).where(*self._search_filter(search))
        return self.session.scalar(statement) or 0

    def get(self, warehouse_id: int) -> Warehouse | None:
        return self.session.get(Warehouse, warehouse_id)

    def add(self, warehouse: Warehouse) -> None:
        self.session.add(warehouse)

    @staticmethod
    def update(warehouse: Warehouse, values: dict[str, object]) -> None:
        for field, value in values.items():
            setattr(warehouse, field, value)

    def delete(self, warehouse: Warehouse) -> None:
        self.session.delete(warehouse)

    def has_references(self, warehouse_id: int) -> bool:
        references = (
            exists(select(Stock.id).where(Stock.warehouse_id == warehouse_id)),
            exists(select(Inbound.id).where(Inbound.warehouse_id == warehouse_id)),
            exists(select(Outbound.id).where(Outbound.warehouse_id == warehouse_id)),
            exists(
                select(StockTransaction.id).where(StockTransaction.warehouse_id == warehouse_id)
            ),
            exists(
                select(PurchaseRequest.id).where(PurchaseRequest.warehouse_id == warehouse_id)
            ),
            exists(select(RouteLog.id).where(RouteLog.warehouse_id == warehouse_id)),
        )
        return bool(self.session.scalar(select(or_(*references))))
