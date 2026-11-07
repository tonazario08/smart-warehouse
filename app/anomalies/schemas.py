"""Strict bounded contracts for the offline anomaly pipeline."""

from datetime import UTC, date, datetime
from typing import Annotated, Literal

from pydantic import Field, model_validator

from app.analytics.export import _PublicAdmission
from app.analytics.schemas import AwareTime, Checksum, Contract, EventRecord, Identifier

FEATURE_ORDER = (
    "log_quantity",
    "hour_fraction",
    "weekday_fraction",
    "log_prior_quantity_mean_7d",
    "log_prior_event_count_7d",
    "log_quantity_to_prior_mean",
)


class Partition(Contract):
    name: Literal["train", "validation", "final_holdout"]
    start: date
    end: date
    information_cutoff: AwareTime

    @model_validator(mode="after")
    def valid_period(self):
        if (
            self.start < date(1, 1, 8)
            or self.start >= self.end
            or self.information_cutoff < datetime.combine(self.end, datetime.min.time(), UTC)
        ):
            raise ValueError("invalid partition")
        return self


class Label(Contract):
    namespace: Identifier
    product_key: Identifier
    warehouse_key: Identifier
    unit: str = Field(min_length=1, max_length=40)
    event_id: Identifier
    label: Literal["normal", "anomaly"]


class AnomalyConfig(Contract):
    schema_version: Literal["anomaly-config/1"] = "anomaly-config/1"
    data_version: str = Field(pattern=r"^ddv1-[0-9a-f]{64}$")
    allow_fixture: bool = False
    created_at: AwareTime
    seed: Literal[42] = 42
    partitions: tuple[Partition, Partition, Partition]
    labels: tuple[Label, ...] = Field(default=(), max_length=10000)

    @model_validator(mode="after")
    def ordered(self):
        a, b, c = self.partitions
        if (
            (a.name, b.name, c.name) != ("train", "validation", "final_holdout")
            or a.end > b.start
            or b.end > c.start
            or a.information_cutoff > datetime.combine(b.start, datetime.min.time(), UTC)
            or b.information_cutoff > datetime.combine(c.start, datetime.min.time(), UTC)
            or c.information_cutoff > self.created_at
        ):
            raise ValueError("invalid partition ordering or cutoff")
        keys = [
            (x.namespace, x.product_key, x.warehouse_key, x.unit, x.event_id) for x in self.labels
        ]
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate label")
        return self


class AnomalyDataset(Contract):
    config: AnomalyConfig
    admission: _PublicAdmission
    events: tuple[EventRecord, ...] = Field(max_length=10000)
    source_hashes: dict[str, Checksum]


class Sample(Contract):
    source_record_key: str = Field(pattern=r"^aek1-[0-9a-f]{64}$")
    event_id: Identifier
    partition: Literal["train", "validation", "final_holdout"]
    occurred_at: AwareTime
    available_at: AwareTime
    values: tuple[float, float, float, float, float, float]
    label: Literal["normal", "anomaly"] | None = None


class FeatureSnapshot(Contract):
    schema_version: Literal["anomaly-features/1"] = "anomaly-features/1"
    feature_order: tuple[str, ...] = FEATURE_ORDER
    config: AnomalyConfig
    source_hashes: dict[str, Checksum]
    samples: tuple[Sample, ...] = Field(max_length=2816)
    exclusions: dict[Identifier, Annotated[int, Field(ge=0, le=10000)]]

    @model_validator(mode="after")
    def order(self):
        import math

        if self.feature_order != FEATURE_ORDER or any(
            not math.isfinite(v) for s in self.samples for v in s.values
        ):
            raise ValueError("invalid feature values or order")
        keys = [(s.occurred_at, s.source_record_key) for s in self.samples]
        if keys != sorted(keys) or len({s.source_record_key for s in self.samples}) != len(keys):
            raise ValueError("samples must have unique keys and canonical order")
        for sample in self.samples:
            if any(v < 0 for v in sample.values) or sample.values[1] > 1 or sample.values[2] > 1:
                raise ValueError("invalid feature range")
            part = next(p for p in self.config.partitions if p.name == sample.partition)
            if not (
                part.start <= sample.occurred_at.astimezone(UTC).date() < part.end
                and sample.occurred_at <= sample.available_at <= part.information_cutoff
            ):
                raise ValueError("sample outside temporal boundary")
        for name, limit in (("train", 2048), ("validation", 512), ("final_holdout", 256)):
            if sum(s.partition == name for s in self.samples) > limit:
                raise ValueError("partition limit exceeded")
        return self
