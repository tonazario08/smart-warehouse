"""Independent, read-only retrospective evaluation reconciliation.

This does not reconstruct XGBoost models or authenticate a catalog author.
"""

import argparse
import hashlib
import json
import math
import os
import stat
from collections import defaultdict
from datetime import date, timedelta
from fractions import Fraction
from pathlib import Path

ALGORITHMS = ("persistence", "seasonal_naive", "xgboost")
LIMIT = 64 * 1024 * 1024


def expected_windows(days, start, end, horizon):
    result = []
    target = start
    while target + timedelta(days=horizon) <= end:
        origin = target - timedelta(days=1)
        history_dates = [origin - timedelta(days=i) for i in range(27, -1, -1)]
        target_dates = [target + timedelta(days=i) for i in range(horizon)]
        if all(day in days and days[day] is not None for day in history_dates + target_dates):
            result.append(
                (
                    origin,
                    [days[day] for day in history_dates],
                    [(day, days[day]) for day in target_dates],
                )
            )
        target += timedelta(days=1)
    return result


def validate_rows(rows, windows, horizon, series, unit):
    expected = {
        (origin.isoformat(), lead): (history, day.isoformat(), actual)
        for origin, history, targets in windows
        for lead, (day, actual) in enumerate(targets, 1)
    }
    seen = set()
    for row in rows:
        key = (row["origin"], row["lead"])
        unique = (row["algorithm"], *key)
        if (
            key not in expected
            or unique in seen
            or row["algorithm"] not in ALGORITHMS
            or row["series_key"] != series
            or row["unit"] != unit
            or row["horizon"] != horizon
        ):
            raise ValueError("population mismatch")
        seen.add(unique)
        history, day, actual = expected[key]
        prediction = row["prediction"]
        if (
            row["target_date"] != day
            or type(row["actual"]) not in (int, float)
            or row["actual"] != actual
            or type(prediction) not in (int, float)
            or not math.isfinite(prediction)
            or prediction < 0
        ):
            raise ValueError("point mismatch")
        if row["algorithm"] == "persistence" and prediction != history[-1]:
            raise ValueError("persistence mismatch")
        if row["algorithm"] == "seasonal_naive" and prediction != history[-8 + row["lead"]]:
            raise ValueError("seasonal mismatch")
    if len(seen) != len(expected) * len(ALGORITHMS):
        raise ValueError("incomplete population")


def metric_report(rows):
    if not rows:
        return dict(
            count=0,
            origin_count=0,
            mae=None,
            wape=None,
            origin_total_mae=None,
            reason="NO_ELIGIBLE_WINDOWS",
            wape_reason=None,
            per_series={},
        )
    groups = defaultdict(lambda: [Fraction(0), Fraction(0)])
    series = defaultdict(lambda: [0, Fraction(0), Fraction(0)])
    absolute = total = Fraction(0)
    for row in rows:
        actual, predicted = Fraction(row["actual"]), Fraction(row["prediction"])
        error = abs(actual - predicted)
        absolute += error
        total += actual
        group = groups[(row["series_key"], row["origin"])]
        group[0] += actual
        group[1] += predicted
        item = series[row["series_key"]]
        item[0] += 1
        item[1] += error
        item[2] += actual
    return dict(
        count=len(rows),
        origin_count=len(groups),
        mae=float(absolute / len(rows)),
        wape=float(absolute / total) if total else None,
        origin_total_mae=float(sum(abs(a - p) for a, p in groups.values()) / len(groups)),
        reason=None,
        wape_reason=None if total else "ZERO_ACTUAL_TOTAL",
        per_series={
            key: [count, float(error / count), float(error / amount) if amount else None]
            for key, (count, error, amount) in series.items()
        },
    )


def compare_metrics(actual, expected):
    def compare(a, b):
        if isinstance(b, dict):
            return (
                isinstance(a, dict) and a.keys() == b.keys() and all(compare(a[k], b[k]) for k in b)
            )
        if isinstance(b, list):
            return (
                isinstance(a, list)
                and len(a) == len(b)
                and all(compare(x, y) for x, y in zip(a, b, strict=True))
            )
        if type(b) is float:
            return (
                type(a) in (int, float)
                and math.isfinite(a)
                and math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-6)
            )
        return type(a) is type(b) and a == b

    if not compare(actual, expected):
        raise ValueError("metric mismatch")


def _checked(path):
    path = Path(path)
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("absolute safe path required")
    for component in (path, *path.parents):
        info = component.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError("reparse path")
    return path


def _read(path):
    path = _checked(path)
    if not path.is_file() or path.stat().st_size > LIMIT:
        raise ValueError("file size")
    return path.read_bytes()


def _digest(body):
    return hashlib.sha256(body).hexdigest()


def _canonical(value):
    return (
        json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")) + "\n"
    ).encode()


