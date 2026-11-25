"""Immutable, source-bound offline replenishment runs and public projections."""

import getpass
import hashlib
import json
import os
import re
import stat
import sys
import tempfile
import uuid
from datetime import UTC, datetime
from pathlib import Path

from app.analytics.export import canonical_json
from app.replenishment.calibration import calibrate
from app.replenishment.inputs import load_inputs
from app.replenishment.schemas import StudyConfig
from app.replenishment.simulation import simulate

LIMIT = 64 * 1024 * 1024
WORKSPACE = Path(__file__).resolve().parents[2]


def _sha(body):
    return hashlib.sha256(body).hexdigest()


def _json(value):
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    return canonical_json(value)


def _checked(path, *, must_exist=True):
    path = Path(path)
    if not path.is_absolute() or ".." in path.parts or str(path).startswith(("\\\\", "//")):
        raise ValueError("unsafe path")
    for part in (*reversed(path.parents), path):
        if part.exists() or part.is_symlink():
            info = part.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
                raise ValueError("unsafe path")
    return path.resolve(strict=must_exist)


def _owned(path, *, must_exist=True):
    path = _checked(path, must_exist=must_exist)
    allowed = WORKSPACE / "artifacts" / "replenishment"
    pytest_root = Path(tempfile.gettempdir()) / f"pytest-of-{getpass.getuser()}"
    in_test = "pytest" in sys.modules and bool(os.environ.get("PYTEST_CURRENT_TEST"))
    if not path.is_relative_to(allowed) and not (in_test and path.is_relative_to(pytest_root)):
        raise ValueError("unsafe output root")
    return path


def _read(path):
    checked = _checked(path)
    with checked.open("rb") as f:
        body = f.read(LIMIT + 1)
    if len(body) > LIMIT:
        raise ValueError("artifact limit")
    return body


def _decode(body):
    def pairs(values):
        data = {}
        for key, value in values:
            if key in data:
                raise ValueError("duplicate key")
            data[key] = value
        return data

    try:
        value = json.loads(
            body,
            object_pairs_hook=pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError()),
        )
    except (ValueError, TypeError, UnicodeError):
        raise ValueError("invalid artifact JSON") from None
    if _json(value) != body:
        raise ValueError("noncanonical artifact")
    return value


def _code_identity():
    entries = []
    for module in ("analytics", "forecasting", "replenishment"):
        for path in sorted((WORKSPACE / "app" / module).glob("*.py")):
            entries.append([path.relative_to(WORKSPACE).as_posix(), _sha(_read(path))])
    return _sha(_json({"base": "abcdd81e6f46dad0766e104c678abf7f73d62231", "sources": entries}))


def _case(trajectory):
    return {
        "algorithm": trajectory.algorithm,
        "horizon": trajectory.horizon,
        "service": str(trajectory.service),
        "policy": trajectory.policy,
    }


def _scientific(result):
    if len(result.trajectories) != 36:
        raise ValueError("invalid case count")
    summaries, days, orders = [], [], []
    seen = set()
    for trajectory in result.trajectories:
        key = _case(trajectory)
        identity = tuple(key.values())
        if identity in seen:
            raise ValueError("duplicate case")
        seen.add(identity)
        summaries.append(
            {
                "case": key,
                "initial_on_hand": trajectory.initial_on_hand,
                "initial_pipeline": [
                    o.model_dump(mode="json") for o in trajectory.initial_pipeline
                ],
                "summary": trajectory.summary.model_dump(mode="json"),
            }
        )
        days.extend({"case": key, "day": row.model_dump(mode="json")} for row in trajectory.days)
        orders.extend(
            {"case": key, "order": row.model_dump(mode="json")} for row in trajectory.orders
        )
    if len(days) > 50000:
        raise ValueError("too many days")
    payload = {
        "calibration.json": _json(
            {
                "calibration": result.calibration.model_dump(mode="json"),
                "interval_metrics": [x.model_dump(mode="json") for x in result.interval_metrics],
                "eoq": result.eoq.model_dump(mode="json"),
            }
        ),
        "summaries.json": _json(summaries),
        "days.jsonl": b"".join(_json(row) for row in days),
        "orders.jsonl": b"".join(_json(row) for row in orders),
    }
    if any(len(body) > LIMIT for body in payload.values()):
        raise ValueError("artifact limit")
    return payload


