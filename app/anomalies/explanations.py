"""Exact SHAP attribution of the displayed anomaly score."""

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Explanation:
    state: str
    reason: str | None = None
    base_value: float | None = None
    contributions: tuple[float, ...] | None = None
    score: float | None = None
    residual: float | None = None
    assumptions: str = "Independent masking; synthetic fixture; attribution is not causal."


def explain(result, index: int) -> Explanation:
    if result.state != "available":
        return Explanation("unavailable", "MODEL_UNAVAILABLE")
    if not 0 <= index < len(result.snapshot.samples):
        raise IndexError(index)
    try:
        import numpy as np
        import shap
    except ImportError:
        return Explanation("unavailable", "EXPLAINER_MISSING")
    try:
        masker = shap.maskers.Independent(np.asarray(result.background), max_samples=16)
        explainer = shap.ExactExplainer(lambda x: -result.model.score_samples(x), masker)
        output = explainer(np.asarray([result.snapshot.samples[index].values]), max_evals=64)
        base = float(output.base_values[0])
        contributions = tuple(float(x) for x in output.values[0])
        score = result.scores[index]
        residual = abs(base + sum(contributions) - score)
        if (
            len(contributions) != 6
            or not all(math.isfinite(v) for v in (base, score, residual, *contributions))
            or residual > 1e-8
        ):
            return Explanation("unavailable", "ADDITIVITY_MISMATCH")
        return Explanation(
            "available",
            base_value=base,
            contributions=contributions,
            score=score,
            residual=residual,
        )
    except Exception:
        return Explanation("unavailable", "EXPLAINER_ERROR")
