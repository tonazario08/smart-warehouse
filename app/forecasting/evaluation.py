"""Leakage-aware offline selection and forecast scoring."""

import hashlib
import inspect
import math
import platform
from fractions import Fraction
from importlib.metadata import version
from pathlib import Path

from pydantic import ConfigDict

from app.analytics.export import canonical_json
from app.analytics.schemas import business_day_bounds
from app.forecasting import baselines as baselines_module
from app.forecasting import dataset as dataset_module
from app.forecasting import evaluation as evaluation_module
from app.forecasting import features as features_module
from app.forecasting import models as models_module
from app.forecasting import schemas as schemas_module
from app.forecasting.baselines import predict_baseline
from app.forecasting.features import make_origin, make_windows
from app.forecasting.models import DirectModels, _predict_with_clips, fit_direct
from app.forecasting.schemas import (
    EvaluationResult as EvaluationMetadata,
)
from app.forecasting.schemas import (
    ForecastDataset,
    MetricReport,
    OperationalBinding,
    PredictionRow,
)
from app.forecasting.schemas import (
    ForecastResult as ForecastMetadata,
)
from app.forecasting.schemas import (
    SelectionResult as SelectionMetadata,
)


class SelectionResult(SelectionMetadata):
    model_config = ConfigDict(
        extra="forbid", strict=True, frozen=True, arbitrary_types_allowed=True
    )
    models: dict[int, DirectModels]


class EvaluationResult(EvaluationMetadata):
    model_config = ConfigDict(
        extra="forbid", strict=True, frozen=True, arbitrary_types_allowed=True
    )
    models: dict[int, DirectModels]


class ForecastResult(ForecastMetadata):
    model_config = ConfigDict(
        extra="forbid", strict=True, frozen=True, arbitrary_types_allowed=True
    )
    models: dict[int, DirectModels]


def _fraction(value):
    return Fraction(value)


def _winner(candidates, errors):
    if not candidates or len(candidates) != len(errors):
        raise ValueError("candidate errors required")
    return min(range(len(candidates)), key=lambda index: errors[index])


def _finite(value):
    try:
        result = float(value)
        if not math.isfinite(result):
            raise ValueError
        return result
    except (OverflowError, ValueError):
        raise ValueError("metric not finite") from None


def score(rows: tuple[PredictionRow, ...]) -> MetricReport:
    if not rows:
        return MetricReport(
            count=0,
            origin_count=0,
            mae=None,
            wape=None,
            origin_total_mae=None,
            reason="NO_ELIGIBLE_WINDOWS",
        )
    if len({(r.unit, r.horizon, r.algorithm) for r in rows}) != 1 or any(
        r.actual is None for r in rows
    ):
        raise ValueError("incompatible or unlabeled predictions")
    groups = {}
    seen = set()
    absolute = Fraction(0)
    actual_sum = Fraction(0)
    for row in rows:
        key = (row.series_key, row.origin, row.lead)
        if key in seen:
            raise ValueError("duplicate prediction")
        seen.add(key)
        actual, prediction = _fraction(row.actual), _fraction(row.prediction)
        absolute += abs(actual - prediction)
        actual_sum += actual
        group = groups.setdefault((row.series_key, row.origin), [Fraction(0), Fraction(0)])
        group[0] += actual
        group[1] += prediction
    origin_error = sum((abs(a - p) for a, p in groups.values()), Fraction(0))
    per_series = {}
    for series in {row.series_key for row in rows}:
        members = [row for row in rows if row.series_key == series]
        error = sum(
            (abs(_fraction(row.actual) - _fraction(row.prediction)) for row in members), Fraction(0)
        )
        total = sum((_fraction(row.actual) for row in members), Fraction(0))
        per_series[series] = (
            len(members),
            _finite(error / len(members)),
            _finite(error / total) if total else None,
        )
    return MetricReport(
        count=len(rows),
        origin_count=len(groups),
        mae=_finite(absolute / len(rows)),
        wape=_finite(absolute / actual_sum) if actual_sum else None,
        origin_total_mae=_finite(origin_error / len(groups)),
        wape_reason=None if actual_sum else "ZERO_ACTUAL_TOTAL",
        per_series=per_series,
    )


def _hash(value):
    if isinstance(value, tuple):
        value = [item.model_dump() for item in value]
    return hashlib.sha256(canonical_json(value)).hexdigest()


def _software_hash():
    return _hash(
        {
            "python": platform.python_version(),
            "xgboost": version("xgboost"),
            "numpy": version("numpy"),
            "scipy": version("scipy"),
            "sources": {
                module.__name__: inspect.getsource(module)
                for module in (
                    dataset_module,
                    baselines_module,
                    features_module,
                    models_module,
                    schemas_module,
                    evaluation_module,
                )
            },
            "persistence_sources": {
                name: Path(__file__).with_name(name).read_text(encoding="utf-8")
                for name in ("artifacts.py", "cli.py")
            },
        }
    )


