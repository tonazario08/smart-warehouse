"""Strict contracts for verified forecasting inputs and temporal windows."""

import math
from datetime import UTC, date, datetime, timedelta
from typing import Annotated, Literal

from pydantic import Field, model_validator

from app.analytics.schemas import (
    AwareTime,
    Contract,
    Identifier,
    PipelineError,
    Unit,
    business_day_bounds,
    load_timezone,
)

Quantity = Annotated[int | float, Field(ge=0, allow_inf_nan=False)]


class Partition(Contract):
    name: Literal["train", "validation", "final_holdout"]
    start: date
    end: date

    @model_validator(mode="after")
    def valid_interval(self):
        if self.start >= self.end:
            raise ValueError("empty partition")
        return self


class ForecastProtocol(Contract):
    schema_version: Literal["forecast-protocol/1"]
    partitions: tuple[Partition, ...]
    horizons: tuple[int, ...]
    history_days: int = Field(ge=28, le=28)
    imputation: Literal["none"]
    train_information_cutoff: AwareTime | None = None
    selection_information_cutoff: AwareTime | None = None
    refit_information_cutoff: AwareTime | None = None


class ModelConfig(Contract):
    max_depth: int = Field(ge=2, le=3)
    booster: Literal["gbtree"] = "gbtree"
    objective: Literal["reg:squarederror"] = "reg:squarederror"
    tree_method: Literal["hist"] = "hist"
    device: Literal["cpu"] = "cpu"
    eta: float = 0.05
    min_child_weight: int = 1
    subsample: int = 1
    colsample_bytree: int = 1
    reg_lambda: int = 1
    alpha: int = 0
    seed: int = 42
    nthread: int = 1
    verbosity: int = 0
    num_boost_round: int = 100

    @model_validator(mode="after")
    def fixed(self):
        if (
            self.eta,
            self.min_child_weight,
            self.subsample,
            self.colsample_bytree,
            self.reg_lambda,
            self.alpha,
            self.seed,
            self.nthread,
            self.verbosity,
            self.num_boost_round,
        ) != (0.05, 1, 1, 1, 1, 0, 42, 1, 0, 100):
            raise ValueError("candidate parameters are frozen")
        return self


class OperationalBinding(Contract):
    schema_version: Literal["forecast-binding/1"]
    data_version: str
    product_key: Identifier
    warehouse_key: Identifier
    product_id: int = Field(gt=0)
    warehouse_id: int = Field(gt=0)
    unit: Unit
    approved_at: AwareTime
    available_at: AwareTime
    permission_ref: Identifier


class ForecastConfig(Contract):
    schema_version: Literal["forecast-config/1"]
    mode: Literal["research", "operational"]
    dataset_class: Literal["research", "fixture"]
    data_version: str = Field(pattern=r"^ddv[12]-[0-9a-f]{64}$")
    target: Literal["reported_daily_unit_sales", "gross_fulfilled_units"]
    reporting_scope: Literal["company_aggregate", "warehouse"]
    unit: Unit
    feature_version: Literal["lag-calendar/1"]
    knowledge_time_mode: Literal["retrospective_final_vintage", "historical_as_of"]
    protocol: ForecastProtocol
    candidates: tuple[ModelConfig, ...]
    binding: OperationalBinding | None = None
    business_timezone: str | None = None

    @property
    def partitions(self):
        return self.protocol.partitions

    @property
    def horizons(self):
        return self.protocol.horizons

    @model_validator(mode="after")
    def coherent(self):
        if tuple(c.max_depth for c in self.candidates) != (2, 3):
            raise ValueError("ordered frozen candidates required")
        if tuple(p.name for p in self.partitions) != ("train", "validation", "final_holdout"):
            raise ValueError("ordered train, validation and final_holdout partitions required")
        if any(a.end > b.start for a, b in zip(self.partitions, self.partitions[1:], strict=False)):
            raise ValueError("partitions overlap or are unordered")
        if (
            not self.horizons
            or len(set(self.horizons)) != len(self.horizons)
            or any(h not in (1, 7) for h in self.horizons)
        ):
            raise ValueError("unsupported horizons")
        if self.mode == "research":
            expected = tuple(
                (n, date(y, 1, 1), date(y + 1, 1, 1))
                for n, y in (("train", 2020), ("validation", 2021), ("final_holdout", 2022))
            )
            if (
                (self.target, self.reporting_scope, self.knowledge_time_mode)
                != ("reported_daily_unit_sales", "company_aggregate", "retrospective_final_vintage")
                or tuple((p.name, p.start, p.end) for p in self.partitions) != expected
                or (
                    self.horizons != (1, 7)
                    or self.binding is not None
                    or self.business_timezone is not None
                    or any(
                        (
                            self.protocol.train_information_cutoff,
                            self.protocol.selection_information_cutoff,
                            self.protocol.refit_information_cutoff,
                        )
                    )
                )
            ):
                raise ValueError("invalid research contract")
        elif (
            (self.target, self.reporting_scope, self.knowledge_time_mode)
            != ("gross_fulfilled_units", "warehouse", "historical_as_of")
            or self.binding is None
            or self.business_timezone is None
            or (self.binding.data_version != self.data_version or self.binding.unit != self.unit)
        ):
            raise ValueError("invalid operational contract")
        else:
            try:
                load_timezone(self.business_timezone)
                train = self.protocol.train_information_cutoff
                selection = self.protocol.selection_information_cutoff
                refit = self.protocol.refit_information_cutoff
                if (
                    not train
                    or not selection
                    or not refit
                    or any(
                        cutoff.utcoffset() != timedelta(0) for cutoff in (train, selection, refit)
                    )
                    or not train <= selection <= refit
                ):
                    raise ValueError("ordered UTC cutoffs required")
                validation_bound = business_day_bounds(
                    self.partitions[1].start - timedelta(days=1), self.business_timezone
                )[1].astimezone(UTC)
                holdout_bound = business_day_bounds(
                    self.partitions[2].start - timedelta(days=1), self.business_timezone
                )[1].astimezone(UTC)
                if train > validation_bound or selection > holdout_bound or refit > holdout_bound:
                    raise ValueError("cutoff exceeds partition boundary")
            except PipelineError:
                raise ValueError("invalid business timezone") from None
        return self


