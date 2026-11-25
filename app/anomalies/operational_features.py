"""Read-only, as-of inputs for scoring a committed operational B2B fulfillment."""

import hashlib
import hmac
import math
import re
import stat
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from types import MappingProxyType
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import and_, or_, select

from app.analytics.export import canonical_json
from app.analytics.ingestion import _bounded_read, _decode_json, checked_path
from app.analytics.schemas import PipelineError
from app.models.domain import (
    MovementProvenance,
    Outbound,
    Product,
    PurchaseRequest,
    PurchaseRequestWorkflow,
    StockTransaction,
    Warehouse,
)

MAX_COVERAGE_BYTES = 4 * 1024 * 1024
MAX_COVERAGE_ROWS = 10_000
MAX_HISTORY_ROWS = 10_000
_MAX_DB_ID = 2_147_483_647
_HEX = re.compile(r"[0-9a-f]{64}")
_UTC_ISO = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z")


class CoverageInvalid(ValueError):
    """The trusted history release cannot be used."""


class VerifiedOutboundView(BaseModel):
    outbound_id: int
    product_name: str
    product_sku: str
    warehouse_code: str
    warehouse_name: str
    quantity: int
    unit: str
    occurred_at: datetime
    performed_by_id: int


@dataclass(frozen=True)
class _Proof:
    available_at: datetime
    events_digest: str


@dataclass(frozen=True)
class Coverage:
    digest: str
    dataset_class: Literal["operational", "synthetic_test"]
    rows: Mapping[tuple[int, int, str, date], _Proof]


def _valid_unit(unit: object) -> bool:
    return (
        isinstance(unit, str)
        and 0 < len(unit) <= 40
        and unit.strip() == unit
        and unit.isprintable()
    )


def _positive_id(value: object) -> bool:
    return type(value) is int and 1 <= value <= _MAX_DB_ID


def _aware(value: object) -> bool:
    return isinstance(value, datetime) and value.utcoffset() is not None


def _hex(value: object) -> bool:
    return isinstance(value, str) and _HEX.fullmatch(value) is not None


def _next_day_start(day: date) -> datetime:
    return datetime.combine(day + timedelta(days=1), time.min, UTC)


def load_coverage(
    path: Path, expected_digest: str, *, allow_synthetic_test: bool = False
) -> Coverage:
    """Load a separately approved SHA-256-pinned, strictly bounded data-only release.

    Each row attests to the history of the *frozen unit* for one complete prior
    UTC day. Empty days require an explicit proof over the empty event list.
    Publication cannot precede the end of the asserted day.
    """
    try:
        if not _hex(expected_digest):
            raise ValueError
        path = checked_path(Path(path))
        if not stat.S_ISREG(path.stat().st_mode):
            raise ValueError
        body = _bounded_read(path, MAX_COVERAGE_BYTES)
        if not hmac.compare_digest(hashlib.sha256(body).hexdigest(), expected_digest):
            raise ValueError
        data = _decode_json(body.decode("utf-8"))
        if (
            not isinstance(data, dict)
            or set(data) != {"schema_version", "dataset_class", "rows"}
            or data["schema_version"] != "b2b-outbound-coverage/1"
            or not (
                data["dataset_class"] == "operational"
                or allow_synthetic_test and data["dataset_class"] == "synthetic_test"
            )
            or not isinstance(data["rows"], list)
            or not 0 < len(data["rows"]) <= MAX_COVERAGE_ROWS
        ):
            raise ValueError
        proofs = {}
        for row in data["rows"]:
            if not isinstance(row, dict) or set(row) != {
                "warehouse_id",
                "product_id",
                "unit",
                "day",
                "available_at",
                "complete",
                "events_digest",
            }:
                raise ValueError
            warehouse, product, unit = row["warehouse_id"], row["product_id"], row["unit"]
            if (
                not _positive_id(warehouse)
                or not _positive_id(product)
                or not _valid_unit(unit)
                or row["complete"] is not True
                or not _hex(row["events_digest"])
                or not isinstance(row["day"], str)
                or not isinstance(row["available_at"], str)
                or not _UTC_ISO.fullmatch(row["available_at"])
            ):
                raise ValueError
            day = date.fromisoformat(row["day"])
            available = datetime.fromisoformat(row["available_at"])
            key = (warehouse, product, unit, day)
            if day.isoformat() != row["day"] or available < _next_day_start(day) or key in proofs:
                raise ValueError
            proofs[key] = _Proof(available, row["events_digest"])
        return Coverage(expected_digest, data["dataset_class"], MappingProxyType(proofs))
    except (OSError, PipelineError, OverflowError, TypeError, ValueError):
        raise CoverageInvalid("invalid operational coverage") from None