def _identity(result, payload):
    return {
        "schema_version": "replenishment-run/1",
        "config": result.config.model_dump(mode="json"),
        "data_version": result.data_version,
        "forecast_run_id": result.forecast_run_id,
        "source_manifest_sha256": result.source_manifest_sha256,
        "public_manifest_sha256": result.public_manifest_sha256,
        "source_business_timezone": result.source_business_timezone,
        "scenario_clock_timezone": result.scenario_clock_timezone,
        "scenario_clock_convention": result.scenario_clock_convention,
        "code_sha256": _code_identity(),
        "scientific_files": {k: _sha(v) for k, v in payload.items()},
    }


def _recompute(config, authorization):
    inputs = load_inputs(
        authorization.forecast_dir, authorization.bundle_path, config, authorization
    )
    result = simulate(inputs, calibrate(inputs, config), config)
    return inputs, result


def _result_paths(root, mode, identity, files, verify_stage=None):
    root = _owned(root, must_exist=False)
    root.mkdir(parents=True, exist_ok=True)
    root = _owned(root)
    if (
        len([p for p in root.iterdir() if p.is_dir() and p.name.startswith("rrv1-")]) >= 100
        and not (root / identity).exists()
    ):
        raise ValueError("catalog limit")
    target = root / identity
    if target.exists():
        target = _owned(target)
        for name, body in files.items():
            if name != "receipt.json" and _read(target / name) != body:
                raise ValueError("artifact conflict")
        if {p.name for p in target.iterdir()} != set(files):
            raise ValueError("artifact conflict")
        return target, True
    stage = root / (".stage-" + uuid.uuid4().hex)
    stage.mkdir(mode=0o700)
    for name, body in files.items():
        with (stage / name).open("xb") as stream:
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
    if verify_stage is not None:
        verify_stage(stage)
    stage.rename(target)
    return _owned(target), False


class PublishedRun:
    def __init__(self, run_id, path, reused=False):
        self.run_id, self.path, self.reused = run_id, path, reused


def publish_run(inputs, config, result, authorization, root):
    fresh_inputs, expected = _recompute(config, authorization)
    if fresh_inputs != inputs or expected != result:
        raise ValueError("result/source mismatch")
    payload = _scientific(expected)
    identity = _identity(expected, payload)
    run_id = "rrv1-" + _sha(_json(identity))
    files = {
        **payload,
        "manifest.json": _json({**identity, "run_id": run_id}),
        "receipt.json": _json(
            {
                "schema_version": "replenishment-receipt/1",
                "created_at": datetime.now(UTC).isoformat(),
            }
        ),
    }
    path, reused = _result_paths(Path(root), config.mode, run_id, files)
    checked = verify_run(path, authorization)
    return PublishedRun(checked.run_id, path, reused)


def verify_run(path, authorization):
    root = _owned(Path(path))
    if re.fullmatch(r"rrv1-[0-9a-f]{64}", root.name) is None:
        raise ValueError("invalid run ID")
    if {p.name for p in root.iterdir()} != {
        "manifest.json",
        "calibration.json",
        "summaries.json",
        "days.jsonl",
        "orders.jsonl",
        "receipt.json",
    }:
        raise ValueError("artifact file set mismatch")
    manifest = _decode(_read(root / "manifest.json"))
    receipt = _decode(_read(root / "receipt.json"))
    if (
        set(receipt) != {"schema_version", "created_at"}
        or receipt["schema_version"] != "replenishment-receipt/1"
    ):
        raise ValueError("invalid receipt")
    created = datetime.fromisoformat(receipt["created_at"])
    if created.utcoffset() is None or created.utcoffset().total_seconds() != 0:
        raise ValueError("invalid receipt time")
    config = StudyConfig.model_validate_json(_json(manifest["config"]))
    _, result = _recompute(config, authorization)
    payload = _scientific(result)
    expected = _identity(result, payload)
    run_id = "rrv1-" + _sha(_json(expected))
    if manifest != {**expected, "run_id": run_id} or root.name != run_id:
        raise ValueError("run identity mismatch")
    for name, body in payload.items():
        if _read(root / name) != body:
            raise ValueError("scientific mismatch")
    return PublishedRun(run_id, root)


