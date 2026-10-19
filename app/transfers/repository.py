"""Flush-only transfer persistence and queries."""

from hashlib import sha256
from uuid import UUID

from sqlalchemy import func, select, text

from app.core.pagination import PageParams
from app.inventory.repository import InventoryRepository
from app.models import (
    Inbound,
    MovementProvenance,
    Outbound,
    Stock,
    StockTransaction,
    StockTransfer,
    TransactionType,
)
from app.transfers.schemas import MovementProvenanceResponse, ProvenanceFilters, TransferFilters


class TransferRepository(InventoryRepository):
    """Share the caller's Session without owning its commit."""

    def lock_key(self, actor_id: int, key: UUID) -> None:
        domain_key = f"smart-warehouse:transfer:v1\0{actor_id}\0{key}".encode()
        lock_id = int.from_bytes(sha256(domain_key).digest()[:8], "big", signed=True)
        self.session.execute(text("SET LOCAL lock_timeout = '3s'"))
        self.session.execute(text("SELECT pg_advisory_xact_lock(:lock_id)"), {"lock_id": lock_id})

    def find_by_key(self, actor_id: int, key: UUID) -> StockTransfer | None:
        return self.session.scalar(
            select(StockTransfer)
            .where(StockTransfer.created_by_id == actor_id, StockTransfer.idempotency_key == key)
            .execution_options(populate_existing=True)
        )

    def get(self, transfer_id: int) -> StockTransfer | None:
        return self.session.get(StockTransfer, transfer_id)

    def list(self, filters: TransferFilters, page: PageParams) -> tuple[list[StockTransfer], int]:
        statement = select(StockTransfer)
        for field in ["source_warehouse_id", "destination_warehouse_id", "product_id"]:
            if (value := getattr(filters, field)) is not None:
                statement = statement.where(getattr(StockTransfer, field) == value)
        if filters.created_from is not None:
            statement = statement.where(StockTransfer.created_at >= filters.created_from)
        if filters.created_to is not None:
            statement = statement.where(StockTransfer.created_at <= filters.created_to)
        total = self.session.scalar(select(func.count()).select_from(statement.subquery())) or 0
        items = list(
            self.session.scalars(
                statement.order_by(StockTransfer.created_at.desc(), StockTransfer.id.desc())
                .offset(page.offset)
                .limit(page.page_size)
            )
        )
        return items, total

    def list_provenance(self, filters: ProvenanceFilters, page: PageParams):
        purpose = func.coalesce(MovementProvenance.purpose, "legacy_unknown")
        statement = select(
            StockTransaction.id.label("transaction_id"),
            purpose.label("purpose"),
            MovementProvenance.transfer_id,
        ).outerjoin(MovementProvenance, MovementProvenance.transaction_id == StockTransaction.id)
        if filters.transaction_id is not None:
            statement = statement.where(StockTransaction.id == filters.transaction_id)
        if filters.transfer_id is not None:
            statement = statement.where(MovementProvenance.transfer_id == filters.transfer_id)
        if filters.purpose is not None:
            statement = statement.where(purpose == filters.purpose)
        total = self.session.scalar(select(func.count()).select_from(statement.subquery())) or 0
        rows = self.session.execute(
            statement.order_by(StockTransaction.id).offset(page.offset).limit(page.page_size)
        ).mappings()
        return [MovementProvenanceResponse.model_validate(dict(row)) for row in rows], total

    def lock_stock(self, warehouse_id: int, product_id: int) -> Stock:
        self.insert_stock_if_absent(warehouse_id, product_id, 0)
        return self.session.scalars(
            select(Stock)
            .where(Stock.warehouse_id == warehouse_id, Stock.product_id == product_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        ).one()

    def add_leg(
        self,
        *,
        direction: TransactionType,
        warehouse_id: int,
        product_id: int,
        quantity: int,
        actor_id: int,
        reference: str | None,
        note: str | None,
    ):
        model = Outbound if direction == TransactionType.OUTBOUND else Inbound
        movement = model(
            warehouse_id=warehouse_id,
            product_id=product_id,
            quantity=quantity,
            created_by_id=actor_id,
            reference=reference,
            note=note,
        )
        self.session.add(movement)
        self.flush()
        transaction = StockTransaction(
            transaction_type=direction,
            warehouse_id=warehouse_id,
            product_id=product_id,
            quantity=quantity,
            created_by_id=actor_id,
            **{direction.value + "_id": movement.id},
        )
        self.session.add(transaction)
        self.flush()
        return movement, transaction
