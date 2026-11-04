"""Owner-scoped coherent reads and flush-only, fresh-lock persistence."""

from hashlib import sha256
from uuid import UUID

from sqlalchemy import func, select, text

from app.core.pagination import PageParams
from app.inventory.repository import InventoryRepository
from app.models import Product, PurchaseRequest, PurchaseRequestWorkflow, Stock
from app.purchase_requests.schemas import PurchaseRequestFilters

PurchaseRequestRecord = tuple[PurchaseRequest, PurchaseRequestWorkflow | None]


class PurchaseRequestRepository(InventoryRepository):
    def _read(self, owner_id: int | None):
        statement = (
            select(PurchaseRequest, PurchaseRequestWorkflow)
            .outerjoin(
                PurchaseRequestWorkflow,
                PurchaseRequestWorkflow.purchase_request_id == PurchaseRequest.id,
            )
            .execution_options(populate_existing=True)
        )
        if owner_id is not None:
            statement = statement.where(PurchaseRequest.requested_by_id == owner_id)
        return statement

    def get_owned(self, request_id: int, *, owner_id: int | None) -> PurchaseRequestRecord | None:
        row = self.session.execute(
            self._read(owner_id).where(PurchaseRequest.id == request_id)
        ).one_or_none()
        return tuple(row) if row is not None else None

    def list_owned(
        self, filters: PurchaseRequestFilters, page: PageParams, *, owner_id: int | None
    ) -> tuple[list[PurchaseRequestRecord], int]:
        statement = self._read(owner_id)
        for field in ("status", "warehouse_id", "product_id", "requested_by_id"):
            if (value := getattr(filters, field)) is not None:
                statement = statement.where(getattr(PurchaseRequest, field) == value)
        if filters.created_from is not None:
            statement = statement.where(PurchaseRequest.created_at >= filters.created_from)
        if filters.created_to is not None:
            statement = statement.where(PurchaseRequest.created_at <= filters.created_to)
        total = self.session.scalar(select(func.count()).select_from(statement.subquery())) or 0
        rows = self.session.execute(
            statement.order_by(PurchaseRequest.created_at.desc(), PurchaseRequest.id.desc())
            .offset(page.offset)
            .limit(page.page_size)
        )
        return [tuple(row) for row in rows], total

    def find_by_key(self, actor_id: int, key: UUID) -> PurchaseRequestRecord | None:
        row = self.session.execute(
            self._read(None).where(
                PurchaseRequestWorkflow.created_by_id == actor_id,
                PurchaseRequestWorkflow.idempotency_key == key,
            )
        ).one_or_none()
        return tuple(row) if row is not None else None

    def _timeout(self):
        self.session.execute(text("SET LOCAL lock_timeout = '3s'"))

    def lock_key(self, actor_id: int, key: UUID) -> None:
        domain = f"smart-warehouse:purchase-request:create:v1\0{actor_id}\0{key}".encode()
        lock_id = int.from_bytes(sha256(domain).digest()[:8], "big", signed=True)
        self._timeout()
        self.session.execute(text("SELECT pg_advisory_xact_lock(:lock_id)"), {"lock_id": lock_id})

    def lock_request(self, request_id: int) -> PurchaseRequest | None:
        self._timeout()
        return self.session.scalar(
            select(PurchaseRequest)
            .where(PurchaseRequest.id == request_id)
            .with_for_update(of=PurchaseRequest)
            .execution_options(populate_existing=True)
        )

    def get_workflow(self, request_id: int) -> PurchaseRequestWorkflow | None:
        return self.session.scalar(
            select(PurchaseRequestWorkflow)
            .where(PurchaseRequestWorkflow.purchase_request_id == request_id)
            .execution_options(populate_existing=True)
        )

    def get_requestable_product(self, product_id: int) -> Product | None:
        return self.session.scalar(
            select(Product)
            .where(Product.id == product_id)
            .with_for_update(read=True)
            .execution_options(populate_existing=True)
        )

    def lock_existing_stock(self, warehouse_id: int, product_id: int) -> Stock | None:
        return self.session.scalar(
            select(Stock)
            .where(Stock.warehouse_id == warehouse_id, Stock.product_id == product_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
