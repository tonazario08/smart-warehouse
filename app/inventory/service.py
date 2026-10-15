"""Inventory read use cases and stable resource errors."""

from app.core.errors import DomainError
from app.core.pagination import PageParams
from app.inventory.repository import InventoryRepository
from app.inventory.schemas import (
    MAX_STOCK_QUANTITY,
    InventoryFilters,
    InventoryMovementCreate,
    TransactionFilters,
)
from app.models import Inbound, Outbound, Stock, StockTransaction


class InventoryService:
    """Coordinate inventory reads and atomic movement transactions."""

    def __init__(self, repository: InventoryRepository) -> None:
        self.repository = repository

    def _increment_stock(self, stock: Stock, quantity: int) -> None:
        if stock.quantity > MAX_STOCK_QUANTITY - quantity:
            raise DomainError(
                409,
                "STOCK_QUANTITY_LIMIT_EXCEEDED",
                "Stock quantity would exceed the supported limit.",
            )
        stock.quantity += quantity

    def _require_movement_references(self, request: InventoryMovementCreate) -> None:
        if self.repository.get_warehouse(request.warehouse_id) is None:
            raise DomainError(404, "WAREHOUSE_NOT_FOUND", "Warehouse was not found.")
        if self.repository.get_product(request.product_id) is None:
            raise DomainError(404, "PRODUCT_NOT_FOUND", "Product was not found.")

    def create_inbound(self, actor_id: int, request: InventoryMovementCreate) -> Inbound:
        try:
            self._require_movement_references(request)
            stock = self.repository.get_stock_for_update(
                request.warehouse_id, request.product_id
            )
            if stock is None:
                stock = self.repository.insert_stock_if_absent(
                    request.warehouse_id, request.product_id, request.quantity
                )
                if stock is None:
                    stock = self.repository.get_stock_for_update(
                        request.warehouse_id, request.product_id
                    )
                    if stock is None:
                        raise DomainError(409, "STOCK_CONFLICT", "Stock could not be created.")
                    self._increment_stock(stock, request.quantity)
            else:
                self._increment_stock(stock, request.quantity)

            inbound = self.repository.add_inbound(request, actor_id)
            self.repository.flush()
            self.repository.add_stock_transaction_for_inbound(inbound, actor_id)
            self.repository.session.commit()
            self.repository.refresh(inbound)
            return inbound
        except Exception:
            self.repository.session.rollback()
            raise

    def create_outbound(self, actor_id: int, request: InventoryMovementCreate) -> Outbound:
        try:
            self._require_movement_references(request)
            stock = self.repository.get_stock_for_update(
                request.warehouse_id, request.product_id
            )
            if stock is None or stock.quantity < request.quantity:
                raise DomainError(409, "INSUFFICIENT_STOCK", "Insufficient stock.")

            stock.quantity -= request.quantity
            outbound = self.repository.add_outbound(request, actor_id)
            self.repository.flush()
            self.repository.add_stock_transaction_for_outbound(outbound, actor_id)
            self.repository.session.commit()
            self.repository.refresh(outbound)
            return outbound
        except Exception:
            self.repository.session.rollback()
            raise

    def list_stock(
        self, filters: InventoryFilters, page: PageParams
    ) -> tuple[list[Stock], int]:
        return self.repository.list_stock(filters, page)

    def get_stock(self, stock_id: int) -> Stock:
        stock = self.repository.get_stock(stock_id)
        if stock is None:
            raise DomainError(404, "STOCK_NOT_FOUND", "Stock record not found.")
        return stock

    def list_inbounds(
        self, filters: InventoryFilters, page: PageParams
    ) -> tuple[list[Inbound], int]:
        return self.repository.list_inbounds(filters, page)

    def get_inbound(self, inbound_id: int) -> Inbound:
        inbound = self.repository.get_inbound(inbound_id)
        if inbound is None:
            raise DomainError(404, "INBOUND_NOT_FOUND", "Inbound record not found.")
        return inbound

    def list_outbounds(
        self, filters: InventoryFilters, page: PageParams
    ) -> tuple[list[Outbound], int]:
        return self.repository.list_outbounds(filters, page)

    def get_outbound(self, outbound_id: int) -> Outbound:
        outbound = self.repository.get_outbound(outbound_id)
        if outbound is None:
            raise DomainError(404, "OUTBOUND_NOT_FOUND", "Outbound record not found.")
        return outbound

    def list_transactions(
        self, filters: TransactionFilters, page: PageParams
    ) -> tuple[list[StockTransaction], int]:
        return self.repository.list_transactions(filters, page)

    def get_transaction(self, transaction_id: int) -> StockTransaction:
        transaction = self.repository.get_transaction(transaction_id)
        if transaction is None:
            raise DomainError(404, "TRANSACTION_NOT_FOUND", "Stock transaction not found.")
        return transaction
