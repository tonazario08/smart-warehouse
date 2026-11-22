"""Read-only, fixture-only proof that the same historical forecast underlies M7 ROP."""

import re
from datetime import date, datetime, timedelta
from decimal import ROUND_CEILING, Decimal
from typing import Literal

from pydantic import BaseModel

from app.auth.dependencies import PERMISSION_ROLES, Permission
from app.core.errors import DomainError
from app.forecasting.repository import ForecastRepository
from app.models import Product, Warehouse
from app.replenishment.repository import ReplenishmentRepository

ALGORITHM = "xgboost"
LEAD_TIME = 7
SERVICE = "0.90"
POLICY = "proposed"
FIXTURE = "M7-E2E-SYNTHETIC"
CASE = (ALGORITHM, LEAD_TIME, SERVICE, POLICY)
Reason = Literal["SOURCE_UNAVAILABLE", "ARTIFACT_MISMATCH", "FIXTURE_BINDING_UNAVAILABLE"]


class PilotEvidence(BaseModel):
    forecast_run_id: str
    replenishment_run_id: str
    product_id: int
    warehouse_id: int
    sku: str
    warehouse_code: str
    unit: Literal["unit"]
    data_version: str
    algorithm: Literal["xgboost"] = ALGORITHM
    lead_time: Literal[7] = LEAD_TIME
    service_level: Literal["0.90"] = SERVICE
    policy: Literal["proposed"] = POLICY
    training_cutoff: datetime
    origin: date
    scenario_day: date
    forecast_during_lead_time: str
    safety_stock: str
    rop: int
    simulated_inventory_position: int
    threshold: Literal["at_or_below", "above"]
    eoq: int | None
    holdout_wape: str | None
    holdout_lead_time_mae: str | None


class ForecastPilotRead(BaseModel):
    state: Literal["ready", "unavailable"]
    reason_code: Reason | None = None
    pilot: PilotEvidence | None = None


def threshold(position, rop):
    return "at_or_below" if position <= rop else "above"


def _missing(reason: Reason) -> ForecastPilotRead:
    return ForecastPilotRead(state="unavailable", reason_code=reason)


def _not_found():
    return DomainError(404, "REPLENISHMENT_PILOT_NOT_FOUND", "Pilot not found.")


def _quantity(value) -> Decimal:
    result = Decimal(str(value))
    if not result.is_finite() or result < 0:
        raise ValueError("invalid pilot measurement")
    return result


def _number(value) -> str:
    return format(_quantity(value).normalize(), "f")


def _metric(metrics, name):
    value = metrics.get(name)
    return None if value is None else _number(value)


def _integer_eoq(artifact):
    quantity = artifact.get("quantity")
    return (
        quantity
        if artifact.get("state") == "ready"
        and artifact.get("reason_code") is None
        and type(quantity) is int
        and quantity > 0
        else None
    )


