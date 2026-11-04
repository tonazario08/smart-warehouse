from datetime import date
from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from app.analytics.schemas import MAX_DAILY_QUANTITY

Identifier = Annotated[str, Field(min_length=1, max_length=128, pattern=r"^\S(?:.*\S)?$")]
Quantity = Annotated[int, Field(strict=True, ge=0, le=MAX_DAILY_QUANTITY)]
MetricValue = Annotated[float, Field(ge=0, allow_inf_nan=False)]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class Snapshot(Contract):
    category: Identifier | None = None
    supplier: Identifier | None = None
    available_at: AwareDatetime


class SkuInput(Contract):
    bundle_path: str = Field(min_length=1, max_length=80)
    data_version: str = Field(pattern=r"^ddv1-[0-9a-f]{64}$")
    product_key: Identifier
    warehouse_key: Identifier
    unit: Identifier
    split: Literal["train", "validation", "holdout"]
    snapshot: Snapshot


class Partition(Contract):
    name: Literal["train", "validation", "holdout"]
    start: date
    end: date


class ColdStartConfig(Contract):
    skus: tuple[SkuInput, ...] = Field(min_length=1, max_length=64)
    partitions: tuple[Partition, ...]
    created_at: AwareDatetime
    target: Literal["gross_fulfilled_units"] = "gross_fulfilled_units"


class Observation(Contract):
    day: date
    value: Quantity | None
    available_at: AwareDatetime | None


class Series(Contract):
    sku: SkuInput
    observations: tuple[Observation, ...]
    admission_cutoff: AwareDatetime


class ColdStartDataset(Contract):
    config: ColdStartConfig
    series: tuple[Series, ...]
    namespace: Identifier


class Provenance(Contract):
    product_key: Identifier
    split: Literal["train", "validation", "holdout"]
    data_version: str = Field(pattern=r"^ddv1-[0-9a-f]{64}$")
    snapshot: Snapshot
    snapshot_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    admission_cutoff: AwareDatetime


class Prediction(Contract):
    sku: Identifier
    split: Literal["validation", "holdout"]
    origin: date
    horizon: Literal[1, 7]
    prediction: MetricValue | None
    baseline: MetricValue | None
    reference_source: Literal[
        "cluster", "category", "all_train", "insufficient_metadata", "insufficient_references"
    ]
    reference_keys: tuple[Identifier, ...]
    confidence: Literal["cluster", "category", "all_train", "unavailable"]
    reason: Literal["insufficient_metadata", "insufficient_references"] | None = None


class Metrics(Contract):
    samples: int = Field(ge=0)
    predicted: int = Field(ge=0)
    baseline_predicted: int = Field(ge=0)
    actual: int = Field(ge=0)
    compared: int = Field(ge=0)
    excluded_prediction: int = Field(ge=0)
    excluded_baseline: int = Field(ge=0)
    excluded_actual: int = Field(ge=0)
    excluded_comparison: int = Field(ge=0)
    actual_sum: int = Field(ge=0)
    category_count: int = Field(ge=0)
    mae: MetricValue | None
    baseline_mae: MetricValue | None
    wape: MetricValue | None
    baseline_wape: MetricValue | None


class ColdStartReport(Contract):
    schema_version: Literal["cold-start-report/1"] = "cold-start-report/1"
    dataset_class: Literal["fixture"] = "fixture"
    created_at: AwareDatetime
    namespace: Identifier
    target: Literal["gross_fulfilled_units"]
    unit: Identifier
    warehouse_key: Identifier
    train_cutoff: AwareDatetime
    validation_cutoff: AwareDatetime
    provenance: tuple[Provenance, ...]
    partitions: tuple[Partition, ...]
    selected_k: int = Field(ge=1, le=3)
    selection_reason: Literal["validation_common_horizon_7_mae", "no_common_validation_samples"]
    metrics: dict[Literal["1", "7"], Metrics]
    predictions: tuple[Prediction, ...]
    limitations: tuple[str, ...] = (
        "FIXTURE_ONLY",
        "REAL_EVALUATION_NOT_VERIFIED",
        "OPERATIONAL_UNAVAILABLE",
        "CONFIDENCE_IS_QUALITATIVE_NOT_PROBABILISTIC",
        "END_OF_DAY_INCLUDES_NEXT_MIDNIGHT_UTC",
    )
