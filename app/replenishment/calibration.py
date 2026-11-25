"""Retrospective same-origin calibration and interval scoring."""

from datetime import date
from decimal import ROUND_CEILING, Decimal

from app.replenishment.inputs import classify_window, select_windows
from app.replenishment.policy import _decimal
from app.replenishment.schemas import (
    CalibrationEntry,
    CalibrationSet,
    CalibrationWindow,
    IntervalResult,
    StudyConfig,
    StudyInputs,
)


def nearest_rank(values, probability):
    p = _decimal(probability)
    if not Decimal(0) < p < Decimal(1):
        raise ValueError("probability must be strictly between zero and one")
    ordered = sorted(_decimal(value) for value in values)
    if not ordered:
        raise ValueError("empty calibration")
    rank = int((p * len(ordered)).to_integral_value(rounding=ROUND_CEILING))
    return ordered[rank - 1]


def cumulative_residual(rows, cutoff: date):
    if not rows or not classify_window(rows, date.min, cutoff):
        raise ValueError("unmatured calibration window")
    return sum(
        (_decimal(row.actual) - max(Decimal(0), _decimal(row.prediction)) for row in rows),
        Decimal(0),
    )


def calibration_quantiles(errors, minimum_samples):
    if type(minimum_samples) is not int or minimum_samples < 30 or len(errors) < minimum_samples:
        raise ValueError("insufficient calibration")
    return {p: nearest_rank(errors, p) for p in map(Decimal, (".05", ".80", ".90", ".95"))}


def annual_demand(values):
    by_day = {}
    for day, value in values:
        if type(day) is not date or type(value) is not int or value < 0:
            raise ValueError("valid integral dated observations required")
        if day in by_day and by_day[day] != value:
            raise ValueError("conflicting actuals")
        by_day[day] = value
    if not by_day:
        raise ValueError("no demand observations")
    return Decimal(365) * Decimal(sum(by_day.values())) / Decimal(len(by_day))


def score_interval(mean, actual, lower_quantile, upper_quantile):
    mean, actual, lo, hi = map(_decimal, (mean, actual, lower_quantile, upper_quantile))
    if mean < 0 or actual < 0 or lo > hi:
        raise ValueError("invalid interval inputs")
    lower, upper = max(Decimal(0), mean + lo), max(Decimal(0), mean + hi)
    width = upper - lower
    score = width + 20 * max(Decimal(0), lower - actual) + 20 * max(Decimal(0), actual - upper)

    def pinball(target, prediction, p):
        error = target - prediction
        return max(p * error, (p - 1) * error)

    return IntervalResult(
        lower=lower,
        upper=upper,
        covered=lower <= actual <= upper,
        width=width,
        interval_score=score,
        lower_pinball=pinball(actual, lower, Decimal(".05")),
        upper_pinball=pinball(actual, upper, Decimal(".95")),
    )


def calibrate(inputs: StudyInputs, config: StudyConfig) -> CalibrationSet:
    config = StudyConfig.model_validate_json(config.model_dump_json())
    if inputs.config != config:
        raise ValueError("study configuration mismatch")
    rows = inputs.forecast.rows
    windows = select_windows(rows, config.calibration_start, config.calibration_end)
    entries = []
    for algorithm in ("persistence", "seasonal_naive", "xgboost"):
        for horizon in config.lead_times:
            selected = tuple(
                w for w in windows if w[0].algorithm == algorithm and w[0].horizon == horizon
            )
            errors = tuple(cumulative_residual(w, config.evaluation_start) for w in selected)
            quantiles = calibration_quantiles(errors, config.minimum_samples)
            entries.append(
                CalibrationEntry(
                    algorithm=algorithm,
                    horizon=horizon,
                    windows=tuple(
                        CalibrationWindow(
                            origin=w[0].origin, target_end=w[-1].target_date, residual=e
                        )
                        for w, e in zip(selected, errors, strict=True)
                    ),
                    quantiles={str(key): value for key, value in quantiles.items()},
                )
            )
    h1_sets = [
        {
            (w[0].target_date, w[0].actual)
            for w in windows
            if w[0].horizon == 1 and w[0].algorithm == algorithm
        }
        for algorithm in ("persistence", "seasonal_naive", "xgboost")
    ]
    common = set.intersection(*h1_sets)
    demand = annual_demand(sorted(common))
    return CalibrationSet(
        entries=tuple(entries),
        annual_demand=demand,
        annual_demand_dates=tuple(sorted(day for day, _ in common)),
        calibration_start=config.calibration_start,
        calibration_end=config.calibration_end,
        evaluation_start=config.evaluation_start,
        evaluation_end=config.evaluation_end,
        knowledge_convention=config.temporal_availability_convention,
    )


