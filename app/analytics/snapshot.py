"""Bounded scalar extraction in one enforced read-only repeatable PostgreSQL snapshot."""

import hashlib
import re
from datetime import timedelta

from sqlalchemy import and_, or_, select, text, tuple_
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError, DBAPIError

from app.analytics.export import canonical_json
from app.analytics.ingestion import validate_batch
from app.analytics.schemas import (
    MAX_ROWS,
    EventRecord,
    PipelineError,
    QualityReport,
    SourceBatch,
    business_day_bounds,
    load_timezone,
)
from app.models import (
    MovementProvenance,
    Outbound,
    PurchaseRequest,
    PurchaseRequestWorkflow,
    StockTransaction,
)


def validate_database_url(value, identity):
    try:
        url = make_url(value)
        if (
            identity is None
            or url.drivername != "postgresql+psycopg"
            or (url.host, url.port, url.database, url.username)
            != (identity.host, identity.port, identity.database, identity.username)
            or set(url.query) - {"connect_timeout"}
            or (url.query and url.query.get("connect_timeout") != "5")
        ):
            raise ValueError
        return url
    except (ArgumentError, TypeError, ValueError):
        raise PipelineError("DATABASE_IDENTITY") from None


def capture_operational(engine, admission):
    validate_database_url(engine.url, admission.source.database_identity)
    if admission.source.kind != "operational_b2b":
        raise PipelineError("ADMISSION_INVALID")
    pairs = set()
    for mapping in admission.mappings:
        if any(
            re.fullmatch(r"[1-9][0-9]{0,9}", value) is None or int(value) > 2147483647
            for value in (mapping.source_product, mapping.source_warehouse)
        ):
            raise PipelineError("UNKNOWN_MAPPING")
        pairs.add((int(mapping.source_product), int(mapping.source_warehouse)))
    start = business_day_bounds(admission.window_start, admission.business_timezone)[0]
    stop = business_day_bounds(
        admission.window_end - timedelta(days=1), admission.business_timezone
    )[1]
    try:
        with engine.connect().execution_options(isolation_level="REPEATABLE READ") as connection:
            transaction = connection.begin()
            try:
                connection.execute(text("SET TRANSACTION READ ONLY"))
                actual = connection.execute(
                    text(
                        "SELECT current_database(), current_user, "
                        "current_setting('transaction_read_only')"
                    )
                ).one()
                identity = admission.source.database_identity
                if actual[:2] != (identity.database, identity.username):
                    raise PipelineError("DATABASE_IDENTITY")
                if actual[2] != "on":
                    raise PipelineError("DATABASE_READ_ONLY")
                return _capture(connection, admission, pairs, start, stop)
            finally:
                transaction.rollback()
    except DBAPIError as error:
        code = (
            "DATABASE_READ_ONLY"
            if getattr(error.orig, "sqlstate", None) == "25006"
            else ("DATABASE_UNAVAILABLE")
        )
        raise PipelineError(code) from None


def _rows(connection, query):
    result = connection.execute(query.limit(MAX_ROWS + 1)).mappings().all()
    if len(result) > MAX_ROWS:
        raise PipelineError("INPUT_LIMIT")
    return [dict(row) for row in result]


