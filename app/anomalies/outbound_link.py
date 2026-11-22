"""Verified fixture-only bridge; never infer an outbound voucher by quantity, date or ID shape."""

import hashlib
import re
from datetime import datetime
from pathlib import Path
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Connection, Engine, make_url
from sqlalchemy.orm import Session

from app.analytics.export import _Manifest, _verify, canonical_json
from app.analytics.schemas import Admission
from app.analytics.semantics import admission_semantics
from app.analytics.snapshot import capture_operational
from app.anomalies.catalog import PublicAnomalyRun
from app.anomalies.dataset import load_anomaly_dataset
from app.anomalies.features import build_feature_snapshot
from app.anomalies.models import AnomalyOutboundLink
from app.anomalies.schemas import AnomalyConfig, Partition
from app.anomalies.service import _enabled, _get_alert, _not_found
from app.core.config import Settings
from app.models import (
    MovementProvenance,
    Outbound,
    Product,
    PurchaseRequest,
    PurchaseRequestWorkflow,
    StockTransaction,
    Warehouse,
)

DEMO_DB = "sw_b2b_outbound_demo_test"
_TEST_IDENTITIES = {
    ("127.0.0.1", 18547, "sw_m7_replenishment_test", "sw_m7_replenishment_test"),
    ("127.0.0.1", 55432, "smart_warehouse_test", "smart_warehouse_test"),
    ("127.0.0.1", 18546, "sw_m5_demand_test", "sw_m5_demand_test"),
}


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


def demo_snapshot_id(demo_id: UUID) -> str:
    return f"b2b-outbound-demo-{demo_id.hex}"


def _database(session: Session, settings: Settings) -> Engine | None:
    if not _enabled(settings) or settings.anomalies_outbound_link_demo_id is None:
        return None
    url = make_url(settings.database_url)
    identity = (url.host, url.port, url.database, url.username)
    allowed = (
        url.host in {"127.0.0.1", "::1"}
        and url.port is not None
        and (url.database, url.username) == (DEMO_DB, DEMO_DB)
    ) or (settings.app_env == "test" and identity in _TEST_IDENTITIES)
    if (
        url.drivername != "postgresql+psycopg"
        or not allowed
        or url.query not in ({}, {"connect_timeout": "5"})
    ):
        return None
    bind = session.get_bind()
    engine = bind.engine if isinstance(bind, Connection) else bind
    if not isinstance(engine, Engine) or engine.url != url:
        return None
    actual = session.execute(text("SELECT current_database(), current_user")).one()
    return engine if tuple(actual) == (url.database, url.username) else None


def _live_proof(session: Session, transaction_id: int, *, lock: bool = False):
    tx = StockTransaction
    outbound = Outbound
    workflow = PurchaseRequestWorkflow
    request = PurchaseRequest
    provenance = MovementProvenance
    query = (
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
            outbound.product_id.label("outbound_product_id"),
            outbound.warehouse_id.label("outbound_warehouse_id"),
            outbound.quantity.label("outbound_quantity"),
            outbound.created_at.label("outbound_at"),
            outbound.created_by_id.label("outbound_actor"),
            outbound.reference.label("outbound_reference"),
            workflow.fulfilled_at,
            workflow.fulfilled_by_id,
            workflow.decided_at,
            workflow.decision_kind,
            workflow.quantity_before,
            workflow.quantity_after,
            request.id.label("request_id"),
            request.created_at.label("request_at"),
            request.request_number,
            request.status,
            request.product_id.label("request_product_id"),
            request.warehouse_id.label("request_warehouse_id"),
            request.quantity.label("request_quantity"),
            provenance.purpose,
            Product.sku.label("product_sku"),
            Product.name.label("product_name"),
            Warehouse.code.label("warehouse_code"),
            Warehouse.name.label("warehouse_name"),
        )
        .select_from(tx)
        .join(outbound, outbound.id == tx.outbound_id)
        .join(
            workflow,
            (workflow.outbound_transaction_id == tx.id) & (workflow.outbound_id == outbound.id),
        )
        .join(request, request.id == workflow.purchase_request_id)
        .join(provenance, provenance.transaction_id == tx.id)
        .join(Product, Product.id == tx.product_id)
        .join(Warehouse, Warehouse.id == tx.warehouse_id)
        .where(tx.id == transaction_id)
        .limit(2)
    )
    if lock:
        query = query.with_for_update(of=(tx, outbound, workflow, request, provenance), read=True)
    rows = session.execute(query).mappings().all()
    if len(rows) != 1:
        return None
    row = rows[0]
    times = (
        row.request_at,
        row.decided_at,
        row.outbound_at,
        row.transaction_at,
        row.fulfilled_at,
    )
    if (
        row.transaction_type != "outbound"
        or row.inbound_id is not None
        or row.purpose != "purchase_request_fulfillment"
        or row.decision_kind != "approved"
        or row.status != "fulfilled"
        or not row.request_number
        or row.request_number != row.outbound_reference
        or not row.fulfilled_by_id
        or not row.fulfilled_by_id == row.outbound_actor == row.transaction_actor
        or not row.product_id == row.outbound_product_id == row.request_product_id
        or not row.warehouse_id == row.outbound_warehouse_id == row.request_warehouse_id
        or not row.quantity == row.outbound_quantity == row.request_quantity
        or row.quantity_before is None
        or row.quantity_after is None
        or row.quantity_before - row.quantity_after != row.quantity
        or any(value is None for value in times)
        or tuple(sorted(times)) != times
    ):
        return None
    return row


