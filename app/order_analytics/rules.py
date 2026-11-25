"""Deterministic provisional B2B quantity check, separate from model alerts."""

from collections.abc import Sequence
from dataclasses import asdict, dataclass
from statistics import median

RULE_ID = "b2b_quantity_robust_zscore"
RULE_VERSION = 1
LABEL = "Kiểm tra đơn tạm tính"
HISTORY_DAYS = 180
MIN_SAMPLES = 8
Z_THRESHOLD = 3.5
ZERO_MAD_RATIO = 3


@dataclass(frozen=True)
class QuantityCheck:
    status: str
    flagged: bool | None
    reason_code: str | None
    sample_count: int
    median: float | None = None
    mad: float | None = None
    score: float | None = None
    rule_id: str = RULE_ID
    rule_version: int = RULE_VERSION
    label: str = LABEL

    def as_fields(self):
        return asdict(self)


def check_quantity(quantity: int, history: Sequence[int]) -> QuantityCheck:
    if len(history) < MIN_SAMPLES:
        return QuantityCheck("insufficient_data", None, "INSUFFICIENT_HISTORY", len(history))

    center = float(median(history))
    mad = float(median([abs(value - center) for value in history]))
    score = None
    if mad:
        score = 0.6745 * (quantity - center) / mad
        high, low = score > Z_THRESHOLD, score < -Z_THRESHOLD
    else:
        high, low = quantity >= ZERO_MAD_RATIO * center, ZERO_MAD_RATIO * quantity <= center
    reason = "QUANTITY_HIGH" if high else "QUANTITY_LOW" if low else None
    return QuantityCheck("available", reason is not None, reason, len(history), center, mad, score)