def paired_evaluation(rows, entries, start, end):
    """Score identical common origins; Monday means the following decision day."""
    from datetime import timedelta

    from app.replenishment.schemas import IntervalMetrics

    algorithms = ("persistence", "seasonal_naive", "xgboost")
    groups = select_windows(rows, start, end)
    index = {(w[0].algorithm, w[0].horizon, w[0].origin): w for w in groups}
    if len(index) != len(groups) or len({w[0].series_key for w in groups}) > 1:
        raise ValueError("single series required")
    actuals = {}
    for group in groups:
        for row in group:
            value = _decimal(row.actual)
            if row.target_date in actuals and actuals[row.target_date] != value:
                raise ValueError("inconsistent actual labels")
            actuals[row.target_date] = value
    entry_map = {(e.algorithm, e.horizon): e for e in entries}
    pairs = {(a, h) for a in algorithms for h in (1, 7)}
    if set(entry_map) != pairs or len(entry_map) != len(entries):
        raise ValueError("complete unique calibration entries required")
    common = set.intersection(*({o for a2, h2, o in index if (a2, h2) == pair} for pair in pairs))
    output = []
    for algorithm in algorithms:
        for horizon in (1, 7):
            quantiles = {
                Decimal(p): value for p, value in entry_map[algorithm, horizon].quantiles.items()
            }
            if set(quantiles) != set(map(Decimal, (".05", ".80", ".90", ".95"))):
                raise ValueError("missing quantiles")
            for subset in ("all", "monday"):
                origins = tuple(
                    sorted(
                        o
                        for o in common
                        if subset == "all" or (o + timedelta(days=1)).weekday() == 0
                    )
                )
                scores = []
                pinballs = {p: [] for p in quantiles}
                for origin in origins:
                    window = index[algorithm, horizon, origin]
                    mean = sum(
                        (max(Decimal(0), _decimal(r.prediction)) for r in window), Decimal(0)
                    )
                    actual = sum((_decimal(r.actual) for r in window), Decimal(0))
                    score = score_interval(
                        mean, actual, quantiles[Decimal(".05")], quantiles[Decimal(".95")]
                    )
                    scores.append(score)
                    for p, q in quantiles.items():
                        prediction = max(Decimal(0), mean + q)
                        error = actual - prediction
                        pinballs[p].append(max(p * error, (p - 1) * error))
                count = len(origins)
                output.append(
                    IntervalMetrics(
                        algorithm=algorithm,
                        horizon=horizon,
                        subset=subset,
                        origins=origins,
                        count=count,
                        reason_code=None if count else "NO_EVALUATION_WINDOWS",
                        coverage=Decimal(sum(s.covered for s in scores)) / count if count else None,
                        mean_width=sum((s.width for s in scores), Decimal(0)) / count
                        if count
                        else None,
                        mean_interval_score=sum((s.interval_score for s in scores), Decimal(0))
                        / count
                        if count
                        else None,
                        pinball={
                            str(p): sum(values, Decimal(0)) / count if count else None
                            for p, values in pinballs.items()
                        },
                    )
                )
    return tuple(output)