def _fingerprint(row, unit: str) -> str:
    # Names can be updated; stable identifiers, quantities and provenance cannot be substituted.
    fields = dict(row)
    for label in ("product_name", "warehouse_name"):
        fields.pop(label)
    return hashlib.sha256(canonical_json({"source": fields, "unit": unit})).hexdigest()


def _validate_admission(admission: Admission, manifest: _Manifest) -> None:
    if canonical_json(manifest.admission) != canonical_json(admission_semantics(admission)):
        raise ValueError("outbound source admission mismatch")


def bind_verified_outbound(
    session: Session,
    settings: Settings,
    *,
    run: PublicAnomalyRun,
    alert_id: str,
    bundle_path: Path,
    admission: Admission,
    event_id: str,
    request_reference: str,
) -> bool:
    """Offline only, caller commits with import; a replay returns False."""
    engine = _database(session, settings)
    demo_id = settings.anomalies_outbound_link_demo_id
    if engine is None or demo_id is None:
        raise ValueError("outbound link demo not enabled")
    if not re.fullmatch(r"tx:[1-9][0-9]{0,9}", event_id) or not re.fullmatch(
        r"PR-[0-9a-f]{32}", request_reference
    ):
        raise ValueError("outbound source identity invalid")
    manifest = _verify(bundle_path)
    if (
        not isinstance(manifest, _Manifest)
        or manifest.admission.dataset_class != "fixture"
        or manifest.admission.business_timezone != "UTC"
        or manifest.admission.target != "gross_fulfilled_units"
        or manifest.admission.source.kind != "operational_b2b"
        or manifest.admission.source.snapshot_id != demo_snapshot_id(demo_id)
        or run.payload.input_version != manifest.data_version
        or run.payload.source_hashes != {**manifest.artifacts, "source": manifest.source_checksum}
    ):
        raise ValueError("outbound source bundle mismatch")
    _validate_admission(admission, manifest)
    captured = capture_operational(engine, admission)
    if captured.source_checksum != manifest.source_checksum:
        raise ValueError("outbound source snapshot mismatch")
    config = AnomalyConfig(
        data_version=manifest.data_version,
        allow_fixture=True,
        created_at=run.payload.created_at,
        partitions=tuple(Partition.model_validate(p.model_dump()) for p in run.payload.partitions),
    )
    dataset = load_anomaly_dataset(config, bundle_path)
    # The bound checksums connect the samples to the exact live validated source.
    live = [event for event in captured.records if event.event_id == event_id]
    bundled = [event for event in dataset.events if event.event_id == event_id]
    if len(live) != 1 or bundled != live or live[0].kind != "purchase_request_fulfillment":
        raise ValueError("outbound source event mismatch")
    event = live[0]
    samples = [
        item for item in build_feature_snapshot(dataset).samples if item.event_id == event_id
    ]
    alert, stored_run, payload, public = _get_alert(session, alert_id)
    if (
        stored_run.run_id != run.run_id
        or payload != run.payload
        or len(samples) != 1
        or samples[0].source_record_key != alert.source_record_key
        or samples[0].occurred_at != public.occurred_at
        or samples[0].partition != public.partition
        or samples[0].values != public.features
    ):
        raise ValueError("outbound source alert mismatch")
    transaction_id = int(event_id.removeprefix("tx:"))
    row = _live_proof(session, transaction_id, lock=True)
    if (
        row is None
        or row.request_number != request_reference
        or str(row.product_id) != event.source_product
        or str(row.warehouse_id) != event.source_warehouse
        or row.quantity != event.quantity
        or row.fulfilled_at != event.occurred_at
    ):
        raise ValueError("outbound source transaction mismatch")
    values = {
        "alert_id": alert_id,
        "transaction_id": transaction_id,
        "outbound_id": row.outbound_id,
        "demo_id": demo_id,
        "bundle_id": manifest.data_version,
        "source_checksum": manifest.source_checksum,
        "source_fingerprint": _fingerprint(row, event.unit),
        "unit": event.unit,
    }
    created = session.scalar(
        insert(AnomalyOutboundLink)
        .values(**values)
        .on_conflict_do_nothing(index_elements=["alert_id"])
        .returning(AnomalyOutboundLink.alert_id)
    )
    if created is not None:
        return True
    existing = session.get(AnomalyOutboundLink, alert_id)
    if existing is None or any(getattr(existing, key) != value for key, value in values.items()):
        raise ValueError("outbound link conflicts with prior proof")
    return False


def verified_outbound(session: Session, settings: Settings, alert_id: str) -> VerifiedOutboundView:
    """Router must require both permissions before calling this read-only service."""
    if _database(session, settings) is None:
        raise _not_found()
    link = session.get(AnomalyOutboundLink, alert_id)
    if link is None or link.demo_id != settings.anomalies_outbound_link_demo_id:
        raise _not_found()
    _, _, payload, public = _get_alert(session, alert_id)
    if (
        payload.input_version != link.bundle_id
        or payload.source_hashes["source"] != link.source_checksum
    ):
        raise _not_found()
    row = _live_proof(session, link.transaction_id)
    if (
        row is None
        or row.outbound_id != link.outbound_id
        or row.fulfilled_at != public.occurred_at
        or _fingerprint(row, link.unit) != link.source_fingerprint
    ):
        raise _not_found()
    return VerifiedOutboundView(
        outbound_id=row.outbound_id,
        product_name=row.product_name,
        product_sku=row.product_sku,
        warehouse_code=row.warehouse_code,
        warehouse_name=row.warehouse_name,
        quantity=row.quantity,
        unit=link.unit,
        occurred_at=row.fulfilled_at,
        performed_by_id=row.fulfilled_by_id,
    )