def _label_cutoff(dataset, windows, cutoff):
    if dataset.config.mode != "operational":
        return
    if cutoff is None:
        raise ValueError("operational information cutoff required")
    rows = {row.day: row for row in dataset.observations}
    if any(
        rows[day].available_at is None or rows[day].available_at > cutoff
        for window in windows
        for day in window.target_dates
    ):
        raise ValueError("label unavailable at information cutoff")


def _rows(dataset, windows, algorithm, model=None):
    result, clips = [], 0
    for window in windows:
        if algorithm == "xgboost":
            values, clipped = _predict_with_clips(model, window.history_values, window.target_dates)
            clips += clipped
        else:
            values = predict_baseline(window, algorithm)
        for lead, (day, actual, prediction) in enumerate(
            zip(window.target_dates, window.target_values, values, strict=True), 1
        ):
            result.append(
                PredictionRow(
                    series_key=window.series_key,
                    origin=window.origin,
                    target_date=day,
                    lead=lead,
                    horizon=len(window.target_dates),
                    algorithm=algorithm,
                    prediction=prediction,
                    actual=actual,
                    unit=dataset.config.unit,
                )
            )
    return tuple(result), clips


def tune(dataset: ForecastDataset, config) -> SelectionResult:
    if config != dataset.config:
        raise ValueError("config and dataset mismatch")
    train_hashes, validation_hashes, selected, metrics, models = {}, {}, {}, {}, {}
    candidate_metrics, candidate_clips, candidate_error = {}, {}, {}
    last_target = []
    for horizon in config.horizons:
        train = make_windows(dataset, "train", horizon)
        validation = make_windows(dataset, "validation", horizon)
        if not train or not validation:
            raise ValueError("no eligible train or validation windows")
        _label_cutoff(dataset, train, config.protocol.train_information_cutoff)
        _label_cutoff(dataset, validation, config.protocol.selection_information_cutoff)
        train_hashes[horizon], validation_hashes[horizon] = _hash(train), _hash(validation)
        choices = []
        for candidate in config.candidates:
            model = fit_direct(train, candidate)
            predictions, clips = _rows(dataset, validation, "xgboost", model)
            report = score(predictions)
            key = f"{horizon}:{candidate.max_depth}"
            candidate_metrics[key], candidate_clips[key] = report, clips
            exact = sum(
                (abs(_fraction(r.actual) - _fraction(r.prediction)) for r in predictions),
                Fraction(0),
            ) / len(predictions)
            candidate_error[key] = (exact.numerator, exact.denominator)
            choices.append((exact, candidate, model, report))
        _, chosen, model, report = choices[
            _winner(config.candidates, [item[0] for item in choices])
        ]
        selected[horizon], models[horizon], metrics[horizon] = chosen, model, report
        last_target.extend(w.target_dates[-1] for w in validation)
    return SelectionResult(
        data_version=config.data_version,
        config_sha256=_hash(config),
        software_sha256=_software_hash(),
        train_hashes=train_hashes,
        validation_hashes=validation_hashes,
        candidates=selected,
        validation_metrics=metrics,
        candidate_metrics=candidate_metrics,
        candidate_clips=candidate_clips,
        candidate_error=candidate_error,
        selection_through=max(last_target),
        knowledge_bound=dataset.knowledge_bound,
        admission_cutoff=dataset.admission_cutoff,
        models=models,
    )


def _revalidate(dataset, selection):
    config = dataset.config
    if (
        not isinstance(selection, SelectionResult)
        or selection.data_version != config.data_version
        or (
            selection.config_sha256 != _hash(config)
            or selection.software_sha256 != _software_hash()
            or selection.knowledge_bound != dataset.knowledge_bound
            or selection.admission_cutoff != dataset.admission_cutoff
            or set(selection.candidates) != set(config.horizons)
        )
    ):
        raise ValueError("selection identity mismatch")
    result = {}
    for horizon in config.horizons:
        train = make_windows(dataset, "train", horizon)
        validation = make_windows(dataset, "validation", horizon)
        keys = [f"{horizon}:{candidate.max_depth}" for candidate in config.candidates]
        reports = [selection.candidate_metrics.get(key) for key in keys]
        errors = [selection.candidate_error.get(key) for key in keys]
        if (
            any(
                report is None or report.mae is None or report.count != len(validation) * horizon
                for report in reports
            )
            or any(selection.candidate_clips.get(key, -1) < 0 for key in keys)
            or any(pair is None or pair[0] < 0 or pair[1] <= 0 for pair in errors)
        ):
            raise ValueError("selection candidate metrics mismatch")
        fractions = [Fraction(*pair) for pair in errors]
        if any(
            _finite(value) != report.mae for value, report in zip(fractions, reports, strict=True)
        ):
            raise ValueError("selection candidate metrics mismatch")
        winner = _winner(config.candidates, fractions)
        if selection.candidates[horizon] != config.candidates[winner] or (
            selection.validation_metrics.get(horizon) != reports[winner]
        ):
            raise ValueError("selection candidate mismatch")
        if (
            not train
            or not validation
            or selection.train_hashes.get(horizon) != _hash(train)
            or (
                selection.validation_hashes.get(horizon) != _hash(validation)
                or selection.candidates[horizon] not in config.candidates
            )
        ):
            raise ValueError("selection windows mismatch")
        _label_cutoff(dataset, train, config.protocol.train_information_cutoff)
        _label_cutoff(dataset, validation, config.protocol.selection_information_cutoff)
        if selection.selection_through != max(
            w.target_dates[-1]
            for h in config.horizons
            for w in make_windows(dataset, "validation", h)
        ):
            raise ValueError("selection boundary mismatch")
        result[horizon] = train + validation
    return result


