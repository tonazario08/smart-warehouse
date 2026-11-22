"""Resolve catalog context without rewriting models or published artifacts."""

from datetime import timedelta
from math import isfinite

from sqlalchemy import func, select

from app.analytics.schemas import load_timezone
from app.forecasting.repository import ForecastRepository
from app.models import Product
from app.order_analytics.repository import get_key_state, write_key_state
from app.replenishment.repository import ReplenishmentRepository


class ContextConflict(Exception):
    """A concurrent worker already wrote context for the same key."""


def _write_context(session, job, seen, values):
    if not write_key_state(session, job.warehouse_id, job.product_id, seen, **values):
        raise ContextConflict


def update_forecast_context(session, job, settings):
    state = get_key_state(session, job.warehouse_id, job.product_id)
    version = state.row_version if state else None
    product = session.get(Product, job.product_id)
    matched = None
    if product is not None and settings.forecast_catalog_root is not None:
        repository = ForecastRepository(
            settings.forecast_catalog_root, allow_fixture=settings.forecast_allow_fixture
        )
        matched = next(
            (
                run
                for run in repository.list_scope("operational")
                if run.binding is not None
                and run.binding.product_id == job.product_id
                and run.binding.warehouse_id == job.warehouse_id
                and run.binding.unit == product.unit
            ),
            None,
        )
    if matched is None:
        values = {
            "forecast_status": "insufficient_data",
            "forecast_reason_code": "BASELINE_NOT_FOUND",
            "forecast_run_id": None,
            "forecast_dataset_class": None,
            "forecast_stale": None,
        }
    else:
        manifest = matched.manifest
        today = (
            session.scalar(select(func.clock_timestamp()))
            .astimezone(load_timezone(manifest.business_timezone))
            .date()
        )
        values = {
            "forecast_status": "available",
            "forecast_reason_code": None,
            "forecast_run_id": manifest.run_id,
            "forecast_dataset_class": manifest.dataset_class,
            "forecast_stale": (
                manifest.origin_end != today - timedelta(days=1)
                or not any(row.target_date == today for row in matched.rows)
            ),
        }
    _write_context(session, job, version, values)


def matching_replenishment(snapshot, warehouse_id, product_id, unit, *, demo):
    manifest = snapshot["manifest"]
    binding = manifest.get("binding") or {}
    return (
        manifest.get("mode") == "operational"
        and manifest.get("reporting_scope") == "warehouse"
        and (
            manifest.get("dataset_class") == "fixture"
            if demo
            else manifest.get("dataset_class") not in {None, "fixture", "research"}
        )
        and (binding.get("warehouse_id"), binding.get("product_id"), binding.get("unit"))
        == (warehouse_id, product_id, unit)
    )


def update_replenishment_context(session, job, settings):
    state = get_key_state(session, job.warehouse_id, job.product_id)
    version = state.row_version if state else None
    product = session.get(Product, job.product_id)
    operational = demo = None
    if product is not None and settings.replenishment_catalog_root is not None:
        repository = ReplenishmentRepository(
            settings.replenishment_catalog_root,
            allow_fixture=settings.replenishment_allow_fixture,
        )
        for _, _, path in repository.index("operational"):
            snapshot = repository.snapshot(path)
            args = (snapshot, job.warehouse_id, job.product_id, product.unit)
            manifest = snapshot["manifest"]
            if demo is None and matching_replenishment(*args, demo=True):
                demo = manifest["run_id"]
            elif operational is None and matching_replenishment(*args, demo=False):
                operational = manifest
            if operational is not None and demo is not None:
                break
    _write_context(
        session,
        job,
        version,
        {
            "replenishment_status": "available" if operational else "insufficient_data",
            "replenishment_reason_code": None if operational else "OPERATIONAL_ROP_NOT_FOUND",
            "replenishment_run_id": operational["run_id"] if operational else None,
            "replenishment_dataset_class": operational["dataset_class"] if operational else None,
            "replenishment_demo_run_id": demo,
        },
    )


def replenishment_reference(snapshot, *, algorithm, lead_time, service, policy, reference_date):
    rows = snapshot["days"].get((algorithm, lead_time, format(service, ".2f"), policy), ())
    for row in rows:
        if row.warmup or (reference_date is not None and row.day != reference_date):
            continue
        rop = row.reorder_point
        if rop is None or not isfinite(rop) or rop < 0:
            continue
        eoq = snapshot["calibration"]["eoq"]
        quantity = eoq.get("quantity")
        if not (type(quantity) is int and quantity > 0 and not eoq.get("reason_code")):
            quantity = None
        return rop, row.day, quantity
    return None


def record_context_failure(session, job, code):
    state = get_key_state(session, job.warehouse_id, job.product_id)
    version = state.row_version if state else None
    if code == "FORECAST_CONTEXT_FAILED":
        fields = {
            "forecast_status": "failed",
            "forecast_reason_code": code,
            "forecast_run_id": None,
            "forecast_dataset_class": None,
            "forecast_stale": None,
        }
    elif code == "REPLENISHMENT_CONTEXT_FAILED":
        fields = {
            "replenishment_status": "failed",
            "replenishment_reason_code": code,
            "replenishment_run_id": None,
            "replenishment_dataset_class": None,
            "replenishment_demo_run_id": None,
        }
    else:
        raise ValueError("Not a context failure")
    _write_context(session, job, version, fields)
