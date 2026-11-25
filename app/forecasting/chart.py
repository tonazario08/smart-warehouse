"""Bounded chart projection over already-verified prediction rows."""

from collections.abc import Iterable
from datetime import date
from heapq import heappush, heapreplace

from app.forecasting.schemas import PredictionRow

CHART_POINTS = 30


def latest_chart_rows(
    rows: Iterable[PredictionRow], *, horizon: int, algorithm: str, lead: int
) -> tuple[str | None, list[PredictionRow]]:
    groups: dict[tuple[str, str], list[tuple[date, int, PredictionRow]]] = {}
    for index, row in enumerate(rows):
        if (row.horizon, row.algorithm, row.lead) != (horizon, algorithm, lead):
            continue
        points = groups.setdefault((row.series_key, row.unit), [])
        point = (row.target_date, index, row)
        if len(points) < CHART_POINTS:
            heappush(points, point)
        elif point[:2] > points[0][:2]:
            heapreplace(points, point)
    if not groups:
        return None, []
    # Prioritize enough context to plot without combining different series.
    # Prefer the newest window, then a stable key when coverage is tied.
    key, window = min(
        groups.items(),
        key=lambda item: (
            -len(item[1]),
            -max(point[0] for point in item[1]).toordinal(),
            item[0],
        ),
    )
    return key[0], [point[2] for point in sorted(window)]
