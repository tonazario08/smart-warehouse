"""Independent arithmetic reconciliation of an already verified M7 run.

This module deliberately does not import M7 calibration, policy or simulation algorithms.
"""

import argparse
import getpass
import hashlib
import json
import os
import stat
import sys
import tempfile
from collections import defaultdict
from datetime import date, timedelta
from decimal import ROUND_CEILING, Decimal
from pathlib import Path


def _owned(path):
    path = Path(path)
    if not path.is_absolute() or ".." in path.parts or str(path).startswith(("\\\\", "//")):
        raise ValueError("PATH")
    for part in (*reversed(path.parents), path):
        info = part.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError("PATH")
    path = path.resolve(strict=True)
    workspace = Path(__file__).resolve().parents[1]
    allowed = workspace / "artifacts" / "replenishment"
    pytest_root = Path(tempfile.gettempdir()) / f"pytest-of-{getpass.getuser()}"
    if not path.is_relative_to(allowed) and not (
        path.is_relative_to(pytest_root)
        and "pytest" in sys.modules
        and os.environ.get("PYTEST_CURRENT_TEST")
    ):
        raise ValueError("PATH")
    return path


def _read(path):
    with Path(path).open("rb") as stream:
        data = stream.read(67108865)
    if len(data) > 67108864:
        raise ValueError("LIMIT")
    return data


def _rank(items, probability):
    ordered = sorted(items)
    if not ordered:
        raise ValueError("EMPTY")
    return ordered[int((probability * len(ordered)).to_integral_value(rounding=ROUND_CEILING)) - 1]


def _require(condition):
    if not condition:
        raise ValueError("MISMATCH")