def publish_catalog(run_dir, authorization, root):
    verified = verify_run(run_dir, authorization)
    manifest = _decode(_read(verified.path / "manifest.json"))
    config = StudyConfig.model_validate_json(_json(manifest["config"]))
    inputs, _ = _recompute(config, authorization)
    payload = {
        name: _read(verified.path / name)
        for name in ("calibration.json", "summaries.json", "days.jsonl", "orders.jsonl")
    }
    safe_calibration = _decode(payload["calibration.json"])
    safe_calibration["calibration"]["knowledge_convention"] = (
        "retrospective_final_vintage" if config.mode == "research" else "fixture_historical_as_of"
    )
    payload["calibration.json"] = _json(safe_calibration)
    safe_config = config.model_dump(mode="json")
    safe_config.pop("disclosures")
    safe_config.pop("temporal_availability_convention")
    forecast_manifest = inputs.forecast.manifest
    receipt = _decode(_read(verified.path / "receipt.json"))
    public = {
        "schema_version": "replenishment-public-run/1",
        "run_id": verified.run_id,
        "source_manifest_sha256": _sha(_read(verified.path / "manifest.json")),
        "mode": config.mode,
        "dataset_class": config.dataset_class,
        "target": config.target,
        "reporting_scope": config.reporting_scope,
        "unit": config.unit,
        "data_version": config.data_version,
        "forecast_run_id": config.forecast_run_id,
        "created_at": receipt["created_at"],
        "admission_cutoff": forecast_manifest.admission_cutoff.isoformat()
        if forecast_manifest.admission_cutoff
        else None,
        "knowledge_bound": forecast_manifest.knowledge_bound.isoformat()
        if forecast_manifest.knowledge_bound
        else None,
        "training_information_cutoff": forecast_manifest.training_information_cutoff.isoformat()
        if forecast_manifest.training_information_cutoff
        else None,
        "source_business_timezone": manifest["source_business_timezone"],
        "scenario_clock_timezone": manifest["scenario_clock_timezone"],
        "scenario_clock_convention": manifest["scenario_clock_convention"],
        "applicability": "fixture_scenario"
        if config.dataset_class == "fixture"
        else "research_scenario",
        "binding": inputs.forecast.binding.model_dump(mode="json")
        if inputs.forecast.binding
        else None,
        "config": safe_config,
        "artifacts": {k: _sha(v) for k, v in payload.items()},
    }
    public["projection_sha256"] = _sha(_json(public))
    path, _ = _result_paths(
        Path(root) / config.mode,
        config.mode,
        verified.run_id,
        {**payload, "public-manifest.json": _json(public)},
        verify_stage=lambda stage: verify_public_projection(stage, require_name=False),
    )
    verify_public_projection(path)
    return path