def _capture(connection, admission, pairs, start, stop):
    tx, provenance = StockTransaction.__table__, MovementProvenance.__table__
    workflow, request = PurchaseRequestWorkflow.__table__, PurchaseRequest.__table__
    outbound = Outbound.__table__
    columns = [
        tx.c[name]
        for name in (
            "id",
            "transaction_type",
            "warehouse_id",
            "product_id",
            "quantity",
            "inbound_id",
            "outbound_id",
            "created_at",
        )
    ]
    movements = _rows(
        connection,
        select(*columns, provenance.c.purpose)
        .select_from(tx.outerjoin(provenance, provenance.c.transaction_id == tx.c.id))
        .where(
            tuple_(tx.c.product_id, tx.c.warehouse_id).in_(sorted(pairs)),
            tx.c.created_at >= start,
            tx.c.created_at < stop,
        )
        .order_by(tx.c.id),
    )
    target_ids = {
        row["id"] for row in movements if row["purpose"] == "purchase_request_fulfillment"
    }
    # Outer joins deliberately retain malformed/missing target legs for parity checks.
    selected = []
    for table, prefix, names in (
        (
            workflow,
            "wf",
            (
                "purchase_request_id",
                "decision_kind",
                "decided_at",
                "fulfilled_at",
                "outbound_id",
                "outbound_transaction_id",
                "quantity_before",
                "quantity_after",
            ),
        ),
        (request, "pr", ("id", "warehouse_id", "product_id", "quantity", "status", "created_at")),
        (outbound, "out", ("id", "warehouse_id", "product_id", "quantity", "created_at")),
        (
            tx,
            "tx",
            (
                "id",
                "warehouse_id",
                "product_id",
                "quantity",
                "transaction_type",
                "inbound_id",
                "outbound_id",
                "created_at",
            ),
        ),
        (provenance, "mp", ("purpose",)),
    ):
        selected.extend(table.c[name].label(f"{prefix}_{name}") for name in names)
    joins = (
        workflow.outerjoin(request, request.c.id == workflow.c.purchase_request_id)
        .outerjoin(outbound, outbound.c.id == workflow.c.outbound_id)
        .outerjoin(tx, tx.c.id == workflow.c.outbound_transaction_id)
        .outerjoin(provenance, provenance.c.transaction_id == tx.c.id)
    )
    candidates = _rows(
        connection,
        select(*selected)
        .select_from(joins)
        .where(
            or_(
                and_(
                    tuple_(request.c.product_id, request.c.warehouse_id).in_(sorted(pairs)),
                    workflow.c.fulfilled_at >= start,
                    workflow.c.fulfilled_at < stop,
                ),
                workflow.c.outbound_transaction_id.in_(sorted(target_ids)),
            )
        )
        .order_by(workflow.c.purchase_request_id),
    )
    records, matched, identities = [], set(), set()
    for row in candidates:
        _validate_link(row, admission.cutoff)
        tx_id = row["tx_id"]
        if tx_id in identities:
            raise PipelineError("LINKAGE_CONFLICT")
        identities.add(tx_id)
        matched.add(tx_id)
        occurred = row["wf_fulfilled_at"]
        if start <= occurred < stop:
            records.append(
                _event(
                    admission,
                    tx_id,
                    row["pr_product_id"],
                    row["pr_warehouse_id"],
                    row["pr_quantity"],
                    "purchase_request_fulfillment",
                    occurred,
                    max(
                        row[name]
                        for name in (
                            "pr_created_at",
                            "wf_decided_at",
                            "wf_fulfilled_at",
                            "out_created_at",
                            "tx_created_at",
                        )
                    ),
                )
            )
    if target_ids - matched:
        raise PipelineError("LINKAGE_CONFLICT")
    for row in movements:
        if row["id"] in matched:
            continue
        purpose = row["purpose"] or "legacy_unknown"
        if purpose not in admission.source.kind_map:
            raise PipelineError("LINKAGE_CONFLICT")
        expected_direction = {
            "standard_inbound": "inbound",
            "transfer_in": "inbound",
            "standard_outbound": "outbound",
            "transfer_out": "outbound",
        }
        if purpose in expected_direction and row["transaction_type"] != expected_direction[purpose]:
            raise PipelineError("LINKAGE_CONFLICT")
        records.append(
            _event(
                admission,
                row["id"],
                row["product_id"],
                row["warehouse_id"],
                row["quantity"],
                purpose,
                row["created_at"],
                row["created_at"],
            )
        )
    if len(records) > MAX_ROWS:
        raise PipelineError("INPUT_LIMIT")
    source_checksum = hashlib.sha256(
        canonical_json({"movements": movements, "fulfillments": candidates})
    ).hexdigest()
    batch = SourceBatch(
        source_checksum=source_checksum,
        records=tuple(records),
        report=QualityReport(
            input_rows=len(records),
            accepted_rows=len(records),
            duplicate_rows=0,
            excluded_rows=0,
            rejected_rows=0,
            exclusions={},
            issues=(),
            warnings=(),
        ),
    )
    return validate_batch(admission, batch)


def _validate_link(row, cutoff):
    required = (
        "pr_id",
        "out_id",
        "tx_id",
        "wf_decided_at",
        "wf_fulfilled_at",
        "pr_created_at",
        "out_created_at",
        "tx_created_at",
        "wf_quantity_before",
        "wf_quantity_after",
    )
    if any(row[key] is None for key in required):
        raise PipelineError("LINKAGE_CONFLICT")
    times = [
        row[key]
        for key in (
            "pr_created_at",
            "wf_decided_at",
            "out_created_at",
            "tx_created_at",
            "wf_fulfilled_at",
        )
    ]
    if max(times) > cutoff:
        raise PipelineError("AFTER_CUTOFF")
    if (
        row["pr_status"] != "fulfilled"
        or row["wf_decision_kind"] != "approved"
        or row["mp_purpose"] != "purchase_request_fulfillment"
        or row["tx_transaction_type"] != "outbound"
        or row["tx_inbound_id"] is not None
        or row["tx_outbound_id"] != row["out_id"]
        or row["wf_quantity_before"] - row["wf_quantity_after"] != row["pr_quantity"]
        or times != sorted(times)
        or any(
            row[f"{prefix}_{field}"] != row[f"pr_{field}"]
            for prefix in ("tx", "out")
            for field in ("warehouse_id", "product_id", "quantity")
        )
    ):
        raise PipelineError("LINKAGE_CONFLICT")


def _event(admission, tx_id, product, warehouse, quantity, purpose, occurred, available):
    day = occurred.astimezone(load_timezone(admission.business_timezone)).date()
    mappings = [
        row
        for row in admission.mappings
        if row.source_product == str(product)
        and row.source_warehouse == str(warehouse)
        and row.valid_from <= day < row.valid_to
    ]
    if len(mappings) != 1:
        raise PipelineError("UNKNOWN_MAPPING")
    return EventRecord(
        event_id=f"tx:{tx_id}",
        source_product=str(product),
        source_warehouse=str(warehouse),
        unit=mappings[0].unit,
        kind=purpose,
        quantity=quantity,
        occurred_at=occurred,
        available_at=available,
    )