def coverage_events_digest(rows: Iterable[tuple[int, int, datetime]]) -> str:
    """Digest of the exact ordered (transaction, quantity, UTC occurrence) records."""
    canonical = [
        (transaction_id, quantity, occurred_at.astimezone(UTC).isoformat(timespec="microseconds"))
        for transaction_id, quantity, occurred_at in rows
    ]
    return hashlib.sha256(canonical_json(sorted(canonical))).hexdigest()


def lineage_fingerprint(
    *,
    transaction_id: int,
    outbound_id: int,
    purchase_request_id: int,
    warehouse_id: int,
    product_id: int,
    quantity: int,
    unit: str,
    occurred_at: datetime,
    performed_by_id: int,
    request_reference: str,
    quantity_before: int,
    quantity_after: int,
) -> str:
    """Freeze the decisive business fields from the very first enqueue."""
    if (
        not all(
            _positive_id(value)
            for value in (
                transaction_id,
                outbound_id,
                purchase_request_id,
                warehouse_id,
                product_id,
                quantity,
                performed_by_id,
            )
        )
        or not _valid_unit(unit)
        or not _aware(occurred_at)
        or not isinstance(request_reference, str)
        or not request_reference
        or type(quantity_before) is not int
        or type(quantity_after) is not int
        or quantity_after < 0
        or quantity_before - quantity_after != quantity
    ):
        raise ValueError("invalid operational lineage facts")
    return hashlib.sha256(
        canonical_json(
            {
                "schema_version": "b2b-outbound-lineage/1",
                "transaction_id": transaction_id,
                "outbound_id": outbound_id,
                "purchase_request_id": purchase_request_id,
                "warehouse_id": warehouse_id,
                "product_id": product_id,
                "quantity": quantity,
                "unit": unit,
                "occurred_at": occurred_at.astimezone(UTC).isoformat(timespec="microseconds"),
                "performed_by_id": performed_by_id,
                "request_reference": request_reference,
                "quantity_before": quantity_before,
                "quantity_after": quantity_after,
            }
        )
    ).hexdigest()


def _lineage_query():
    tx, voucher, wf, req = StockTransaction, Outbound, PurchaseRequestWorkflow, PurchaseRequest
    prov = MovementProvenance
    return (
        select(
            tx.id.label("transaction_id"),
            tx.transaction_type,
            tx.inbound_id,
            tx.outbound_id,
            tx.product_id,
            tx.warehouse_id,
            tx.quantity,
            tx.created_at.label("transaction_at"),
            tx.created_by_id.label("transaction_actor"),
            voucher.id.label("voucher_id"),
            voucher.product_id.label("outbound_product"),
            voucher.warehouse_id.label("outbound_warehouse"),
            voucher.quantity.label("outbound_quantity"),
            voucher.created_at.label("outbound_at"),
            voucher.created_by_id.label("outbound_actor"),
            voucher.reference.label("outbound_reference"),
            wf.outbound_id.label("workflow_outbound"),
            wf.purchase_request_id.label("workflow_request"),
            wf.created_by_id.label("workflow_requester"),
            wf.decided_by_id,
            wf.decided_at,
            wf.decision_kind,
            wf.fulfilled_at,
            wf.fulfilled_by_id,
            wf.quantity_before,
            wf.quantity_after,
            req.id.label("request_id"),
            req.requested_by_id.label("requester"),
            req.created_at.label("request_at"),
            req.request_number,
            req.status,
            req.product_id.label("request_product"),
            req.warehouse_id.label("request_warehouse"),
            req.quantity.label("request_quantity"),
            prov.purpose,
            prov.transfer_id,
            Product.name.label("product_name"),
            Product.sku.label("product_sku"),
            Warehouse.name.label("warehouse_name"),
            Warehouse.code.label("warehouse_code"),
        )
        .select_from(tx)
        .outerjoin(voucher, voucher.id == tx.outbound_id)
        .outerjoin(wf, wf.outbound_transaction_id == tx.id)
        .outerjoin(req, req.id == wf.purchase_request_id)
        .outerjoin(prov, prov.transaction_id == tx.id)
        .outerjoin(Product, Product.id == tx.product_id)
        .outerjoin(Warehouse, Warehouse.id == tx.warehouse_id)
    )


