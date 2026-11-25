"""Atomic immediate stock transfer use case."""

import json
from hashlib import sha256
from uuid import UUID

from sqlalchemy.exc import DBAPIError

from app.core.errors import DomainError
from app.core.pagination import PageParams
from app.inventory.schemas import MAX_STOCK_QUANTITY
from app.models import MovementProvenance, StockTransfer, TransactionType
from app.transfers.repository import TransferRepository
from app.transfers.schemas import ProvenanceFilters, TransferCreate, TransferFilters


class TransferService:
    def __init__(self, repository: TransferRepository):
        self.repository = repository

    def get(self, transfer_id: int) -> StockTransfer:
        result = self.repository.get(transfer_id)
        if result is None:
            raise DomainError(404, "TRANSFER_NOT_FOUND", "Transfer was not found.")
        return result

    def get_by_key(self, actor_id: int, key: UUID) -> StockTransfer:
        result = self.repository.find_by_key(actor_id, key)
        if result is None:
            raise DomainError(404, "TRANSFER_NOT_FOUND", "Transfer was not found.")
        return result

    def list(self, filters: TransferFilters, page: PageParams):
        return self.repository.list(filters, page)

    def list_provenance(self, filters: ProvenanceFilters, page: PageParams):
        return self.repository.list_provenance(filters, page)

    def create(
        self, actor_id: int, key: UUID, request: TransferCreate
    ) -> tuple[StockTransfer, bool]:
        session = self.repository.session
        fingerprint = sha256(
            json.dumps(
                request.model_dump(), sort_keys=True, separators=(",", ":"), ensure_ascii=False
            ).encode()
        ).hexdigest()
        for attempt in range(3):
            try:
                self.repository.lock_key(actor_id, key)
                existing = self.repository.find_by_key(actor_id, key)
                if existing is not None:
                    if existing.request_fingerprint != fingerprint:
                        raise DomainError(
                            409,
                            "IDEMPOTENCY_KEY_CONFLICT",
                            "Key is already used for a different request.",
                        )
                    session.commit()
                    session.refresh(existing)
                    return existing, True
                return self._create_attempt(actor_id, key, request, fingerprint)
            except DBAPIError as error:
                sqlstate = getattr(error.orig, "sqlstate", None)
                try:
                    session.rollback()
                except DBAPIError:
                    session.invalidate()
                if sqlstate in {"40P01", "40001"} and attempt < 2:
                    session.expire_all()
                    continue
                if (
                    sqlstate in {"40P01", "40001", "55P03"}
                    or error.connection_invalidated
                    or (sqlstate and sqlstate.startswith("08"))
                ):
                    raise DomainError(
                        503, "TRANSFER_RETRY_REQUIRED", "Retry the same transfer request."
                    ) from None
                raise
            except Exception:
                session.rollback()
                raise
        raise AssertionError("Transfer retry boundary was exceeded.")

    def _create_attempt(
        self, actor_id: int, key: UUID, request: TransferCreate, fingerprint: str
    ) -> tuple[StockTransfer, bool]:
        session = self.repository.session
        try:
            if self.repository.get_product(request.product_id) is None:
                raise DomainError(404, "PRODUCT_NOT_FOUND", "Product was not found.")
            for warehouse_id in [request.source_warehouse_id, request.destination_warehouse_id]:
                if self.repository.get_warehouse(warehouse_id) is None:
                    raise DomainError(404, "WAREHOUSE_NOT_FOUND", "Warehouse was not found.")
            stocks = {
                warehouse_id: self.repository.lock_stock(warehouse_id, product_id)
                for warehouse_id, product_id in sorted(
                    [
                        (request.source_warehouse_id, request.product_id),
                        (request.destination_warehouse_id, request.product_id),
                    ]
                )
            }
            source, destination = (
                stocks[request.source_warehouse_id],
                stocks[request.destination_warehouse_id],
            )
            if source.quantity < request.quantity:
                raise DomainError(409, "INSUFFICIENT_STOCK", "Insufficient stock.")
            if destination.quantity > MAX_STOCK_QUANTITY - request.quantity:
                raise DomainError(
                    409, "STOCK_QUANTITY_LIMIT_EXCEEDED", "Stock quantity limit exceeded."
                )
            source_before, destination_before = source.quantity, destination.quantity
            source.quantity -= request.quantity
            self.repository.flush()
            destination.quantity += request.quantity
            self.repository.flush()
            common = {
                "product_id": request.product_id,
                "quantity": request.quantity,
                "actor_id": actor_id,
                "reference": request.reference,
                "note": request.note,
            }
            outbound, out_transaction = self.repository.add_leg(
                direction=TransactionType.OUTBOUND,
                warehouse_id=request.source_warehouse_id,
                **common,
            )
            inbound, in_transaction = self.repository.add_leg(
                direction=TransactionType.INBOUND,
                warehouse_id=request.destination_warehouse_id,
                **common,
            )
            transfer = StockTransfer(
                **request.model_dump(),
                created_by_id=actor_id,
                idempotency_key=key,
                request_fingerprint=fingerprint,
                source_quantity_before=source_before,
                source_quantity_after=source.quantity,
                destination_quantity_before=destination_before,
                destination_quantity_after=destination.quantity,
                outbound_id=outbound.id,
                inbound_id=inbound.id,
                outbound_transaction_id=out_transaction.id,
                inbound_transaction_id=in_transaction.id,
            )
            session.add(transfer)
            self.repository.flush()
            for transaction, purpose in [
                (out_transaction, "transfer_out"),
                (in_transaction, "transfer_in"),
            ]:
                session.add(
                    MovementProvenance(
                        transaction=transaction, purpose=purpose, transfer_id=transfer.id
                    )
                )
                self.repository.flush()
            session.commit()
            session.refresh(transfer)
            return transfer, False
        except Exception:
            # The outer attempt boundary owns rollback, retry and ambiguous-commit handling.
            raise