def read_forecast_pilot(actor, run_id, settings, session) -> ForecastPilotRead:
    if any(actor.role not in PERMISSION_ROLES[p] for p in (
        Permission.REPLENISHMENT_READ, Permission.FORECAST_READ,
    )):
        raise DomainError(403, "REPLENISHMENT_FORBIDDEN", "Permission denied.")
    if not (
        settings.app_env in ("test", "integration")
        and settings.forecast_allow_fixture
        and settings.replenishment_allow_fixture
    ):
        raise _not_found()

    policies = ReplenishmentRepository(settings.replenishment_catalog_root, allow_fixture=True)
    forecasts = ForecastRepository(settings.forecast_catalog_root, allow_fixture=True)
    try:
        snapshot = policies.scoped(run_id, ("operational",))
        if snapshot is None:
            raise _not_found()
        policy = snapshot["manifest"]
        if (
            policy["run_id"] != run_id
            or (policy["mode"], policy["dataset_class"], policy["applicability"])
            != ("operational", "fixture", "fixture_scenario")
            or (policy["target"], policy["reporting_scope"], policy["unit"])
            != ("gross_fulfilled_units", "warehouse", "unit")
        ):
            return _missing("ARTIFACT_MISMATCH")

        config = policy["config"]
        upstream_id = policy["forecast_run_id"]
        expected_sha = config["public_manifest_sha256"]
        if (
            not re.fullmatch(r"frv1-[0-9a-f]{64}", upstream_id)
            or not re.fullmatch(r"[0-9a-f]{64}", expected_sha)
        ):
            return _missing("ARTIFACT_MISMATCH")
        forecast = forecasts.get_scoped(
            upstream_id, ("operational",), expected_public_manifest_sha256=expected_sha,
        )
        if forecast is None:
            return _missing("SOURCE_UNAVAILABLE")
        manifest, binding = forecast.manifest, forecast.binding
        if (
            (manifest.mode, manifest.dataset_class, manifest.kind, manifest.knowledge_time_mode)
            != ("operational", "fixture", "evaluation", "historical_as_of")
            or (manifest.target, manifest.reporting_scope, manifest.unit)
            != (policy["target"], policy["reporting_scope"], policy["unit"])
            or manifest.run_id != upstream_id
            or manifest.data_version != policy["data_version"]
            or manifest.source_manifest_sha256 != config["source_manifest_sha256"]
            or manifest.business_timezone != policy["source_business_timezone"]
            or LEAD_TIME not in manifest.horizons
            or binding is None
            or binding.model_dump(mode="json") != policy["binding"]
            or binding.data_version != manifest.data_version
        ):
            return _missing("ARTIFACT_MISMATCH")
        for key in ("training_information_cutoff", "admission_cutoff", "knowledge_bound"):
            value = getattr(manifest, key)
            if policy[key] != (value.isoformat() if value else None):
                return _missing("ARTIFACT_MISMATCH")
        cutoff = manifest.training_information_cutoff
        day = next((row for row in snapshot["days"][CASE] if not row.warmup), None)
        if cutoff is None or day is None or day.origin + timedelta(days=1) != day.day:
            return _missing("ARTIFACT_MISMATCH")
        rows = [
            row for row in forecast.rows
            if (row.algorithm, row.horizon, row.origin) == (ALGORITHM, LEAD_TIME, day.origin)
        ]
        if (
            [row.lead for row in rows] != list(range(1, LEAD_TIME + 1))
            or len({row.series_key for row in rows}) != 1
            or any(row.unit != policy["unit"] for row in rows)
        ):
            return _missing("ARTIFACT_MISMATCH")
        mean = sum((_quantity(row.prediction) for row in rows), Decimal(0))
        safety = _quantity(day.safety_stock)
        if (
            mean != day.forecast_mean
            or day.reorder_point != int((mean + safety).to_integral_value(rounding=ROUND_CEILING))
            or day.position < 0
        ):
            return _missing("ARTIFACT_MISMATCH")
        eoq = _integer_eoq(snapshot["calibration"]["eoq"])
        metrics = (forecast.metrics or {}).get(f"{ALGORITHM}:{LEAD_TIME}", {})
        wape = _metric(metrics, "wape")
        lead_mae = _metric(metrics, "origin_total_mae")
    except (FileNotFoundError, OSError):
        return _missing("SOURCE_UNAVAILABLE")
    except (KeyError, TypeError, ValueError, ArithmeticError, OverflowError):
        return _missing("ARTIFACT_MISMATCH")

    if (binding.product_id, binding.warehouse_id) != (2, 2):
        return _missing("FIXTURE_BINDING_UNAVAILABLE")
    product = session.get(Product, binding.product_id)
    warehouse = session.get(Warehouse, binding.warehouse_id)
    if (
        product is None or warehouse is None or not product.is_active
        or product.unit != binding.unit or product.sku != FIXTURE or warehouse.code != FIXTURE
    ):
        return _missing("FIXTURE_BINDING_UNAVAILABLE")

    return ForecastPilotRead(
        state="ready",
        pilot=PilotEvidence(
            forecast_run_id=manifest.run_id,
            replenishment_run_id=run_id,
            product_id=product.id,
            warehouse_id=warehouse.id,
            sku=product.sku,
            warehouse_code=warehouse.code,
            unit=product.unit,
            data_version=manifest.data_version,
            training_cutoff=cutoff,
            origin=day.origin,
            scenario_day=day.day,
            forecast_during_lead_time=_number(mean),
            safety_stock=_number(safety),
            rop=day.reorder_point,
            simulated_inventory_position=day.position,
            threshold=threshold(day.position, day.reorder_point),
            eoq=eoq,
            holdout_wape=wape,
            holdout_lead_time_mae=lead_mae,
        ),
    )
