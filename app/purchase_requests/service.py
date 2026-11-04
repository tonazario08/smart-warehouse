"""Customer requests: one caller-owned transaction and immutable effect history."""

import json
from hashlib import sha256
from typing import NoReturn
from uuid import UUID, uuid4

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.auth.dependencies import PERMISSION_ROLES, Permission
from app.core.errors import DomainError
from app.core.pagination import PageParams
from app.inventory.schemas import InventoryMovementCreate
from app.models import (
    MovementProvenance,
    Outbound,
    PurchaseRequest,
    PurchaseRequestWorkflow,
    StockTransaction,
    User,
)
from app.models.domain import utc_now
from app.purchase_requests.repository import PurchaseRequestRecord, PurchaseRequestRepository
from app.purchase_requests.schemas import (
    PurchaseRequestCreate,
    PurchaseRequestFilters,
    PurchaseRequestReject,
    PurchaseRequestResponse,
)


def fingerprint(body: PurchaseRequestCreate) -> str:
    return sha256(
        json.dumps(
            body.model_dump(), sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode()
    ).hexdigest()


def conflict() -> NoReturn:
    raise DomainError(409, "PURCHASE_REQUEST_STATE_CONFLICT", "Purchase request state conflicts.")


class PurchaseRequestService:
    def __init__(self, repository: PurchaseRequestRepository):
        self.repository = repository

    def _authorize(self, actor: User, permission: Permission):
        if not actor.is_active:
            raise DomainError(401, "INVALID_CREDENTIALS", "Invalid authentication credentials.")
        if actor.role not in PERMISSION_ROLES[permission]:
            raise DomainError(403, "HTTP_403_ERROR", "Permission denied")

    def _owner(self, actor: User):
        return actor.id if actor.role == "client" else None

    def _project(self, record: PurchaseRequestRecord | None) -> PurchaseRequestResponse:
        if record is None:
            raise DomainError(404, "PURCHASE_REQUEST_NOT_FOUND", "Purchase request was not found.")
        row, workflow = record
        decision = fulfillment = None
        if workflow is not None:
            if workflow.created_by_id != row.requested_by_id:
                conflict()
            if workflow.note is not None and (
                not workflow.note or workflow.note != workflow.note.strip()
            ):
                conflict()
            try:
                original = PurchaseRequestCreate(
                    warehouse_id=row.warehouse_id,
                    product_id=row.product_id,
                    quantity=row.quantity,
                    note=workflow.note,
                )
            except ValidationError:
                conflict()
            if fingerprint(original) != workflow.request_fingerprint:
                conflict()
            if workflow.decision_kind is not None:
                if workflow.decided_by_id is None or workflow.decided_at is None:
                    conflict()
                decision = {
                    "kind": workflow.decision_kind,
                    "actor_id": workflow.decided_by_id,
                    "decided_at": workflow.decided_at,
                    "rejection_reason": workflow.rejection_reason,
                }
            fields = [
                workflow.outbound_id,
                workflow.outbound_transaction_id,
                workflow.fulfilled_by_id,
                workflow.fulfilled_at,
                workflow.quantity_before,
                workflow.quantity_after,
            ]
            if any(value is not None for value in fields):
                if any(value is None for value in fields) or workflow.decision_kind != "approved":
                    conflict()
                if workflow.quantity_before - workflow.quantity_after != row.quantity:
                    conflict()
                session = self.repository.session
                outbound = session.scalar(
                    select(Outbound)
                    .where(Outbound.id == workflow.outbound_id)
                    .execution_options(populate_existing=True)
                )
                transaction = session.scalar(
                    select(StockTransaction)
                    .where(StockTransaction.id == workflow.outbound_transaction_id)
                    .execution_options(populate_existing=True)
                )
                provenance = session.get(
                    MovementProvenance, workflow.outbound_transaction_id, populate_existing=True
                )
                if outbound is None or transaction is None or provenance is None:
                    conflict()
                expected = (
                    row.warehouse_id,
                    row.product_id,
                    row.quantity,
                    workflow.fulfilled_by_id,
                )
                if any(
                    (leg.warehouse_id, leg.product_id, leg.quantity, leg.created_by_id) != expected
                    for leg in (outbound, transaction)
                ):
                    conflict()
                if (
                    transaction.transaction_type != "outbound"
                    or transaction.outbound_id != outbound.id
                    or transaction.inbound_id is not None
                    or provenance.purpose != "purchase_request_fulfillment"
                    or provenance.transfer_id is not None
                    or outbound.reference != row.request_number
                    or outbound.note != workflow.note
                ):
                    conflict()
                fulfillment = {
                    "outbound_id": outbound.id,
                    "transaction_id": transaction.id,
                    "actor_id": workflow.fulfilled_by_id,
                    "fulfilled_at": workflow.fulfilled_at,
                    "quantity_before": workflow.quantity_before,
                    "quantity_after": workflow.quantity_after,
                }
            expected_status = "fulfilled" if fulfillment else workflow.decision_kind or "pending"
            if row.status != expected_status:
                conflict()
        return PurchaseRequestResponse(
            id=row.id,
            request_number=row.request_number,
            warehouse_id=row.warehouse_id,
            product_id=row.product_id,
            quantity=row.quantity,
            status=row.status,
            requested_by_id=row.requested_by_id,
            created_at=row.created_at,
            updated_at=row.updated_at,
            workflow_managed=workflow is not None,
            note=workflow.note if workflow else None,
            decision=decision,
            fulfillment=fulfillment,
        )

    def get(self, actor: User, request_id: int) -> PurchaseRequestResponse:
        self._authorize(actor, Permission.PURCHASE_REQUEST_READ)
        return self._project(self.repository.get_owned(request_id, owner_id=self._owner(actor)))

    def get_by_key(self, actor: User, key: UUID) -> PurchaseRequestResponse:
        self._authorize(actor, Permission.PURCHASE_REQUEST_READ)
        return self._project(self.repository.find_by_key(actor.id, key))

    def list(
        self, actor: User, filters: PurchaseRequestFilters, page: PageParams
    ) -> tuple[list[PurchaseRequestResponse], int]:
        self._authorize(actor, Permission.PURCHASE_REQUEST_READ)
        if actor.role == "client" and filters.requested_by_id is not None:
            raise DomainError(
                422, "REQUEST_VALIDATION_ERROR", "Client owner filters are forbidden."
            )
        rows, total = self.repository.list_owned(filters, page, owner_id=self._owner(actor))
        return [self._project(row) for row in rows], total

    def _write(self, actor: User, permission: Permission, operation):
        self._authorize(actor, permission)
        session = self.repository.session
        for attempt in range(3):
            try:
                result = operation()
                session.commit()
                return result
            except DBAPIError as error:
                state = getattr(error.orig, "sqlstate", None)
                rollback_ok = self._rollback()
                if (
                    state in {"40P01", "40001"}
                    and rollback_ok
                    and not error.connection_invalidated
                    and attempt < 2
                ):
                    session.expire_all()
                    continue
                if (
                    state in {"40P01", "40001", "55P03"}
                    or not rollback_ok
                    or error.connection_invalidated
                    or (state and state.startswith("08"))
                ):
                    raise DomainError(
                        503,
                        "PURCHASE_REQUEST_RETRY_REQUIRED",
                        "Retry exactly the same purchase request action.",
                    ) from None
                if isinstance(error, IntegrityError):
                    raise DomainError(
                        409, "DATABASE_CONFLICT", "Database conflict occurred."
                    ) from None
                raise
            except Exception:
                if not self._rollback():
                    raise DomainError(
                        503,
                        "PURCHASE_REQUEST_RETRY_REQUIRED",
                        "Retry exactly the same purchase request action.",
                    ) from None
                raise
        raise AssertionError("Purchase request retry boundary was exceeded.")

    def _rollback(self) -> bool:
        try:
            self.repository.session.rollback()
            return True
        except DBAPIError:
            self.repository.session.invalidate()
            return False

    def _admit(self, row):
        product = self.repository.get_requestable_product(row.product_id)
        if product is None:
            raise DomainError(404, "PRODUCT_NOT_FOUND", "Product was not found.")
        if not product.is_active:
            raise DomainError(409, "PRODUCT_NOT_REQUESTABLE", "Product is not requestable.")
        if self.repository.get_warehouse(row.warehouse_id) is None:
            raise DomainError(404, "WAREHOUSE_NOT_FOUND", "Warehouse was not found.")

    def create(
        self, actor: User, key: UUID, body: PurchaseRequestCreate
    ) -> tuple[PurchaseRequestResponse, bool]:
        actor_id, digest = actor.id, fingerprint(body)

        def operation():
            self.repository.lock_key(actor_id, key)
            existing = self.repository.find_by_key(actor_id, key)
            if existing is not None:
                result = self._project(existing)
                if existing[1].request_fingerprint != digest:
                    raise DomainError(
                        409, "IDEMPOTENCY_KEY_CONFLICT", "Key belongs to another body."
                    )
                return result, True
            self._admit(body)
            row = PurchaseRequest(
                **body.model_dump(exclude={"note"}),
                request_number="PR-" + uuid4().hex,
                requested_by_id=actor_id,
            )
            self.repository.session.add(row)
            self.repository.flush()
            workflow = PurchaseRequestWorkflow(
                purchase_request_id=row.id,
                created_by_id=actor_id,
                idempotency_key=key,
                request_fingerprint=digest,
                note=body.note,
            )
            self.repository.session.add(workflow)
            self.repository.flush()
            return self._project((row, workflow)), False

        return self._write(actor, Permission.PURCHASE_REQUEST_CREATE, operation)

    def approve(self, actor: User, request_id: int) -> PurchaseRequestResponse:
        actor_id = actor.id

        def operation():
            row, workflow, current = self._locked(request_id)
            if workflow.decision_kind == "approved":
                return current
            if row.status != "pending":
                conflict()
            self._admit(row)
            row.status = "approved"
            workflow.decision_kind = "approved"
            workflow.decided_by_id, workflow.decided_at = actor_id, utc_now()
            self.repository.flush()
            return self._project((row, workflow))

        return self._write(actor, Permission.PURCHASE_REQUEST_REVIEW, operation)

    def reject(
        self, actor: User, request_id: int, body: PurchaseRequestReject
    ) -> PurchaseRequestResponse:
        actor_id = actor.id

        def operation():
            row, workflow, current = self._locked(request_id)
            if (
                workflow.decision_kind == "rejected"
                and workflow.rejection_reason == body.rejection_reason
            ):
                return current
            if row.status != "pending":
                conflict()
            row.status = "rejected"
            workflow.decision_kind = "rejected"
            workflow.decided_by_id, workflow.decided_at = actor_id, utc_now()
            workflow.rejection_reason = body.rejection_reason
            self.repository.flush()
            return self._project((row, workflow))

        return self._write(actor, Permission.PURCHASE_REQUEST_REVIEW, operation)

    def fulfill(self, actor: User, request_id: int) -> PurchaseRequestResponse:
        actor_id = actor.id

        def operation():
            row, workflow, current = self._locked(request_id)
            if row.status == "fulfilled":
                return current
            if row.status != "approved":
                conflict()
            self._admit(row)
            stock = self.repository.lock_existing_stock(row.warehouse_id, row.product_id)
            if stock is None or stock.quantity < row.quantity:
                raise DomainError(409, "INSUFFICIENT_STOCK", "Insufficient stock.")
            before = stock.quantity
            stock.quantity -= row.quantity
            self.repository.flush()
            outbound = self.repository.add_outbound(
                InventoryMovementCreate(
                    warehouse_id=row.warehouse_id,
                    product_id=row.product_id,
                    quantity=row.quantity,
                    reference=row.request_number,
                    note=workflow.note,
                ),
                actor_id,
            )
            self.repository.flush()
            transaction = self.repository.add_stock_transaction_for_outbound(
                outbound, actor_id, purpose="purchase_request_fulfillment"
            )
            self.repository.flush()
            workflow.fulfilled_by_id, workflow.fulfilled_at = actor_id, utc_now()
            workflow.outbound_id, workflow.outbound_transaction_id = outbound.id, transaction.id
            workflow.quantity_before, workflow.quantity_after = before, stock.quantity
            row.status = "fulfilled"
            self.repository.flush()
            return self._project((row, workflow))

        return self._write(actor, Permission.PURCHASE_REQUEST_FULFILL, operation)

    def _locked(self, request_id: int):
        row = self.repository.lock_request(request_id)
        if row is None:
            self._project(None)
        workflow = self.repository.get_workflow(request_id)
        if workflow is None:
            raise DomainError(
                409, "LEGACY_PURCHASE_REQUEST_READ_ONLY", "Legacy purchase request is read-only."
            )
        return row, workflow, self._project((row, workflow))