def verify_public_projection(path, *, require_name=True, include_snapshot=False):
    """Check bounded public bytes and case structure without fitting or simulation."""
    from collections import defaultdict
    from datetime import date, timedelta
    from decimal import ROUND_CEILING, Decimal

    from app.analytics.schemas import PipelineError, load_timezone, parse_timestamp
    from app.forecasting.repository import PublicBinding
    from app.replenishment.schemas import (
        CalibrationSet,
        EoqResult,
        IntervalMetrics,
        SimulationDay,
        SimulationOrder,
        TrajectorySummary,
    )

    root = _checked(Path(path))
    names = {
        "public-manifest.json",
        "calibration.json",
        "summaries.json",
        "days.jsonl",
        "orders.jsonl",
    }
    if {p.name for p in root.iterdir()} != names:
        raise ValueError("public file set mismatch")
    manifest = _decode(_read(root / "public-manifest.json"))
    fields = {
        "schema_version",
        "run_id",
        "source_manifest_sha256",
        "mode",
        "dataset_class",
        "target",
        "reporting_scope",
        "unit",
        "data_version",
        "forecast_run_id",
        "created_at",
        "admission_cutoff",
        "knowledge_bound",
        "training_information_cutoff",
        "source_business_timezone",
        "scenario_clock_timezone",
        "scenario_clock_convention",
        "applicability",
        "binding",
        "config",
        "artifacts",
        "projection_sha256",
    }
    if set(manifest) != fields or manifest["schema_version"] != "replenishment-public-run/1":
        raise ValueError("unsupported public schema")
    projection = {k: v for k, v in manifest.items() if k != "projection_sha256"}
    if (
        _sha(_json(projection)) != manifest["projection_sha256"]
        or (require_name and manifest["run_id"] != root.name)
        or not isinstance(manifest["run_id"], str)
        or re.fullmatch(r"rrv1-[0-9a-f]{64}", manifest["run_id"]) is None
        or root.parent.name != manifest["mode"]
    ):
        raise ValueError("public identity mismatch")
    if (
        manifest["mode"],
        manifest["dataset_class"],
        manifest["target"],
        manifest["reporting_scope"],
        manifest["applicability"],
    ) not in {
        (
            "research",
            "research",
            "reported_daily_unit_sales",
            "company_aggregate",
            "research_scenario",
        ),
        (
            "research",
            "fixture",
            "reported_daily_unit_sales",
            "company_aggregate",
            "fixture_scenario",
        ),
        ("operational", "fixture", "gross_fulfilled_units", "warehouse", "fixture_scenario"),
    }:
        raise ValueError("public scope mismatch")
    if (manifest["mode"] == "operational") != (manifest["binding"] is not None):
        raise ValueError("public binding mismatch")
    if manifest["binding"] is not None:
        binding = PublicBinding.model_validate_json(_json(manifest["binding"]))
        if binding.data_version != manifest["data_version"] or binding.unit != manifest["unit"]:
            raise ValueError("public binding identity mismatch")
    try:
        created = parse_timestamp(manifest["created_at"])
        if created.utcoffset() != timedelta(0):
            raise ValueError("invalid creation time")
        for name in ("admission_cutoff", "knowledge_bound", "training_information_cutoff"):
            if manifest[name] is not None:
                parse_timestamp(manifest[name])
        load_timezone(manifest["scenario_clock_timezone"])
    except PipelineError:
        raise ValueError("invalid public time metadata") from None
    if manifest["mode"] == "research":
        if (
            manifest["source_business_timezone"] is not None
            or manifest["scenario_clock_timezone"] != "UTC"
            or manifest["scenario_clock_convention"] != "ANALYTICAL_SCENARIO_CLOCK_UTC"
            or manifest["admission_cutoff"] is None
            or manifest["training_information_cutoff"] != manifest["admission_cutoff"]
        ):
            raise ValueError("invalid retrospective provenance")
    elif (
        not manifest["source_business_timezone"]
        or manifest["scenario_clock_timezone"] != manifest["source_business_timezone"]
        or manifest["scenario_clock_convention"] != "OPERATIONAL_BUSINESS_TIMEZONE"
        or manifest["training_information_cutoff"] is None
    ):
        raise ValueError("invalid fixture provenance")
    if set(manifest["artifacts"]) != names - {"public-manifest.json"}:
        raise ValueError("public artifacts mismatch")
    bodies = {name: _read(root / name) for name in manifest["artifacts"]}
    if any(_sha(body) != manifest["artifacts"][name] for name, body in bodies.items()):
        raise ValueError("public hash mismatch")
    config = manifest["config"]
    if (
        not isinstance(config, dict)
        or "disclosures" in config
        or "temporal_availability_convention" in config
    ):
        raise ValueError("unsafe public configuration")
    public_config = StudyConfig.model_validate_json(
        _json(
            {
                **config,
                "disclosures": ["PUBLIC_SCENARIO"],
                "temporal_availability_convention": "PUBLIC_SCENARIO",
            }
        )
    )
    if (
        public_config.reservations != 0
        or public_config.backlog != 0
        or public_config.costs.ordering_cost is None
        or public_config.costs.holding_cost is None
        or public_config.costs.ordering_cost <= 0
        or public_config.costs.holding_cost <= 0
    ):
        raise ValueError("unsupported public scenario")
    if any(
        config.get(name) != manifest[name]
        for name in (
            "mode",
            "dataset_class",
            "target",
            "reporting_scope",
            "unit",
            "data_version",
            "forecast_run_id",
        )
    ):
        raise ValueError("public configuration mismatch")
    calibration = _decode(bodies["calibration.json"])
    if set(calibration) != {"calibration", "interval_metrics", "eoq"}:
        raise ValueError("invalid public calibration")
    parsed_calibration = CalibrationSet.model_validate_json(_json(calibration["calibration"]))
    eoq = EoqResult.model_validate_json(_json(calibration["eoq"]))
    metrics = [
        IntervalMetrics.model_validate_json(_json(m)) for m in calibration["interval_metrics"]
    ]
    algorithms = ("persistence", "seasonal_naive", "xgboost")
    pair_keys = {(a, h) for a in algorithms for h in (1, 7)}
    entry_map = {(entry.algorithm, entry.horizon): entry for entry in parsed_calibration.entries}
    metric_keys = {(m.algorithm, m.horizon, m.subset) for m in metrics}
    if (
        len(parsed_calibration.entries) != 6
        or set(entry_map) != pair_keys
        or len(metrics) != 12
        or metric_keys != {(a, h, s) for a, h in pair_keys for s in ("all", "monday")}
    ):
        raise ValueError("incomplete public metrics")
    if (
        parsed_calibration.calibration_start,
        parsed_calibration.calibration_end,
        parsed_calibration.evaluation_start,
        parsed_calibration.evaluation_end,
    ) != (
        public_config.calibration_start,
        public_config.calibration_end,
        public_config.evaluation_start,
        public_config.evaluation_end,
    ):
        raise ValueError("public calibration dates mismatch")
    for entry in parsed_calibration.entries:
        errors = sorted(w.residual for w in entry.windows)
        if (
            len(errors) < public_config.minimum_samples
            or any(not value.is_finite() for value in errors)
            or any(
                not (
                    public_config.calibration_start <= w.origin + timedelta(days=1)
                    and w.target_end == w.origin + timedelta(days=entry.horizon)
                    and w.target_end < public_config.calibration_end
                )
                for w in entry.windows
            )
        ):
            raise ValueError("invalid public calibration windows")
        quantiles = {
            str(Decimal(p)): errors[
                int((Decimal(p) * len(errors)).to_integral_value(rounding=ROUND_CEILING)) - 1
            ]
            for p in (".05", ".80", ".90", ".95")
        }
        if dict(entry.quantiles) != quantiles:
            raise ValueError("public calibration quantile mismatch")
    if eoq.state != "ready" or eoq.quantity is None:
        raise ValueError("public EOQ unavailable")
    summaries = _decode(bodies["summaries.json"])
    if not isinstance(summaries, list) or len(summaries) != 36:
        raise ValueError("incomplete public cases")

    def key(item):
        case = item["case"]
        if set(case) != {"algorithm", "horizon", "service", "policy"}:
            raise ValueError("invalid case")
        return (case["algorithm"], case["horizon"], case["service"], case["policy"])

    expected = {
        (a, h, s, p)
        for a in ("persistence", "seasonal_naive", "xgboost")
        for h in (1, 7)
        for s in ("0.80", "0.90", "0.95")
        for p in ("baseline", "proposed")
    }
    cases = {}
    for item in summaries:
        if set(item) != {"case", "initial_on_hand", "initial_pipeline", "summary"}:
            raise ValueError("invalid case summary")
        case = key(item)
        if case in cases or case not in expected:
            raise ValueError("duplicate public case")
        summary = TrajectorySummary.model_validate_json(_json(item["summary"]))
        cases[case] = (item, summary)

    def lines(name, limit):
        raw = bodies[name].splitlines(keepends=True)
        if len(raw) > limit:
            raise ValueError("public row limit")
        return [_decode(line) for line in raw]

    days = defaultdict(list)
    for item in lines("days.jsonl", 50000):
        if set(item) != {"case", "day"} or key(item) not in cases:
            raise ValueError("invalid public day")
        days[key(item)].append(SimulationDay.model_validate_json(_json(item["day"])))
    orders = defaultdict(list)
    for item in lines("orders.jsonl", 50000):
        if set(item) != {"case", "order"} or key(item) not in cases:
            raise ValueError("invalid public order")
        orders[key(item)].append(SimulationOrder.model_validate_json(_json(item["order"])))
    if set(days) != expected:
        raise ValueError("missing public days")
    start = date.fromisoformat(config["evaluation_start"])
    end = date.fromisoformat(config["evaluation_end"])
    count = (end - start).days - 6
    if count <= config["warmup_days"]:
        raise ValueError("invalid public calendar")
    for case, (item, summary) in cases.items():
        records = days[case]
        if len(records) != count or summary.scored_days != count - config["warmup_days"]:
            raise ValueError("public count mismatch")
        if len({o.order_id for o in orders[case]}) != len(orders[case]):
            raise ValueError("duplicate case order")
        order_index = {o.order_id: o for o in orders[case]}
        if set(order_index) != {r.order_id for r in records if r.ordered}:
            raise ValueError("public order set mismatch")
        if item["initial_on_hand"] != public_config.initial_on_hand or item["initial_pipeline"] != [
            o.model_dump(mode="json") for o in public_config.initial_pipeline
        ]:
            raise ValueError("public initial state mismatch")
        if records[0].opening_on_hand != public_config.initial_on_hand:
            raise ValueError("public opening stock mismatch")
        pending = {o.order_id: (o.due_date, o.quantity) for o in public_config.initial_pipeline}
        if len(pending) != len(public_config.initial_pipeline):
            raise ValueError("public initial pipeline mismatch")
        opening_scored = None
        quantile = entry_map[case[0], case[1]].quantiles[case[2]]
        for i, row in enumerate(records):
            if i == public_config.warmup_days:
                opening_scored = (row.opening_on_hand, sum(q for _, q in pending.values()))
            due = [(key, quantity) for key, (when, quantity) in pending.items() if when == row.day]
            for key, _quantity in due:
                del pending[key]
            expected_received = sum(quantity for _, quantity in due)
            expected_position = (
                row.opening_on_hand
                + expected_received
                + sum(quantity for _, quantity in pending.values())
            )
            safety = max(Decimal(0), quantile) if case[3] == "proposed" else Decimal(0)
            reorder = int((row.forecast_mean + safety).to_integral_value(rounding=ROUND_CEILING))
            expected_order = eoq.quantity if expected_position <= reorder and eoq.quantity else 0
            if (
                row.day != start + timedelta(days=i)
                or row.origin != row.day - timedelta(days=1)
                or row.warmup != (i < config["warmup_days"])
                or row.opening_on_hand + row.received != row.fulfilled + row.on_hand_end
                or row.demand != row.fulfilled + row.lost
                or min(
                    row.opening_on_hand,
                    row.received,
                    row.position,
                    row.ordered,
                    row.demand,
                    row.fulfilled,
                    row.lost,
                    row.on_hand_end,
                    row.pipeline_end,
                )
                < 0
                or not row.forecast_mean.is_finite()
                or row.forecast_mean < 0
                or row.received != expected_received
                or row.received_order_ids != tuple(key for key, _quantity in due)
                or row.position != expected_position
                or row.residual_quantile != quantile
                or row.safety_stock != safety
                or row.reorder_point != reorder
                or row.order_quantity != eoq.quantity
                or row.ordered != expected_order
                or row.fulfilled != min(row.opening_on_hand + row.received, row.demand)
            ):
                raise ValueError("public day inconsistent")
            if i and row.opening_on_hand != records[i - 1].on_hand_end:
                raise ValueError("public stock discontinuity")
            if row.ordered:
                order = order_index.get(row.order_id)
                if (
                    order is None
                    or order.quantity != row.ordered
                    or order.ordered_on != row.day
                    or order.due_date != row.day + timedelta(days=case[1])
                    or row.due_date != order.due_date
                ):
                    raise ValueError("public order mismatch")
                if row.order_id in pending:
                    raise ValueError("public order collision")
                pending[row.order_id] = (row.due_date, row.ordered)
            elif row.order_id is not None or row.due_date is not None:
                raise ValueError("public unexpected order")
            if (
                row.pipeline_end != sum(quantity for _, quantity in pending.values())
                or row.ordering_cost != (public_config.costs.ordering_cost if row.ordered else 0)
                or row.holding_cost
                != Decimal(row.on_hand_end) * public_config.costs.holding_cost / 365
            ):
                raise ValueError("public accounting mismatch")
        scored = records[config["warmup_days"] :]
        warmup = records[: config["warmup_days"]]
        demand, fulfilled = sum(r.demand for r in scored), sum(r.fulfilled for r in scored)
        positive_days = sum(r.demand > 0 for r in scored)
        ordering = sum((r.ordering_cost for r in scored), Decimal(0))
        holding = sum((r.holding_cost for r in scored), Decimal(0))
        if (
            summary.demand != sum(r.demand for r in scored)
            or summary.fulfilled != sum(r.fulfilled for r in scored)
            or summary.lost != sum(r.lost for r in scored)
            or summary.closing_on_hand != records[-1].on_hand_end
            or summary.terminal_pipeline != records[-1].pipeline_end
            or (summary.scored_opening_on_hand, summary.scored_opening_pipeline) != opening_scored
            or summary.fill_rate != (Decimal(fulfilled) / demand if demand else None)
            or summary.fill_reason != (None if demand else "ZERO_DEMAND")
            or summary.day_service
            != (
                Decimal(sum(r.demand > 0 and r.lost == 0 for r in scored)) / positive_days
                if positive_days
                else None
            )
            or summary.day_service_reason != (None if positive_days else "NO_POSITIVE_DEMAND_DAYS")
            or summary.stockout_days != sum(r.lost > 0 for r in scored)
            or summary.average_on_hand != Decimal(sum(r.on_hand_end for r in scored)) / len(scored)
            or summary.order_count != sum(r.ordered > 0 for r in scored)
            or summary.receipt_count != sum(len(r.received_order_ids) for r in scored)
            or summary.ordering_cost != ordering
            or summary.holding_cost != holding
            or summary.partial_cost != ordering + holding
            or summary.warmup_demand != sum(r.demand for r in warmup)
            or summary.warmup_fulfilled != sum(r.fulfilled for r in warmup)
            or summary.warmup_lost != sum(r.lost for r in warmup)
            or summary.warmup_ordering_cost != sum((r.ordering_cost for r in warmup), Decimal(0))
            or summary.warmup_holding_cost != sum((r.holding_cost for r in warmup), Decimal(0))
        ):
            raise ValueError("public summary mismatch")
        if any(not x.is_finite() for x in (summary.average_on_hand, summary.partial_cost)):
            raise ValueError("invalid public numeric")
    if include_snapshot:
        return {
            "manifest": manifest,
            "calibration": calibration,
            "summaries": summaries,
            "days": {case: tuple(rows) for case, rows in days.items()},
        }
    return manifest


