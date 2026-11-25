"""Strict replenishment source authorization and study contracts."""

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from app.analytics.schemas import Checksum, Contract, Identifier, Unit
from app.forecasting.repository import PublicRun
from app.forecasting.schemas import Observation


class InputAuthorization(Contract):
    schema_version: Literal["replenishment-input-authorization/1"]
    mode: Literal["research", "operational"]
    dataset_class: Literal["research", "fixture"]
    approved_bundle_root: Path
    bundle_path: Path
    bundle_hashes: dict[str, Checksum]
    approved_forecast_root: Path
    forecast_dir: Path
    public_manifest_sha256: Checksum
    source_manifest_sha256: Checksum
    forecast_run_id: str = Field(pattern=r"^frv1-[0-9a-f]{64}$")
    allow_fixture: bool
    expected_fixture_binding: tuple[int, int, str] | None = None

    @model_validator(mode="after")
    def coherent(self):
        if set(self.bundle_hashes) != {
            "manifest.json",
            "observations.jsonl",
            "quality.json",
            "records.jsonl",
        }:
            raise ValueError("exact bundle hashes required")
        if self.allow_fixture != (self.dataset_class == "fixture"):
            raise ValueError("fixture authorization mismatch")
        if self.mode == "operational" and self.dataset_class != "fixture":
            raise ValueError("operational source not admitted")
        if self.mode == "operational" and self.expected_fixture_binding is None:
            raise ValueError("fixture binding required")
        if self.expected_fixture_binding is not None and (
            self.dataset_class != "fixture"
            or self.mode != "operational"
            or min(self.expected_fixture_binding[:2]) <= 0
        ):
            raise ValueError("invalid fixture binding")
        return self


class CostInputs(Contract):
    ordering_cost: Decimal | None
    holding_cost: Decimal | None
    currency: Literal["VND"]
    holding_period: Literal["year"]

    @model_validator(mode="after")
    def valid_costs(self):
        if any(
            value is not None and (not value.is_finite() or value < 0)
            for value in (self.ordering_cost, self.holding_cost)
        ):
            raise ValueError("invalid costs")
        return self


class SupplyOrder(Contract):
    order_id: Identifier
    quantity: int = Field(gt=0)
    unit: Unit
    ordered_at: datetime
    known_at: datetime
    due_date: date

    @model_validator(mode="after")
    def aware(self):
        if self.ordered_at.utcoffset() is None or self.known_at.utcoffset() is None:
            raise ValueError("aware order times required")
        if self.known_at < self.ordered_at:
            raise ValueError("supply cannot be known before the order")
        return self


class StudyConfig(Contract):
    schema_version: Literal["replenishment-study/1"]
    mode: Literal["research", "operational"]
    dataset_class: Literal["research", "fixture"]
    target: Literal["reported_daily_unit_sales", "gross_fulfilled_units"]
    reporting_scope: Literal["company_aggregate", "warehouse"]
    unit: Unit
    data_version: str = Field(pattern=r"^ddv[12]-[0-9a-f]{64}$")
    forecast_run_id: str = Field(pattern=r"^frv1-[0-9a-f]{64}$")
    source_manifest_sha256: Checksum
    public_manifest_sha256: Checksum
    calibration_start: date
    calibration_end: date
    evaluation_start: date
    evaluation_end: date
    nominal_coverage: Decimal
    service_probabilities: tuple[Decimal, ...]
    minimum_samples: int = Field(ge=30)
    lead_times: tuple[int, ...]
    warmup_days: int = Field(ge=0)
    costs: CostInputs
    initial_on_hand: int = Field(ge=0)
    initial_pipeline: tuple[SupplyOrder, ...]
    reservations: int | None = Field(ge=0)
    backlog: int | None = Field(ge=0)
    temporal_availability_convention: str = Field(min_length=1, max_length=256)
    disclosures: tuple[str, ...] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def coherent(self):
        if not (
            self.calibration_start
            < self.calibration_end
            <= self.evaluation_start
            < self.evaluation_end
        ):
            raise ValueError("invalid temporal partitions")
        if self.lead_times != (1, 7) or self.service_probabilities != (
            Decimal(".80"),
            Decimal(".90"),
            Decimal(".95"),
        ):
            raise ValueError("unsupported study protocol")
        if self.nominal_coverage != Decimal(".90"):
            raise ValueError("unsupported coverage")
        if self.mode == "research" and (self.target, self.reporting_scope) != (
            "reported_daily_unit_sales",
            "company_aggregate",
        ):
            raise ValueError("invalid research scope")
        if self.mode == "operational" and (self.target, self.reporting_scope) != (
            "gross_fulfilled_units",
            "warehouse",
        ):
            raise ValueError("invalid operational scope")
        return self


