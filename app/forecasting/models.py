"""Offline direct native XGBoost models, one per forecast lead."""

from dataclasses import dataclass
from datetime import date, timedelta

from app.forecasting.features import feature_vector
from app.forecasting.schemas import ForecastWindow, ModelConfig


@dataclass
class DirectModels:
    candidate: ModelConfig
    boosters: list
    array_dtype: str = "float32"


def _matrix(values, *, labels=None):
    import numpy as np
    import xgboost as xgb

    try:
        with np.errstate(over="ignore", invalid="ignore"):
            array = np.asarray(values, dtype=np.float32)
            y = np.asarray(labels, dtype=np.float32) if labels is not None else None
        if not np.isfinite(array).all() or (y is not None and not np.isfinite(y).all()):
            raise ValueError("model array must be finite")
        return xgb.DMatrix(array, label=y, nthread=1)
    except (OverflowError, TypeError, FloatingPointError):
        raise ValueError("model array must be finite") from None


def fit_direct(windows: tuple[ForecastWindow, ...], candidate: ModelConfig) -> DirectModels:
    import xgboost as xgb

    if not windows or not isinstance(candidate, ModelConfig):
        raise ValueError("training windows and candidate required")
    candidate = ModelConfig.model_validate(candidate.model_dump())
    horizon = len(windows[0].target_dates)
    if any(len(w.target_dates) != horizon for w in windows):
        raise ValueError("mixed horizons")
    params = candidate.model_dump(exclude={"num_boost_round"})
    params["lambda"] = params.pop("reg_lambda")
    boosters = []
    for lead in range(horizon):
        features = [feature_vector(w.history_values, w.target_dates[lead]) for w in windows]
        labels = [w.target_values[lead] for w in windows]
        boosters.append(
            xgb.train(
                params, _matrix(features, labels=labels), num_boost_round=candidate.num_boost_round
            )
        )
    return DirectModels(candidate=candidate, boosters=boosters)


def _predict_with_clips(
    models: DirectModels, history: tuple[int | float, ...], target_dates: tuple[date, ...]
) -> tuple[tuple[float, ...], int]:
    import math

    if len(target_dates) not in (1, 7) or len(models.boosters) != len(target_dates):
        raise ValueError("model and horizon mismatch")
    if any(type(day) is not date for day in target_dates) or any(
        right != left + timedelta(days=1)
        for left, right in zip(target_dates, target_dates[1:], strict=False)
    ):
        raise ValueError("target dates must be consecutive")
    outputs = []
    clips = 0
    for booster, target in zip(models.boosters, target_dates, strict=True):
        value = float(booster.predict(_matrix([feature_vector(history, target)]))[0])
        if not math.isfinite(value):
            raise ValueError("nonfinite prediction")
        if value < 0:
            clips += 1
            value = 0.0
        outputs.append(value)
    return tuple(outputs), clips


def predict_direct(
    models: DirectModels, history: tuple[int | float, ...], target_dates: tuple[date, ...]
) -> tuple[float, ...]:
    return _predict_with_clips(models, history, target_dates)[0]
