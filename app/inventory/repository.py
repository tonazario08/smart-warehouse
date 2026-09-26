"""Inventory read queries and persistence primitives."""

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.pagination import PageParams
from app.inventory.schemas import InventoryFilters, InventoryMovementCreate, TransactionFilters
from app.models import (
    Inbound,
    Outbound,
    Product,
    Stock,
    StockTransaction,
    TransactionType,
    Warehouse,
)


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

    def get_warehouse(self, warehouse_id: int) -> Warehouse | None:
        return self.session.get(Warehouse, warehouse_id)

    def get_product(self, product_id: int) -> Product | None:
        return self.session.get(Product, product_id)

    def get_stock_for_update(self, warehouse_id: int, product_id: int) -> Stock | None:
        return self.session.scalar(
            select(Stock)
            .where(Stock.warehouse_id == warehouse_id, Stock.product_id == product_id)
            .with_for_update()
        )

    def insert_stock_if_absent(
        self, warehouse_id: int, product_id: int, quantity: int
    ) -> Stock | None:
        statement = (
            insert(Stock)
            .values(warehouse_id=warehouse_id, product_id=product_id, quantity=quantity)
            .on_conflict_do_nothing(index_elements=[Stock.warehouse_id, Stock.product_id])
            .returning(Stock.id)
        )
        stock_id = self.session.scalar(statement)
        return self.session.get(Stock, stock_id) if stock_id is not None else None

    def add_inbound(self, movement: InventoryMovementCreate, actor_id: int) -> Inbound:
        inbound = Inbound(**movement.model_dump(), created_by_id=actor_id)
        self.session.add(inbound)
        return inbound

    def add_outbound(self, movement: InventoryMovementCreate, actor_id: int) -> Outbound:
        outbound = Outbound(**movement.model_dump(), created_by_id=actor_id)
        self.session.add(outbound)
        return outbound

    def add_stock_transaction_for_inbound(
        self, inbound: Inbound, actor_id: int
    ) -> StockTransaction:
        transaction = StockTransaction(
            transaction_type=TransactionType.INBOUND,
            warehouse_id=inbound.warehouse_id,
            product_id=inbound.product_id,
            quantity=inbound.quantity,
            inbound_id=inbound.id,
            created_by_id=actor_id,
        )
        self.session.add(transaction)
        return transaction

    def add_stock_transaction_for_outbound(
        self, outbound: Outbound, actor_id: int
    ) -> StockTransaction:
        transaction = StockTransaction(
            transaction_type=TransactionType.OUTBOUND,
            warehouse_id=outbound.warehouse_id,
            product_id=outbound.product_id,
            quantity=outbound.quantity,
            outbound_id=outbound.id,
            created_by_id=actor_id,
        )
        self.session.add(transaction)
        return transaction

    def flush(self) -> None:
        self.session.flush()

    def refresh(self, instance: Inbound | Outbound) -> None:
        self.session.refresh(instance)
