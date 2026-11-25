"""History-only forecast baselines."""

from typing import Literal

from app.forecasting.schemas import ForecastOrigin, ForecastWindow


def predict_baseline(
    origin: ForecastOrigin | ForecastWindow, algorithm: Literal["persistence", "seasonal_naive"]
) -> tuple[int | float, ...]:
    horizon = len(origin.target_dates)
    if algorithm == "persistence":
        return (origin.history_values[-1],) * horizon
    if algorithm == "seasonal_naive":
        return tuple(origin.history_values[-7 + i] for i in range(horizon))
    raise ValueError("unknown baseline")