def publish_failure(config, authorization, root, reason_code):
    """Publish a bounded failure derived from reverified source context."""
    from app.replenishment.inputs import validate_forecast_coverage
    from app.replenishment.schemas import ReplenishmentFailureReceipt

    config = StudyConfig.model_validate_json(config.model_dump_json())
    authorization = type(authorization).model_validate_json(authorization.model_dump_json())
    inputs = load_inputs(
        authorization.forecast_dir, authorization.bundle_path, config, authorization
    )
    try:
        validate_forecast_coverage(
            inputs.forecast.rows, config.evaluation_start, config.evaluation_end
        )
        simulate(inputs, calibrate(inputs, config), config)
    except ValueError as error:
        observed = (
            "INSUFFICIENT_CALIBRATION" if str(error) == "insufficient calibration" else str(error)
        )
    else:
        raise ValueError("failure was not observed") from None
    if reason_code != observed:
        raise ValueError("failure reason mismatch")
    receipt = ReplenishmentFailureReceipt(
        schema_version="replenishment-failure/1",
        attempt_id=uuid.uuid4().hex,
        mode=config.mode,
        dataset_class=config.dataset_class,
        config_sha256=_sha(_json(config)),
        created_at=datetime.now(UTC),
        reason_code=reason_code,
    )
    folder = _owned(Path(root) / config.mode / "failures", must_exist=False)
    folder.mkdir(parents=True, exist_ok=True)
    folder = _owned(folder)
    if len(tuple(folder.iterdir())) >= 100:
        raise ValueError("failure count limit")
    target = folder / (receipt.attempt_id + ".json")
    with target.open("xb") as stream:
        stream.write(_json(receipt))
        stream.flush()
        os.fsync(stream.fileno())
    return target