class StudyInputs(Contract):
    forecast: PublicRun
    observations: tuple[Observation, ...]
    config: StudyConfig


class EoqResult(Contract):
    state: Literal["ready", "unavailable"]
    reason_code: str | None
    raw: Decimal | None
    quantity: int | None

    @model_validator(mode="after")
    def coherent(self):
        if self.state == "ready":
            if (
                self.raw is None
                or not self.raw.is_finite()
                or self.raw < 0
                or self.quantity is None
                or self.quantity < 0
            ):
                raise ValueError("invalid ready EOQ")
            from decimal import ROUND_CEILING

            if self.quantity != int(self.raw.to_integral_value(rounding=ROUND_CEILING)):
                raise ValueError("invalid rounded EOQ")
            if (self.raw == 0) != (self.reason_code == "ZERO_DEMAND"):
                raise ValueError("invalid zero demand reason")
            if self.raw > 0 and self.reason_code is not None:
                raise ValueError("unexpected EOQ reason")
        elif self.raw is not None or self.quantity is not None or not self.reason_code:
            raise ValueError("invalid unavailable EOQ")
        return self


class PolicyDecision(Contract):
    state: Literal["ready", "unavailable"]
    reason_code: str | None
    safety_stock: Decimal | None
    reorder_point: int | None
    order_quantity: int | None


class IntervalResult(Contract):
    lower: Decimal
    upper: Decimal
    covered: bool
    width: Decimal
    interval_score: Decimal
    lower_pinball: Decimal
    upper_pinball: Decimal


class CalibrationWindow(Contract):
    origin: date
    target_end: date
    residual: Decimal


class CalibrationEntry(Contract):
    algorithm: Literal["persistence", "seasonal_naive", "xgboost"]
    horizon: Literal[1, 7]
    windows: tuple[CalibrationWindow, ...]
    quantiles: dict[str, Decimal]


class CalibrationSet(Contract):
    entries: tuple[CalibrationEntry, ...]
    annual_demand: Decimal
    annual_demand_dates: tuple[date, ...]
    calibration_start: date
    calibration_end: date
    evaluation_start: date
    evaluation_end: date
    knowledge_convention: str


class IntervalMetrics(Contract):
    algorithm: Literal["persistence", "seasonal_naive", "xgboost"]
    horizon: Literal[1, 7]
    subset: Literal["all", "monday"]
    origins: tuple[date, ...]
    count: int = Field(ge=0)
    reason_code: Literal["NO_EVALUATION_WINDOWS"] | None
    coverage: Decimal | None
    mean_width: Decimal | None
    mean_interval_score: Decimal | None
    pinball: dict[str, Decimal | None]

    @model_validator(mode="after")
    def coherent(self):
        values = (self.coverage, self.mean_width, self.mean_interval_score, *self.pinball.values())
        if len(self.origins) != self.count or len(set(self.origins)) != self.count:
            raise ValueError("origin count mismatch")
        if set(self.pinball) != {"0.05", "0.80", "0.90", "0.95"}:
            raise ValueError("pinball probabilities mismatch")
        if self.count == 0:
            if self.reason_code != "NO_EVALUATION_WINDOWS" or any(v is not None for v in values):
                raise ValueError("empty metrics require an explicit reason")
        elif self.reason_code is not None or any(v is None for v in values):
            raise ValueError("populated metrics require values without a reason")
        return self