class Observation(Contract):
    day: date
    value: Quantity | None
    available_at: datetime | None

    @model_validator(mode="after")
    def aware(self):
        if self.available_at is not None and self.available_at.utcoffset() is None:
            raise ValueError("aware availability required")
        return self


class ForecastDataset(Contract):
    config: ForecastConfig
    series_key: Identifier
    observations: tuple[Observation, ...]
    limitations: tuple[str, ...]
    knowledge_bound: AwareTime | None = None
    admission_cutoff: AwareTime | None = None

    @model_validator(mode="after")
    def ordered(self):
        if len(self.observations) > 10000 or any(
            a.day >= b.day for a, b in zip(self.observations, self.observations[1:], strict=False)
        ):
            raise ValueError("ordered unique bounded calendar required")
        return self


class ForecastOrigin(Contract):
    series_key: Identifier
    origin: date
    history_dates: tuple[date, ...]
    history_values: tuple[Quantity, ...]
    target_dates: tuple[date, ...]

    @model_validator(mode="after")
    def aligned(self):
        if (
            len(self.history_dates) != 28
            or len(self.history_values) != 28
            or len(self.target_dates) not in (1, 7)
            or self.history_dates
            != tuple(self.origin - timedelta(days=i) for i in range(27, -1, -1))
            or (
                self.target_dates
                != tuple(
                    self.origin + timedelta(days=i) for i in range(1, len(self.target_dates) + 1)
                )
            )
            or any(type(v) is float and not math.isfinite(v) for v in self.history_values)
        ):
            raise ValueError("invalid origin")
        return self


class ForecastWindow(ForecastOrigin):
    target_values: tuple[Quantity, ...]

    @model_validator(mode="after")
    def labels(self):
        if len(self.target_values) != len(self.target_dates) or any(
            type(v) is float and not math.isfinite(v) for v in self.target_values
        ):
            raise ValueError("invalid targets")
        return self


class PredictionRow(Contract):
    series_key: Identifier
    origin: date
    target_date: date
    lead: int = Field(ge=1, le=7)
    horizon: int
    algorithm: Literal["persistence", "seasonal_naive", "xgboost"]
    prediction: Quantity
    actual: Quantity | None
    unit: Unit

    @model_validator(mode="after")
    def aligned(self):
        if (
            self.horizon not in (1, 7)
            or self.lead > self.horizon
            or (self.target_date != self.origin + timedelta(days=self.lead))
        ):
            raise ValueError("invalid prediction dates")
        return self


class MetricReport(Contract):
    count: int = Field(ge=0)
    origin_count: int = Field(ge=0)
    mae: float | None
    wape: float | None
    origin_total_mae: float | None
    reason: Literal["NO_ELIGIBLE_WINDOWS"] | None = None
    wape_reason: Literal["ZERO_ACTUAL_TOTAL"] | None = None
    per_series: dict[str, tuple[int, float, float | None]] = {}


class SelectionResult(Contract):
    data_version: str
    config_sha256: str
    software_sha256: str
    train_hashes: dict[int, str]
    validation_hashes: dict[int, str]
    candidates: dict[int, ModelConfig]
    validation_metrics: dict[int, MetricReport]
    candidate_metrics: dict[str, MetricReport]
    candidate_clips: dict[str, int]
    candidate_error: dict[str, tuple[int, int]]
    selection_through: date
    knowledge_bound: AwareTime | None
    admission_cutoff: AwareTime | None


class EvaluationResult(Contract):
    rows: tuple[PredictionRow, ...]
    metrics: dict[str, MetricReport]
    exclusions: dict[int, int]
    clips: int
    trained_through: date
    refit_window_hashes: dict[int, str]
    training_information_cutoff: AwareTime | None
    knowledge_bound: AwareTime | None
    admission_cutoff: AwareTime | None


class ForecastResult(Contract):
    rows: tuple[PredictionRow, ...]
    clips: int
    trained_through: date
    refit_window_hashes: dict[int, str]
    training_information_cutoff: AwareTime
