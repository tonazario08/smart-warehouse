"""Calendar windows and leak-free direct-forecast features."""

import math
from datetime import date, timedelta

from app.analytics.schemas import business_day_bounds
from app.forecasting.schemas import ForecastDataset, ForecastOrigin, ForecastWindow


def feature_vector(history: tuple[int | float, ...], target_date: date) -> tuple[int | float, ...]:
    try:
        valid = (
            isinstance(history, tuple)
            and len(history) == 28
            and all(type(v) in (int, float) and math.isfinite(v) and v >= 0 for v in history)
        )
        if not valid:
            raise ValueError
        mean7 = sum(history[-7:]) / 7
        mean28 = sum(history) / 28
        if not math.isfinite(mean7) or not math.isfinite(mean28):
            raise ValueError
    except (TypeError, OverflowError, ValueError):
        raise ValueError("28 finite nonnegative history values required") from None
    return (
        *reversed(history),
        mean7,
        mean28,
        float(target_date.isoweekday()),
        float(target_date.month),
    )


def make_origin(dataset: ForecastDataset, origin: date, horizon: int) -> ForecastOrigin:
    if type(horizon) is not int or horizon not in dataset.config.horizons:
        raise ValueError("unsupported horizon")
    rows = {row.day: row for row in dataset.observations}
    days = tuple(origin - timedelta(days=i) for i in range(27, -1, -1))
    cutoff = None
    if dataset.config.mode == "operational":
        cutoff = business_day_bounds(origin, dataset.config.business_timezone)[1]
    history = []
    for day in days:
        row = rows.get(day)
        if (
            row is None
            or row.value is None
            or (cutoff is not None and (row.available_at is None or row.available_at > cutoff))
        ):
            raise ValueError("ineligible history")
        history.append(row.value)
    return ForecastOrigin(
        series_key=dataset.series_key,
        origin=origin,
        history_dates=days,
        history_values=tuple(history),
        target_dates=tuple(origin + timedelta(days=i) for i in range(1, horizon + 1)),
    )


def make_windows(
    dataset: ForecastDataset, partition: str, horizon: int
) -> tuple[ForecastWindow, ...]:
    if type(horizon) is not int or horizon not in dataset.config.horizons:
        raise ValueError("unsupported horizon")
    matching = [p for p in dataset.config.partitions if p.name == partition]
    if len(matching) != 1:
        raise ValueError("unknown partition")
    part = matching[0]
    rows = {row.day: row for row in dataset.observations}
    windows = []
    for row in dataset.observations:
        origin = row.day
        if not (
            part.start <= origin + timedelta(days=1) and origin + timedelta(days=horizon) < part.end
        ):
            continue
        try:
            item = make_origin(dataset, origin, horizon)
        except ValueError:
            continue
        labels = [rows.get(day) for day in item.target_dates]
        if any(label is None or label.value is None for label in labels):
            continue
        windows.append(
            ForecastWindow(
                **item.model_dump(), target_values=tuple(label.value for label in labels)
            )
        )
    return tuple(windows)