def _lineage_valid(row) -> bool:
    times = (row.request_at, row.decided_at, row.outbound_at, row.transaction_at, row.fulfilled_at)
    return (
        row.transaction_type == "outbound"
        and row.inbound_id is None
        and row.purpose == "purchase_request_fulfillment"
        and row.transfer_id is None
        and row.decision_kind == "approved"
        and row.status == "fulfilled"
        and _positive_id(row.outbound_id)
        and row.outbound_id == row.voucher_id == row.workflow_outbound
        and _positive_id(row.request_id)
        and row.request_id == row.workflow_request
        and isinstance(row.request_number, str)
        and bool(row.request_number)
        and row.request_number == row.outbound_reference
        and _positive_id(row.requester)
        and row.requester == row.workflow_requester
        and _positive_id(row.decided_by_id)
        and _positive_id(row.fulfilled_by_id)
        and row.fulfilled_by_id == row.outbound_actor == row.transaction_actor
        and _positive_id(row.product_id)
        and row.product_id == row.outbound_product == row.request_product
        and _positive_id(row.warehouse_id)
        and row.warehouse_id == row.outbound_warehouse == row.request_warehouse
        and _positive_id(row.quantity)
        and row.quantity == row.outbound_quantity == row.request_quantity
        and type(row.quantity_before) is int
        and type(row.quantity_after) is int
        and row.quantity_after >= 0
        and row.quantity_before - row.quantity_after == row.quantity
        and all(_aware(value) for value in times)
        and tuple(sorted(times)) == times
        and all(
            isinstance(value, str)
            for value in (row.product_name, row.product_sku, row.warehouse_name, row.warehouse_code)
        )
    )


def resolve_lineage(session, job_or_claim) -> VerifiedOutboundView | None:
    """The only voucher identity is the committed transaction's exact FK lineage."""
    job = job_or_claim
    if (
        not _aware(job.occurred_at)
        or not _valid_unit(job.unit)
        or not _positive_id(job.transaction_id)
        or not _hex(job.source_fingerprint)
    ):
        return None
    rows = (
        session.execute(_lineage_query().where(StockTransaction.id == job.transaction_id).limit(2))
        .mappings()
        .all()
    )
    if len(rows) != 1:
        return None
    row = rows[0]
    if (
        not _lineage_valid(row)
        or row.outbound_id != job.outbound_id
        or row.request_id != job.purchase_request_id
        or row.product_id != job.product_id
        or row.warehouse_id != job.warehouse_id
        or row.quantity != job.quantity
        or row.fulfilled_at != job.occurred_at
        or not hmac.compare_digest(
            lineage_fingerprint(
                transaction_id=row.transaction_id,
                outbound_id=row.outbound_id,
                purchase_request_id=row.request_id,
                warehouse_id=row.warehouse_id,
                product_id=row.product_id,
                quantity=row.quantity,
                unit=job.unit,
                occurred_at=row.fulfilled_at,
                performed_by_id=row.fulfilled_by_id,
                request_reference=row.request_number,
                quantity_before=row.quantity_before,
                quantity_after=row.quantity_after,
            ),
            job.source_fingerprint,
        )
    ):
        return None
    return VerifiedOutboundView(
        outbound_id=row.outbound_id,
        product_name=row.product_name,
        product_sku=row.product_sku,
        warehouse_code=row.warehouse_code,
        warehouse_name=row.warehouse_name,
        quantity=row.quantity,
        unit=job.unit,
        occurred_at=row.fulfilled_at,
        performed_by_id=row.fulfilled_by_id,
    )


