from datetime import date

import pytest

from app.forecasting.baselines import predict_baseline
from app.forecasting.features import make_origin, make_windows
from tests.forecasting_helpers import dataset


def test_seasonal_and_persistence_use_only_history_for_future_and_evaluation():
    ds = dataset()
    origin = make_origin(ds, date(2020, 1, 28), 7)
    window = make_windows(ds, "train", 7)[0]
    for item in (origin, window):
        assert predict_baseline(item, "persistence") == (28,) * 7
        assert predict_baseline(item, "seasonal_naive") == (22, 23, 24, 25, 26, 27, 28)
    with pytest.raises(ValueError):
        predict_baseline(origin, "unknown")
