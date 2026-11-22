"""Narrow, validated operational inference result; not an M9 fixture alert."""

import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

UnavailableReason = Literal[
    "NO_APPROVED_MODEL",
    "MODEL_ARTIFACT_INVALID",
    "INSUFFICIENT_DATA",
    "LINEAGE_INVALID",
    "EXPLANATION_UNAVAILABLE",
]
FeatureVector = tuple[float, float, float, float, float, float]


class OperationalResult(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    state: Literal["unavailable", "normal", "flagged"]
    reason_code: UnavailableReason | None = None
    score: float | None = None
    threshold: float | None = None
    model_version: str | None = None
    feature_version: str | None = None
    base_value: float | None = None
    contributions: FeatureVector | None = None
    input_fingerprint: str | None = None
    dataset_class: Literal["operational", "synthetic_test"] | None = None

    @model_validator(mode="after")
    def valid_result(self):
        if self.state == "unavailable":
            if self.reason_code is None or any(
                value is not None
                for value in (
                    self.score,
                    self.threshold,
                    self.model_version,
                    self.feature_version,
                    self.base_value,
                    self.contributions,
                    self.input_fingerprint,
                    self.dataset_class,
                )
            ):
                raise ValueError("unavailable results cannot carry an inference")
            return self
        if (
            self.reason_code is not None
            or self.score is None
            or self.threshold is None
            or not all(math.isfinite(x) and 0 <= x <= 1 for x in (self.score, self.threshold))
            or (self.score > self.threshold) != (self.state == "flagged")
            or not self.input_fingerprint
            or self.dataset_class is None
            or not self.model_version
            or not self.feature_version
        ):
            raise ValueError("invalid operational scoring result")
        if self.state == "normal":
            if self.base_value is not None or self.contributions is not None:
                raise ValueError("normal results cannot carry an alert explanation")
        elif (
            self.base_value is None
            or self.contributions is None
            or not all(math.isfinite(x) for x in (self.base_value, *self.contributions))
            or abs(self.base_value + sum(self.contributions) - self.score) > 1e-8
        ):
            raise ValueError("flagged results require a matching explanation")
        return self
