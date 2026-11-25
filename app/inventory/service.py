"""Inventory read use cases and stable resource errors."""

import json
from hashlib import sha256
from uuid import UUID, uuid4

from sqlalchemy.exc import DBAPIError

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

    @staticmethod
    def _fingerprint(request: InventoryMovementCreate) -> str:
        return sha256(
            json.dumps(
                request.model_dump(), sort_keys=True, separators=(",", ":"), ensure_ascii=False
            ).encode()
        ).hexdigest()

    def get_inbound_by_key(self, actor_id: int, key: UUID) -> Inbound:
        inbound = self.repository.find_inbound_by_key(actor_id, key)
        if inbound is None:
            raise DomainError(404, "INBOUND_NOT_FOUND", "Inbound record not found.")
        return inbound

    def get_outbound_by_key(self, actor_id: int, key: UUID) -> Outbound:
        outbound = self.repository.find_outbound_by_key(actor_id, key)
        if outbound is None:
            raise DomainError(404, "OUTBOUND_NOT_FOUND", "Outbound record not found.")
        return outbound

    def create_inbound(
        self, actor_id: int, request: InventoryMovementCreate, key: UUID | None = None
    ) -> tuple[Inbound, bool]:
        """Create one inbound, replaying the original on an exact retry.

        ``key`` is required at the API boundary and validated by the router.
        Internal callers that omit it get a server-generated UUID, so one
        service call can never be replayed by accident. The retry loop mirrors
        ``TransferService.create``: an actor-scoped advisory lock serializes
        concurrent attempts for the same key, a SHA256 fingerprint of the
        normalized body distinguishes an exact replay (200) from a conflicting
        reuse (409), and an ambiguous commit surfaces as 503 so the caller
        retries the exact same body and key.
        """
        key = key or uuid4()
        fingerprint = self._fingerprint(request)
        for attempt in range(3):
            try:
                self.repository.lock_movement_key(actor_id, key, "inbound")
                existing = self.repository.find_inbound_by_key(actor_id, key)
                if existing is not None:
                    if existing.request_fingerprint != fingerprint:
                        raise DomainError(
                            409,
                            "IDEMPOTENCY_KEY_CONFLICT",
                            "Key is already used for a different request.",
                        )
                    self.repository.session.commit()
                    self.repository.refresh(existing)
                    return existing, True
                return self._create_inbound_attempt(actor_id, key, request, fingerprint)
            except Exception as error:
                try:
                    self.repository.session.rollback()
                except DBAPIError:
                    self.repository.session.invalidate()
                if isinstance(error, DomainError):
                    raise
                if isinstance(error, DBAPIError):
                    sqlstate = getattr(error.orig, "sqlstate", None)
                    if sqlstate in {"40P01", "40001"} and attempt < 2:
                        self.repository.session.expire_all()
                        continue
                    if (
                        sqlstate in {"40P01", "40001", "55P03"}
                        or error.connection_invalidated
                        or (sqlstate and sqlstate.startswith("08"))
                    ):
                        raise DomainError(
                            503,
                            "INBOUND_RETRY_REQUIRED",
                            "Retry the same inbound request.",
                        ) from None
                raise
        raise AssertionError("Inbound retry boundary was exceeded.")

    def _create_inbound_attempt(
        self, actor_id: int, key: UUID, request: InventoryMovementCreate, fingerprint: str
    ) -> tuple[Inbound, bool]:
        session = self.repository.session
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

        inbound = self.repository.add_inbound(request, actor_id, key=key, fingerprint=fingerprint)
        self.repository.flush()
        self.repository.add_stock_transaction_for_inbound(inbound, actor_id)
        session.commit()
        self.repository.refresh(inbound)
        return inbound, False

    def create_outbound(
        self, actor_id: int, request: InventoryMovementCreate, key: UUID | None = None
    ) -> tuple[Outbound, bool]:
        """Create one outbound with the same idempotency contract as inbound."""
        key = key or uuid4()
        fingerprint = self._fingerprint(request)
        for attempt in range(3):
            try:
                self.repository.lock_movement_key(actor_id, key, "outbound")
                existing = self.repository.find_outbound_by_key(actor_id, key)
                if existing is not None:
                    if existing.request_fingerprint != fingerprint:
                        raise DomainError(
                            409,
                            "IDEMPOTENCY_KEY_CONFLICT",
                            "Key is already used for a different request.",
                        )
                    self.repository.session.commit()
                    self.repository.refresh(existing)
                    return existing, True
                return self._create_outbound_attempt(actor_id, key, request, fingerprint)
            except Exception as error:
                try:
                    self.repository.session.rollback()
                except DBAPIError:
                    self.repository.session.invalidate()
                if isinstance(error, DomainError):
                    raise
                if isinstance(error, DBAPIError):
                    sqlstate = getattr(error.orig, "sqlstate", None)
                    if sqlstate in {"40P01", "40001"} and attempt < 2:
                        self.repository.session.expire_all()
                        continue
                    if (
                        sqlstate in {"40P01", "40001", "55P03"}
                        or error.connection_invalidated
                        or (sqlstate and sqlstate.startswith("08"))
                    ):
                        raise DomainError(
                            503,
                            "OUTBOUND_RETRY_REQUIRED",
                            "Retry the same outbound request.",
                        ) from None
                raise
        raise AssertionError("Outbound retry boundary was exceeded.")

    def _create_outbound_attempt(
        self, actor_id: int, key: UUID, request: InventoryMovementCreate, fingerprint: str
    ) -> tuple[Outbound, bool]:
        session = self.repository.session
        self._require_movement_references(request)
        stock = self.repository.get_stock_for_update(
            request.warehouse_id, request.product_id
        )
        if stock is None or stock.quantity < request.quantity:
            raise DomainError(409, "INSUFFICIENT_STOCK", "Insufficient stock.")

        stock.quantity -= request.quantity
        outbound = self.repository.add_outbound(
            request, actor_id, key=key, fingerprint=fingerprint
        )
        self.repository.flush()
        self.repository.add_stock_transaction_for_outbound(outbound, actor_id)
        session.commit()
        self.repository.refresh(outbound)
        return outbound, False

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
