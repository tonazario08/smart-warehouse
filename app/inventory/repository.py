"""Inventory read queries and persistence primitives."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.pagination import PageParams
from app.inventory.schemas import InventoryFilters, TransactionFilters
from app.models import Inbound, Outbound, Stock, StockTransaction


class InventoryRepository:
    """Encapsulate inventory queries without owning database transactions."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def _stock_statement(self, filters: InventoryFilters):
        statement = select(Stock)
        if filters.warehouse_id is not None:
            statement = statement.where(Stock.warehouse_id == filters.warehouse_id)
        if filters.product_id is not None:
            statement = statement.where(Stock.product_id == filters.product_id)
        if filters.created_from is not None:
            statement = statement.where(Stock.created_at >= filters.created_from)
        if filters.created_to is not None:
            statement = statement.where(Stock.created_at <= filters.created_to)
        return statement

    def _inbound_statement(self, filters: InventoryFilters):
        statement = select(Inbound)
        if filters.warehouse_id is not None:
            statement = statement.where(Inbound.warehouse_id == filters.warehouse_id)
        if filters.product_id is not None:
            statement = statement.where(Inbound.product_id == filters.product_id)
        if filters.created_from is not None:
            statement = statement.where(Inbound.created_at >= filters.created_from)
        if filters.created_to is not None:
            statement = statement.where(Inbound.created_at <= filters.created_to)
        return statement

    def _outbound_statement(self, filters: InventoryFilters):
        statement = select(Outbound)
        if filters.warehouse_id is not None:
            statement = statement.where(Outbound.warehouse_id == filters.warehouse_id)
        if filters.product_id is not None:
            statement = statement.where(Outbound.product_id == filters.product_id)
        if filters.created_from is not None:
            statement = statement.where(Outbound.created_at >= filters.created_from)
        if filters.created_to is not None:
            statement = statement.where(Outbound.created_at <= filters.created_to)
        return statement

    def _transaction_statement(self, filters: TransactionFilters):
        statement = select(StockTransaction)
        if filters.warehouse_id is not None:
            statement = statement.where(StockTransaction.warehouse_id == filters.warehouse_id)
        if filters.product_id is not None:
            statement = statement.where(StockTransaction.product_id == filters.product_id)
        if filters.transaction_type is not None:
            statement = statement.where(
                StockTransaction.transaction_type == filters.transaction_type
            )
        if filters.created_from is not None:
            statement = statement.where(StockTransaction.created_at >= filters.created_from)
        if filters.created_to is not None:
            statement = statement.where(StockTransaction.created_at <= filters.created_to)
        return statement

    def list_stock(
        self, filters: InventoryFilters, page: PageParams
    ) -> tuple[list[Stock], int]:
        statement = self._stock_statement(filters)
        items = list(
            self.session.scalars(
                statement.order_by(Stock.id).offset(page.offset).limit(page.page_size)
            )
        )
        total = self.session.scalar(
            select(func.count()).select_from(self._stock_statement(filters).subquery())
        ) or 0
        return items, total

    def get_stock(self, stock_id: int) -> Stock | None:
        return self.session.get(Stock, stock_id)

    def list_inbounds(
        self, filters: InventoryFilters, page: PageParams
    ) -> tuple[list[Inbound], int]:
        statement = self._inbound_statement(filters)
        items = list(
            self.session.scalars(
                statement.order_by(Inbound.created_at.desc(), Inbound.id.desc())
                .offset(page.offset)
                .limit(page.page_size)
            )
        )
        total = self.session.scalar(
            select(func.count()).select_from(self._inbound_statement(filters).subquery())
        ) or 0
        return items, total

    def get_inbound(self, inbound_id: int) -> Inbound | None:
        return self.session.get(Inbound, inbound_id)

    def list_outbounds(
        self, filters: InventoryFilters, page: PageParams
    ) -> tuple[list[Outbound], int]:
        statement = self._outbound_statement(filters)
        items = list(
            self.session.scalars(
                statement.order_by(Outbound.created_at.desc(), Outbound.id.desc())
                .offset(page.offset)
                .limit(page.page_size)
            )
        )
        total = self.session.scalar(
            select(func.count()).select_from(self._outbound_statement(filters).subquery())
        ) or 0
        return items, total

    def get_outbound(self, outbound_id: int) -> Outbound | None:
        return self.session.get(Outbound, outbound_id)

    def list_transactions(
        self, filters: TransactionFilters, page: PageParams
    ) -> tuple[list[StockTransaction], int]:
        statement = self._transaction_statement(filters)
        items = list(
            self.session.scalars(
                statement.order_by(StockTransaction.created_at.desc(), StockTransaction.id.desc())
                .offset(page.offset)
                .limit(page.page_size)
            )
        )
        total = self.session.scalar(
            select(func.count()).select_from(self._transaction_statement(filters).subquery())
        ) or 0
        return items, total

    def get_transaction(self, transaction_id: int) -> StockTransaction | None:
        return self.session.get(StockTransaction, transaction_id)