def _refit(dataset, selection):
    windows = _revalidate(dataset, selection)
    models, hashes = {}, {}
    for horizon, items in windows.items():
        _label_cutoff(dataset, items, dataset.config.protocol.refit_information_cutoff)
        models[horizon] = fit_direct(items, selection.candidates[horizon])
        hashes[horizon] = _hash(items)
    return models, hashes, max(w.target_dates[-1] for items in windows.values() for w in items)


def _possible_origins(partition, horizon):
    return max(0, (partition.end - partition.start).days - horizon + 1)


def evaluate_holdout(dataset: ForecastDataset, selection: SelectionResult) -> EvaluationResult:
    models, hashes, trained = _refit(dataset, selection)
    rows, metrics, exclusions, clips = [], {}, {}, 0
    part = dataset.config.partitions[2]
    for horizon in dataset.config.horizons:
        windows = make_windows(dataset, "final_holdout", horizon)
        possible = _possible_origins(part, horizon)
        exclusions[horizon] = possible - len(windows)
        for algorithm in ("persistence", "seasonal_naive", "xgboost"):
            result, count = _rows(dataset, windows, algorithm, models[horizon])
            rows.extend(result)
            clips += count
            metrics[f"{algorithm}:{horizon}"] = score(result)
    return EvaluationResult(
        rows=tuple(rows),
        metrics=metrics,
        exclusions=exclusions,
        clips=clips,
        trained_through=trained,
        refit_window_hashes=hashes,
        training_information_cutoff=(
            dataset.config.protocol.refit_information_cutoff
            if dataset.config.mode == "operational"
            else dataset.admission_cutoff
        ),
        knowledge_bound=dataset.knowledge_bound,
        admission_cutoff=dataset.admission_cutoff,
        models=models,
    )


def forecast(
    dataset: ForecastDataset, selection: SelectionResult, binding: OperationalBinding, origin
) -> ForecastResult:
    config = dataset.config
    if config.mode != "operational" or config.binding != binding:
        raise ValueError("operational binding mismatch")
    cutoff = business_day_bounds(origin, config.business_timezone)[1]
    if config.protocol.refit_information_cutoff > cutoff or (
        config.protocol.selection_information_cutoff > cutoff
        or selection.selection_through >= origin
    ):
        raise ValueError("selection or refit not known at origin")
    windows = _revalidate(dataset, selection)
    trained = max(w.target_dates[-1] for items in windows.values() for w in items)
    if trained > origin:
        raise ValueError("training targets after origin")
    models, hashes, trained = _refit(dataset, selection)
    rows, clips = [], 0
    for horizon in config.horizons:
        item = make_origin(dataset, origin, horizon)
        for algorithm in ("persistence", "seasonal_naive", "xgboost"):
            if algorithm == "xgboost":
                predictions, count = _predict_with_clips(
                    models[horizon], item.history_values, item.target_dates
                )
                clips += count
            else:
                predictions = predict_baseline(item, algorithm)
            for lead, (day, prediction) in enumerate(
                zip(item.target_dates, predictions, strict=True), 1
            ):
                rows.append(
                    PredictionRow(
                        series_key=item.series_key,
                        origin=origin,
                        target_date=day,
                        lead=lead,
                        horizon=horizon,
                        algorithm=algorithm,
                        prediction=prediction,
                        actual=None,
                        unit=config.unit,
                    )
                )
    return ForecastResult(
        rows=tuple(rows),
        clips=clips,
        trained_through=trained,
        refit_window_hashes=hashes,
        training_information_cutoff=config.protocol.refit_information_cutoff,
        models=models,
    )
