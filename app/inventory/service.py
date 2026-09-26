"""Inventory read use cases and stable resource errors."""

from app.core.errors import DomainError
from app.core.pagination import PageParams
from app.inventory.repository import InventoryRepository
from app.inventory.schemas import InventoryFilters, TransactionFilters
from app.models import Inbound, Outbound, Stock, StockTransaction


class InventoryService:
    """Coordinate inventory read queries without committing or rolling back."""

    def __init__(self, repository: InventoryRepository) -> None:
        self.repository = repository

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