def reconcile(bundle, run, allow_fixture=False):
    from app.analytics.export import verify_bundle

    root_value = os.environ.get("FORECAST_APPROVED_BUNDLE_ROOT")
    if not root_value:
        raise ValueError("approved root required")
    root, bundle, run = _checked(root_value), _checked(bundle), _checked(run)
    owned = _checked(Path.cwd() / "artifacts" / "forecasting")
    if (
        not root.is_dir()
        or bundle == root
        or not bundle.is_relative_to(root)
        or not run.is_relative_to(owned)
    ):
        raise ValueError("path boundary")
    source_names = ("manifest.json", "records.jsonl", "observations.jsonl", "quality.json")
    before = {name: _digest(_read(bundle / name)) for name in source_names}
    version = verify_bundle(bundle)
    source = json.loads(_read(bundle / "manifest.json"))
    manifest = json.loads(_read(run / "manifest.json"))
    config = manifest["config"]
    if (
        manifest["kind"] != "evaluation"
        or config["mode"] != "research"
        or config["data_version"] != version
        or source["data_version"] != version
        or config["dataset_class"] not in ("research", "fixture")
        or config["dataset_class"] != source["admission"]["dataset_class"]
        or config["target"] != source["admission"]["target"]
        or config["knowledge_time_mode"] != "retrospective_final_vintage"
        or config["reporting_scope"] != "company_aggregate"
        or manifest["admission_cutoff"] != source["admission"]["cutoff"]
        or manifest["knowledge_bound"] != source["admission"]["source"]["available_at_upper_bound"]
        or (config["dataset_class"] == "fixture" and not allow_fixture)
    ):
        raise ValueError("source identity mismatch")
    identity = {k: v for k, v in manifest.items() if k != "run_id"}
    if (
        manifest["run_id"] != "frv1-" + _digest(_canonical(identity))
        or run.name != manifest["run_id"]
    ):
        raise ValueError("run identity mismatch")
    for name, digest in manifest["artifacts"].items():
        if (
            Path(name).is_absolute()
            or ".." in Path(name).parts
            or _digest(_read(run / name)) != digest
        ):
            raise ValueError("artifact hash mismatch")
    observations = [json.loads(line) for line in _read(bundle / "observations.jsonl").splitlines()]
    days = {}
    for row in observations:
        day = date.fromisoformat(row["business_date"])
        if day in days:
            raise ValueError("duplicate day")
        days[day] = row["target_quantity"]
    admission = source["admission"]
    if len(admission["mappings"]) != 1:
        raise ValueError("single series required")
    mapping = admission["mappings"][0]
    if any(
        (row["product_key"], row["reporting_entity_key"], row["unit"])
        != (mapping["product_key"], mapping["reporting_entity_key"], mapping["unit"])
        for row in observations
    ) or mapping["unit"] != config["unit"]:
        raise ValueError("series mismatch")
    series = "fsk1-" + _digest(
        _canonical(
            [
                admission["source"]["namespace"],
                mapping["product_key"],
                mapping["reporting_entity_key"],
                mapping["unit"],
                config["target"],
                config["reporting_scope"],
            ]
        )
    )
    rows = [json.loads(line) for line in _read(run / "predictions.jsonl").splitlines()]
    metrics = json.loads(_read(run / "metrics.json"))
    if set(metrics) != {
        f"{algorithm}:{horizon}"
        for algorithm in ALGORITHMS
        for horizon in config["protocol"]["horizons"]
    }:
        raise ValueError("metric set mismatch")
    partitions = config["protocol"]["partitions"]
    counts = {}
    for part in partitions:
        start, end = date.fromisoformat(part["start"]), date.fromisoformat(part["end"])
        for horizon in config["protocol"]["horizons"]:
            windows = expected_windows(days, start, end, horizon)
            counts[f"{part['name']}:{horizon}"] = len(windows)
            if part["name"] != "final_holdout":
                continue
            selected = [row for row in rows if row["horizon"] == horizon]
            validate_rows(selected, windows, horizon, series, config["unit"])
            possible = max(0, (end - start).days - horizon + 1)
            if manifest["result"]["exclusions"][str(horizon)] != possible - len(windows):
                raise ValueError("exclusions mismatch")
            for algorithm in ALGORITHMS:
                members = [row for row in selected if row["algorithm"] == algorithm]
                compare_metrics(metrics[f"{algorithm}:{horizon}"], metric_report(members))
    if len(rows) != sum(
        counts[f"final_holdout:{h}"] * h * 3 for h in config["protocol"]["horizons"]
    ):
        raise ValueError("unexpected rows")
    after = {name: _digest(_read(bundle / name)) for name in source_names}
    if before != after:
        raise ValueError("source changed")
    return dict(
        status="reconciled",
        run_id=manifest["run_id"],
        counts=counts,
        calendar_days=len(days),
        eligible=sum(v is not None for v in days.values()),
        zeros=sum(v == 0 for v in days.values()),
        nulls=sum(v is None for v in days.values()),
        eligible_sum=sum(v for v in days.values() if v is not None),
        source_sha256=after,
        limitation="retrospective final vintage; XGBoost model not independently reconstructed",
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bundle", required=True)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--allow-fixture", action="store_true")
    args = parser.parse_args()
    try:
        print(json.dumps(reconcile(args.bundle, args.run_dir, args.allow_fixture), sort_keys=True))
    except Exception:
        print('{"status":"reconciliation_failed"}')
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
