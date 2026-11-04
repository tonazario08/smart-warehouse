from datetime import date

import pytest

from app.forecasting.features import make_windows
from app.forecasting.models import _predict_with_clips, fit_direct, predict_direct
from app.forecasting.schemas import ModelConfig
from tests.forecasting_helpers import dataset


def test_native_model_is_deterministic_and_json_round_trip():
    import xgboost as xgb

    windows = make_windows(dataset(), "train", 1)
    first = fit_direct(windows, ModelConfig(max_depth=2))
    second = fit_direct(windows, ModelConfig(max_depth=2))
    origin = windows[0]
    expected = predict_direct(first, origin.history_values, origin.target_dates)
    assert predict_direct(second, origin.history_values, origin.target_dates) == expected
    assert first.array_dtype == "float32"
    restored = xgb.Booster()
    restored.load_model(bytearray(first.boosters[0].save_raw(raw_format="json")))
    first.boosters[0] = restored
    assert predict_direct(first, origin.history_values, origin.target_dates) == expected


def test_empty_training_and_invalid_candidates_rejected():
    with pytest.raises(ValueError):
        fit_direct((), ModelConfig(max_depth=2))
    with pytest.raises(ValueError):
        ModelConfig(max_depth=5)
    invalid = ModelConfig(max_depth=2).model_copy(update={"nthread": 2})
    with pytest.raises(ValueError):
        fit_direct(make_windows(dataset(), "train", 1), invalid)


def test_all_zero_training_yields_finite_nonnegative_prediction():
    windows = make_windows(dataset(future_value=0), "train", 1)
    model = fit_direct(windows, ModelConfig(max_depth=2))
    assert predict_direct(model, (0,) * 28, (date(2020, 2, 1),))[0] >= 0


def test_model_requires_consecutive_future_calendar_dates():
    from datetime import timedelta

    windows = make_windows(dataset(), "train", 7)
    model = fit_direct(windows, ModelConfig(max_depth=2))
    start = date(2020, 2, 1)
    dates = tuple(start + timedelta(days=i * 2) for i in range(7))
    with pytest.raises(ValueError):
        predict_direct(model, (1,) * 28, dates)


def test_negative_predictions_are_clipped_and_nonfinite_predictions_fail(monkeypatch):
    import numpy as np

    model = fit_direct(make_windows(dataset(), "train", 1), ModelConfig(max_depth=2))
    monkeypatch.setattr(model.boosters[0], "predict", lambda _: np.array([-3.0]))
    values, clips = _predict_with_clips(model, (1,) * 28, (date(2020, 2, 1),))
    assert values == (0,) and clips == 1
    monkeypatch.setattr(model.boosters[0], "predict", lambda _: np.array([float("nan")]))
    with pytest.raises(ValueError):
        predict_direct(model, (1,) * 28, (date(2020, 2, 1),))


def test_model_structural_verification_accepts_nonconstant_fit():
    from app.forecasting.artifacts import _validate_model
    from app.forecasting.schemas import ForecastDataset

    source = dataset()
    altered = ForecastDataset(
        config=source.config,
        series_key=source.series_key,
        observations=tuple(
            row.model_copy(update={"value": i}) for i, row in enumerate(source.observations)
        ),
        limitations=(),
    )
    candidate = ModelConfig(max_depth=2)
    models = fit_direct(make_windows(altered, "train", 1), candidate)
    _validate_model(models.boosters[0], candidate)