class SimulationOrder(Contract):
    order_id: str
    ordered_on: date
    due_date: date
    quantity: int = Field(gt=0)


class SimulationDay(Contract):
    day: date
    origin: date
    warmup: bool
    opening_on_hand: int
    received: int
    received_order_ids: tuple[str, ...]
    position: int
    forecast_mean: Decimal
    residual_quantile: Decimal
    safety_stock: Decimal
    reorder_point: int
    order_quantity: int
    ordered: int
    order_id: str | None
    due_date: date | None
    demand: int
    fulfilled: int
    lost: int
    on_hand_end: int
    pipeline_end: int
    ordering_cost: Decimal
    holding_cost: Decimal


class TrajectorySummary(Contract):
    scored_days: int
    scored_opening_on_hand: int
    scored_opening_pipeline: int
    closing_on_hand: int
    terminal_pipeline: int
    demand: int
    fulfilled: int
    lost: int
    fill_rate: Decimal | None
    fill_reason: Literal["ZERO_DEMAND"] | None
    day_service: Decimal | None
    day_service_reason: Literal["NO_POSITIVE_DEMAND_DAYS"] | None
    stockout_days: int
    average_on_hand: Decimal
    order_count: int
    receipt_count: int
    ordering_cost: Decimal
    holding_cost: Decimal
    partial_cost: Decimal
    warmup_demand: int
    warmup_fulfilled: int
    warmup_lost: int
    warmup_ordering_cost: Decimal
    warmup_holding_cost: Decimal
    cycle_service: None
    cycle_service_reason: Literal["OVERLAPPING_CYCLES_UNSUPPORTED"]


class SimulationTrajectory(Contract):
    algorithm: Literal["persistence", "seasonal_naive", "xgboost"]
    horizon: Literal[1, 7]
    service: Decimal
    policy: Literal["baseline", "proposed"]
    initial_on_hand: int
    initial_pipeline: tuple[SupplyOrder, ...]
    days: tuple[SimulationDay, ...]
    orders: tuple[SimulationOrder, ...]
    summary: TrajectorySummary


class StudyResult(Contract):
    schema_version: Literal["replenishment-result/1"]
    config: StudyConfig
    calibration: CalibrationSet
    eoq: EoqResult
    interval_metrics: tuple[IntervalMetrics, ...]
    trajectories: tuple[SimulationTrajectory, ...]
    data_version: str
    forecast_run_id: str
    source_manifest_sha256: Checksum
    public_manifest_sha256: Checksum
    source_business_timezone: str | None
    scenario_clock_timezone: str
    scenario_clock_convention: str


class ReplenishmentFailureReceipt(Contract):
    schema_version: Literal["replenishment-failure/1"]
    attempt_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    mode: Literal["research", "operational"]
    dataset_class: Literal["research", "fixture"]
    config_sha256: Checksum
    created_at: datetime
    reason_code: Literal[
        "FORECAST_STALE",
        "CALENDAR_UNAVAILABLE",
        "NO_EVALUATION_WINDOWS",
        "UNSUPPORTED_INVENTORY_STATE",
        "INSUFFICIENT_CALIBRATION",
        "ORDERING_COST_MISSING",
        "ORDERING_COST_ZERO",
        "HOLDING_COST_MISSING",
        "HOLDING_COST_ZERO",
    ]

    @model_validator(mode="after")
    def coherent(self):
        from datetime import timedelta

        if self.created_at.utcoffset() != timedelta(0):
            raise ValueError("UTC receipt time required")
        if self.mode == "operational" and self.dataset_class != "fixture":
            raise ValueError("operational source not admitted")
        return self