def _history(session, claim, start: datetime, end: datetime):
    tx, wf, req, prov = (
        StockTransaction,
        PurchaseRequestWorkflow,
        PurchaseRequest,
        MovementProvenance,
    )
    # An event near midnight may have a transaction created on a different day
    # from its completion. Retain both candidates until exact lineage is checked.
    return (
        session.execute(
            _lineage_query()
            .where(
                or_(
                    and_(
                        tx.product_id == claim.product_id,
                        tx.warehouse_id == claim.warehouse_id,
                    ),
                    and_(
                        req.product_id == claim.product_id,
                        req.warehouse_id == claim.warehouse_id,
                    ),
                ),
                or_(
                    and_(tx.created_at >= start, tx.created_at < end),
                    and_(wf.fulfilled_at >= start, wf.fulfilled_at < end),
                ),
                or_(
                    prov.purpose == "purchase_request_fulfillment",
                    wf.outbound_transaction_id.is_not(None),
                ),
            )
            .order_by(tx.id)
            .limit(MAX_HISTORY_ROWS + 1)
        )
        .mappings()
        .all()
    )


def build_features(session, claim, coverage: Coverage) -> tuple[tuple[float, ...], str] | None:
    """Compute the six anomaly-features/1 scalars using verified complete days."""
    target = resolve_lineage(session, claim)
    if target is None or not isinstance(coverage, Coverage):
        return None
    instant = target.occurred_at.astimezone(UTC)
    try:
        days = [instant.date() - timedelta(days=delta) for delta in range(7, 0, -1)]
    except OverflowError:
        return None
    proof_by_day = {
        day: coverage.rows.get((claim.warehouse_id, claim.product_id, claim.unit, day))
        for day in days
    }
    if any(proof is None or proof.available_at > instant for proof in proof_by_day.values()):
        return None
    start = datetime.combine(days[0], time.min, UTC)
    end = datetime.combine(instant.date(), time.min, UTC)
    history = _history(session, claim, start, end)
    if len(history) > MAX_HISTORY_ROWS:
        return None
    events_by_day: dict[date, list[tuple[int, int, datetime]]] = {day: [] for day in days}
    seen = set()
    total = count = 0
    for row in history:
        if (
            not _lineage_valid(row)
            or row.warehouse_id != claim.warehouse_id
            or row.product_id != claim.product_id
            or row.transaction_id in seen
        ):
            return None
        seen.add(row.transaction_id)
        previous = row.fulfilled_at.astimezone(UTC)
        if previous >= end:
            # Do not admit a current/future event just because stock was logged earlier.
            continue
        if previous < start:
            return None
        day = previous.date()
        proof = proof_by_day[day]
        if previous > proof.available_at:
            return None
        events_by_day[day].append((row.transaction_id, row.quantity, previous))
        total += row.quantity
        count += 1
    if any(
        not hmac.compare_digest(coverage_events_digest(events_by_day[day]), proof.events_digest)
        for day, proof in proof_by_day.items()
    ):
        return None
    mean = total / 7
    values = (
        math.log1p(target.quantity),
        instant.hour / 23,
        instant.weekday() / 6,
        math.log1p(mean),
        math.log1p(count),
        math.log1p(target.quantity / (1 + mean)),
    )
    fingerprint = hashlib.sha256(
        canonical_json(
            {
                "feature_version": "anomaly-features/1",
                "coverage_digest": coverage.digest,
                "transaction_id": claim.transaction_id,
                "voucher_id": claim.outbound_id,
                "request_id": claim.purchase_request_id,
                "warehouse_id": claim.warehouse_id,
                "product_id": claim.product_id,
                "unit": claim.unit,
                "as_of": instant.isoformat(timespec="microseconds"),
                "values": values,
            }
        )
    ).hexdigest()
    return values, fingerprint