def reconcile(run_dir, forecast_dir, bundle_dir, config, authorization):
    from app.replenishment.inputs import validate_authorization_paths

    validate_authorization_paths(authorization)
    _require(
        Path(forecast_dir) == authorization.forecast_dir
        and Path(bundle_dir) == authorization.bundle_path
    )
    root = _owned(Path(run_dir))
    for name, expected in authorization.bundle_hashes.items():
        _require(hashlib.sha256(_read(Path(bundle_dir) / name)).hexdigest() == expected)
    public_body = _read(Path(forecast_dir) / "public-manifest.json")
    _require(hashlib.sha256(public_body).hexdigest() == authorization.public_manifest_sha256)
    public_manifest = json.loads(public_body)
    _require(set(public_manifest["artifacts"]) == {"predictions.jsonl", "metrics.json"})
    for name, digest in public_manifest["artifacts"].items():
        _require(hashlib.sha256(_read(Path(forecast_dir) / name)).hexdigest() == digest)
    manifest = json.loads(_read(root / "manifest.json"))
    _require(manifest["config"] == config.model_dump(mode="json"))
    for name, digest in manifest["scientific_files"].items():
        _require(hashlib.sha256(_read(root / name)).hexdigest() == digest)
    forecasts = [
        json.loads(line) for line in _read(Path(forecast_dir) / "predictions.jsonl").splitlines()
    ]
    observations = [
        json.loads(line) for line in _read(Path(bundle_dir) / "observations.jsonl").splitlines()
    ]
    labels = {
        date.fromisoformat(row["business_date"]): row["target_quantity"] for row in observations
    }
    _require(len(labels) == len(observations))
    groups = defaultdict(list)
    for row in forecasts:
        key = (row["algorithm"], row["horizon"], date.fromisoformat(row["origin"]))
        groups[key].append(row)
    for (_algorithm, horizon, origin), rows in groups.items():
        rows.sort(key=lambda row: row["lead"])
        _require([row["lead"] for row in rows] == list(range(1, horizon + 1)))
        for row in rows:
            target = date.fromisoformat(row["target_date"])
            _require(
                target == origin + timedelta(days=row["lead"])
                and labels.get(target) == row["actual"]
            )
    algorithms = ("persistence", "seasonal_naive", "xgboost")
    cs, ce, es, ee = (
        config.calibration_start,
        config.calibration_end,
        config.evaluation_start,
        config.evaluation_end,
    )
    calibration = json.loads(_read(root / "calibration.json"))
    entries = {(e["algorithm"], e["horizon"]): e for e in calibration["calibration"]["entries"]}
    _require(set(entries) == {(a, h) for a in algorithms for h in (1, 7)})
    quantiles = {}
    daily_samples = []
    for algorithm in algorithms:
        for horizon in (1, 7):
            selected = sorted(
                (origin, rows)
                for (a, h, origin), rows in groups.items()
                if a == algorithm
                and h == horizon
                and origin + timedelta(days=1) >= cs
                and origin + timedelta(days=horizon) < ce
            )
            residuals = []
            expected_windows = []
            for origin, rows in selected:
                actual = sum(Decimal(str(row["actual"])) for row in rows)
                forecast = sum(max(Decimal(0), Decimal(str(row["prediction"]))) for row in rows)
                error = actual - forecast
                residuals.append(error)
                expected_windows.append(
                    (origin.isoformat(), (origin + timedelta(days=horizon)).isoformat(), error)
                )
                if horizon == 1 and algorithm == algorithms[0]:
                    daily_samples.append((origin + timedelta(days=1), rows[0]["actual"]))
            _require(len(residuals) >= config.minimum_samples)
            entry = entries[algorithm, horizon]
            got = [(x["origin"], x["target_end"], Decimal(x["residual"])) for x in entry["windows"]]
            _require(got == expected_windows)
            q = {
                str(Decimal(p)): _rank(residuals, Decimal(p)) for p in (".05", ".80", ".90", ".95")
            }
            _require({key: Decimal(value) for key, value in entry["quantiles"].items()} == q)
            quantiles[algorithm, horizon] = q
    unique = dict(daily_samples)
    _require(len(unique) == len(daily_samples) and len(unique) > 0)
    annual = Decimal(365) * Decimal(sum(unique.values())) / Decimal(len(unique))
    _require(annual == Decimal(calibration["calibration"]["annual_demand"]))
    _require(
        calibration["calibration"]["annual_demand_dates"] == [d.isoformat() for d in sorted(unique)]
    )
    k, h = config.costs.ordering_cost, config.costs.holding_cost
    _require(k is not None and h is not None and k > 0 and h > 0)
    eoq = (2 * annual * k / h).sqrt() if annual else Decimal(0)
    quantity = int(eoq.to_integral_value(rounding=ROUND_CEILING))
    _require(
        Decimal(calibration["eoq"]["raw"]) == eoq and calibration["eoq"]["quantity"] == quantity
    )
    origin_sets = [
        {
            origin
            for a2, h2, origin in groups
            if (a2, h2) == (a, horizon)
            and origin + timedelta(days=1) >= es
            and origin + timedelta(days=horizon) < ee
        }
        for a in algorithms
        for horizon in (1, 7)
    ]
    common = set.intersection(*origin_sets)
    expected_origins = {es + timedelta(days=i - 1) for i in range((ee - es).days - 6)}
    _require(common == expected_origins)
    metrics = {
        (m["algorithm"], m["horizon"], m["subset"]): m for m in calibration["interval_metrics"]
    }
    _require(len(metrics) == 12)
    for algorithm in algorithms:
        for horizon in (1, 7):
            q = quantiles[algorithm, horizon]
            for subset in ("all", "monday"):
                origins = sorted(
                    o for o in common if subset == "all" or (o + timedelta(days=1)).weekday() == 0
                )
                result = metrics[algorithm, horizon, subset]
                _require(
                    result["count"] == len(origins)
                    and result["origins"] == [o.isoformat() for o in origins]
                )
                if not origins:
                    _require(
                        result["reason_code"] == "NO_EVALUATION_WINDOWS"
                        and result["coverage"] is None
                    )
                    continue
                cover, widths, scores = 0, [], []
                losses = {p: [] for p in q}
                for origin in origins:
                    rows = groups[algorithm, horizon, origin]
                    m = sum(max(Decimal(0), Decimal(str(r["prediction"]))) for r in rows)
                    actual = sum(Decimal(str(r["actual"])) for r in rows)
                    low = max(Decimal(0), m + q["0.05"])
                    high = max(Decimal(0), m + q["0.95"])
                    cover += low <= actual <= high
                    widths.append(high - low)
                    scores.append(
                        high
                        - low
                        + 20 * max(Decimal(0), low - actual)
                        + 20 * max(Decimal(0), actual - high)
                    )
                    for probability in q:
                        p = Decimal(probability)
                        error = actual - max(Decimal(0), m + q[probability])
                        losses[probability].append(max(p * error, (p - 1) * error))
                n = len(origins)
                _require(
                    result["reason_code"] is None
                    and Decimal(result["coverage"]) == Decimal(cover) / n
                )
                _require(Decimal(result["mean_width"]) == sum(widths, Decimal(0)) / n)
                _require(Decimal(result["mean_interval_score"]) == sum(scores, Decimal(0)) / n)
                _require(
                    {p: Decimal(v) for p, v in result["pinball"].items()}
                    == {p: sum(v, Decimal(0)) / n for p, v in losses.items()}
                )
    day_rows = [json.loads(line) for line in _read(root / "days.jsonl").splitlines()]
    order_rows = [json.loads(line) for line in _read(root / "orders.jsonl").splitlines()]
    summaries = json.loads(_read(root / "summaries.json"))

    def key(item):
        c = item["case"]
        return c["algorithm"], c["horizon"], c["service"], c["policy"]

    by_day = defaultdict(list)
    by_order = defaultdict(list)
    for item in day_rows:
        by_day[key(item)].append(item["day"])
    for item in order_rows:
        by_order[key(item)].append(item["order"])
    by_summary = {key(item): item for item in summaries}
    expected_cases = {
        (a, lead, str(service), policy)
        for a in algorithms
        for lead in (1, 7)
        for service in config.service_probabilities
        for policy in ("baseline", "proposed")
    }
    _require(set(by_day) == set(by_summary) == expected_cases and len(summaries) == 36)
    for case in sorted(expected_cases):
        algorithm, lead, service, policy = case
        rows = by_day[case]
        data = by_summary[case]
        _require(
            len(rows) == len(common)
            and data["initial_on_hand"] == config.initial_on_hand
            and data["initial_pipeline"]
            == [o.model_dump(mode="json") for o in config.initial_pipeline]
        )
        pending = {o.order_id: (o.due_date, o.quantity) for o in config.initial_pipeline}
        _require(len(pending) == len(config.initial_pipeline))
        on_hand = config.initial_on_hand
        orders = []
        warm = []
        scored = []
        scored_open = None
        for idx, (origin, row) in enumerate(zip(sorted(common), rows, strict=True)):
            day = origin + timedelta(days=1)
            warmup = idx < config.warmup_days
            if idx == config.warmup_days:
                scored_open = (on_hand, sum(q for _, q in pending.values()))
            opening = on_hand
            due = [(ident, qty) for ident, (when, qty) in pending.items() if when == day]
            for ident, _ in due:
                del pending[ident]
            received = sum(qty for _, qty in due)
            on_hand += received
            position = on_hand + sum(qty for _, qty in pending.values())
            mean = sum(
                max(Decimal(0), Decimal(str(r["prediction"])))
                for r in groups[algorithm, lead, origin]
            )
            q = quantiles[algorithm, lead][service]
            safety = max(Decimal(0), q) if policy == "proposed" else Decimal(0)
            reorder = int((mean + safety).to_integral_value(rounding=ROUND_CEILING))
            ordered = quantity if position <= reorder and quantity > 0 else 0
            due_date = day + timedelta(days=lead) if ordered else None
            ident = row["order_id"]
            if ordered:
                _require(isinstance(ident, str) and ident not in pending)
                pending[ident] = (due_date, ordered)
                orders.append(
                    {
                        "order_id": ident,
                        "ordered_on": day.isoformat(),
                        "due_date": due_date.isoformat(),
                        "quantity": ordered,
                    }
                )
            else:
                _require(ident is None)
            demand = labels[day]
            fulfilled = min(on_hand, demand)
            lost = demand - fulfilled
            on_hand -= fulfilled
            expected = {
                "day": day.isoformat(),
                "origin": origin.isoformat(),
                "warmup": warmup,
                "opening_on_hand": opening,
                "received": received,
                "received_order_ids": [i for i, _ in due],
                "position": position,
                "forecast_mean": str(mean),
                "residual_quantile": str(q),
                "safety_stock": str(safety),
                "reorder_point": reorder,
                "order_quantity": quantity,
                "ordered": ordered,
                "order_id": ident,
                "due_date": due_date.isoformat() if due_date else None,
                "demand": demand,
                "fulfilled": fulfilled,
                "lost": lost,
                "on_hand_end": on_hand,
                "pipeline_end": sum(qty for _, qty in pending.values()),
                "ordering_cost": str(k if ordered else Decimal(0)),
                "holding_cost": str(Decimal(on_hand) * h / 365),
            }
            _require(row == expected)
            (warm if warmup else scored).append(row)
        _require(by_order[case] == orders)
        summary = data["summary"]
        total = sum(r["demand"] for r in scored)
        filled = sum(r["fulfilled"] for r in scored)
        positive = sum(r["demand"] > 0 for r in scored)
        ordering = sum((Decimal(r["ordering_cost"]) for r in scored), Decimal(0))
        holding = sum((Decimal(r["holding_cost"]) for r in scored), Decimal(0))
        _require(
            summary["scored_days"] == len(scored)
            and (summary["scored_opening_on_hand"], summary["scored_opening_pipeline"])
            == scored_open
        )
        _require(
            (summary["closing_on_hand"], summary["terminal_pipeline"])
            == (on_hand, sum(qty for _, qty in pending.values()))
        )
        _require(
            (summary["demand"], summary["fulfilled"], summary["lost"])
            == (total, filled, total - filled)
        )
        _require(
            (Decimal(summary["fill_rate"]) if summary["fill_rate"] is not None else None)
            == (Decimal(filled) / total if total else None)
        )
        _require(summary["fill_reason"] == (None if total else "ZERO_DEMAND"))
        expected_service = (
            Decimal(sum(r["demand"] > 0 and r["lost"] == 0 for r in scored)) / positive
            if positive
            else None
        )
        _require(
            (Decimal(summary["day_service"]) if summary["day_service"] is not None else None)
            == expected_service
        )
        _require(summary["day_service_reason"] == (None if positive else "NO_POSITIVE_DEMAND_DAYS"))
        _require(summary["stockout_days"] == sum(r["lost"] > 0 for r in scored))
        _require(
            Decimal(summary["average_on_hand"])
            == Decimal(sum(r["on_hand_end"] for r in scored)) / len(scored)
        )
        _require(
            summary["order_count"] == sum(r["ordered"] > 0 for r in scored)
            and summary["receipt_count"] == sum(len(r["received_order_ids"]) for r in scored)
        )
        _require(
            Decimal(summary["ordering_cost"]) == ordering
            and Decimal(summary["holding_cost"]) == holding
            and Decimal(summary["partial_cost"]) == ordering + holding
        )
        _require(
            (summary["warmup_demand"], summary["warmup_fulfilled"], summary["warmup_lost"])
            == (
                sum(r["demand"] for r in warm),
                sum(r["fulfilled"] for r in warm),
                sum(r["lost"] for r in warm),
            )
        )
        _require(
            Decimal(summary["warmup_ordering_cost"])
            == sum((Decimal(r["ordering_cost"]) for r in warm), Decimal(0))
        )
        _require(
            Decimal(summary["warmup_holding_cost"])
            == sum((Decimal(r["holding_cost"]) for r in warm), Decimal(0))
        )
        _require(
            summary["cycle_service"] is None
            and summary["cycle_service_reason"] == "OVERLAPPING_CYCLES_UNSUPPORTED"
        )
    return {"status": "reconciled", "cases": len(expected_cases), "days": len(day_rows)}


def main(argv=None):
    parser = argparse.ArgumentParser()
    for field in ("run-dir", "forecast-dir", "bundle", "config", "authorization"):
        parser.add_argument("--" + field, required=True)
    try:
        args = parser.parse_args(argv)
        from app.replenishment.schemas import InputAuthorization, StudyConfig

        config = StudyConfig.model_validate_json(_read(_owned(Path(args.config))))
        authorization = InputAuthorization.model_validate_json(
            _read(_owned(Path(args.authorization)))
        )
        print(
            json.dumps(
                reconcile(
                    Path(args.run_dir),
                    Path(args.forecast_dir),
                    Path(args.bundle),
                    config,
                    authorization,
                ),
                separators=(",", ":"),
            )
        )
        return 0
    except Exception:
        print('{"code":"RECONCILIATION_FAILED"}', file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
