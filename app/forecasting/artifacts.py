"""Immutable offline artifacts; never load executable object formats."""

import getpass
import hashlib
import os
import re
import stat
import tempfile
import uuid
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from app.analytics.export import canonical_json
from app.analytics.ingestion import _bounded_read, _decode_json
from app.analytics.schemas import business_day_bounds
from app.forecasting.baselines import predict_baseline
from app.forecasting.evaluation import (
    EvaluationResult,
    ForecastResult,
    SelectionResult,
    _hash,
    _possible_origins,
    _revalidate,
    _rows,
    score,
)
from app.forecasting.features import make_origin, make_windows
from app.forecasting.models import DirectModels, _predict_with_clips
from app.forecasting.schemas import (
    EvaluationResult as EvaluationMetadata,
)
from app.forecasting.schemas import (
    ForecastConfig,
    ForecastDataset,
    ModelConfig,
    OperationalBinding,
    PredictionRow,
)
from app.forecasting.schemas import (
    ForecastResult as ForecastMetadata,
)

MAX_ARTIFACT_BYTES = 256 * 1024 * 1024


class PublishedSelection(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    selection_id: str
    path: Path
    reused: bool


class VerifiedSelection(BaseModel):
    model_config = ConfigDict(
        extra="forbid", strict=True, frozen=True, arbitrary_types_allowed=True
    )
    selection_id: str
    path: Path
    selection: SelectionResult


class PublishedRun(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    run_id: str
    path: Path
    reused: bool


class VerifiedRun(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    run_id: str
    path: Path
    manifest: dict


def _checked(path: Path, *, must_exist=True) -> Path:
    path = Path(path)
    if ".." in path.parts or str(path).startswith(("\\\\", "//")):
        raise ValueError("unsafe path")
    absolute = path.absolute()
    for part in (*reversed(absolute.parents), absolute):
        if part.exists() or part.is_symlink():
            info = part.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
                raise ValueError("unsafe path")
    return absolute.resolve(strict=must_exist)


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _validate_model(booster, candidate):
    if booster.num_features() != 32 or booster.num_boosted_rounds() != 100:
        raise ValueError("model shape mismatch")
    config = _decode_json(booster.save_config())
    if config["learner"]["objective"]["name"] != candidate.objective:
        raise ValueError("model objective mismatch")

    def walk(node, depth):
        if depth > candidate.max_depth:
            raise ValueError("model depth mismatch")
        if "leaf" in node:
            return
        split = node.get("split", "")
        if not isinstance(split, str) or not re.fullmatch(r"f(?:[0-9]|[12][0-9]|3[01])", split):
            raise ValueError("model feature mismatch")
        children = node.get("children", [])
        if len(children) != 2:
            raise ValueError("model tree mismatch")
        for child in children:
            walk(child, depth + 1)

    for tree in booster.get_dump(dump_format="json"):
        walk(_decode_json(tree), 0)


def _owned_root(path):
    root = _checked(path, must_exist=False)
    workspace = Path(__file__).resolve().parents[2]
    allowed = workspace / "artifacts" / "forecasting"
    pytest_root = Path(tempfile.gettempdir()) / f"pytest-of-{getpass.getuser()}"
    if not root.is_relative_to(allowed) and not root.is_relative_to(pytest_root):
        raise ValueError("unsafe output root")
    return root


def write_failure_receipt(config: ForecastConfig, root: Path, code: str) -> Path:
    from app.forecasting.repository import FailureReceipt

    checked_config = ForecastConfig.model_validate_json(canonical_json(config))
    receipt = FailureReceipt(
        state="failed",
        error_code=code,
        mode=checked_config.mode,
        dataset_class=checked_config.dataset_class,
        reporting_scope=checked_config.reporting_scope,
        config_sha256=_sha(canonical_json(checked_config)),
        created_at=datetime.now(UTC),
        attempt_id=uuid.uuid4().hex,
    )
    folder = _owned_root(Path(root) / "attempts")
    folder.mkdir(parents=True, exist_ok=True)
    folder = _checked(folder)
    path = folder / (receipt.attempt_id + ".json")
    with path.open("xb") as stream:
        stream.write(canonical_json(receipt))
        stream.flush()
        os.fsync(stream.fileno())
    return path


def publish_failure(path: Path, root: Path) -> Path:
    from app.forecasting.repository import FailureReceipt

    path = _checked(path)
    if path.parent.name != "attempts" or _owned_root(path.parent) != path.parent:
        raise ValueError("unsafe receipt")
    body = _bounded_read(path, 4096)
    receipt = FailureReceipt.model_validate_json(body)
    if canonical_json(receipt) != body or path.name != receipt.attempt_id + ".json":
        raise ValueError("invalid receipt")
    folder = _owned_root(Path(root) / receipt.mode / "failures")
    folder.mkdir(parents=True, exist_ok=True)
    folder = _checked(folder)
    target = folder / path.name
    try:
        with target.open("xb") as stream:
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError:
        if _bounded_read(_checked(target), 4096) != body:
            raise ValueError("receipt conflict") from None
    return target


def _selection_contents(selection, dataset):
    _revalidate(dataset, selection)
    config = dataset.config
    files = {}
    if set(selection.models) != set(config.horizons):
        raise ValueError("model horizons mismatch")
    for horizon in config.horizons:
        models = selection.models[horizon]
        if models.candidate != selection.candidates[horizon] or len(models.boosters) != horizon:
            raise ValueError("model shape mismatch")
        for lead, booster in enumerate(models.boosters, 1):
            files[f"models/h{horizon}-l{lead}.json"] = bytes(booster.save_raw(raw_format="json"))
    validation = canonical_json(
        {
            "metrics": {
                str(k): v.model_dump(mode="json") for k, v in selection.validation_metrics.items()
            },
            "candidate_metrics": {
                k: v.model_dump(mode="json") for k, v in selection.candidate_metrics.items()
            },
            "candidate_clips": dict(selection.candidate_clips),
            "candidate_error": dict(selection.candidate_error),
        }
    )
    files["validation.json"] = validation
    identity = {
        "schema_version": "forecast-selection/1",
        "config": config.model_dump(mode="json"),
        "selection": selection.model_dump(mode="json", exclude={"models"}),
        "artifacts": {name: _sha(body) for name, body in files.items()},
    }
    selection_id = "fsv1-" + _sha(canonical_json(identity))
    files["selection.json"] = canonical_json({**identity, "selection_id": selection_id})
    if sum(map(len, files.values())) > MAX_ARTIFACT_BYTES:
        raise ValueError("artifact too large")
    return selection_id, files


def _read_selection(path, dataset, *, require_name=True):
    import xgboost as xgb

    root = _checked(path)
    if not root.is_dir():
        raise ValueError("invalid selection")
    raw = _bounded_read(_checked(root / "selection.json"), MAX_ARTIFACT_BYTES)
    data = _decode_json(raw.decode("utf-8"))
    if set(data) != {"schema_version", "config", "selection", "artifacts", "selection_id"} or (
        data["schema_version"] != "forecast-selection/1" or canonical_json(data) != raw
    ):
        raise ValueError("invalid selection manifest")
    identity = {key: value for key, value in data.items() if key != "selection_id"}
    selection_id = "fsv1-" + _sha(canonical_json(identity))
    if data["selection_id"] != selection_id or (require_name and root.name != selection_id):
        raise ValueError("selection identity mismatch")
    config = ForecastConfig.model_validate_json(canonical_json(data["config"]))
    if config != dataset.config:
        raise ValueError("selection config mismatch")
    expected = {"selection.json", "validation.json", "models"}
    names = {f"h{h}-l{lead}.json" for h in config.horizons for lead in range(1, h + 1)}
    if {p.name for p in root.iterdir()} != expected or (
        {p.name for p in _checked(root / "models").iterdir()} != names
    ):
        raise ValueError("selection file set mismatch")
    artifacts = {"validation.json", *(f"models/{name}" for name in names)}
    if set(data["artifacts"]) != artifacts:
        raise ValueError("selection artifact set mismatch")
    contents, total = {}, len(raw)
    for name in sorted(artifacts):
        body = _bounded_read(_checked(root / name), MAX_ARTIFACT_BYTES - total)
        total += len(body)
        if _sha(body) != data["artifacts"][name]:
            raise ValueError("selection artifact hash mismatch")
        contents[name] = body
    metadata = data["selection"]
    validation = _decode_json(contents["validation.json"].decode("utf-8"))
    expected_validation = {
        "metrics": metadata["validation_metrics"],
        "candidate_metrics": metadata["candidate_metrics"],
        "candidate_clips": metadata["candidate_clips"],
        "candidate_error": metadata["candidate_error"],
    }
    if (
        validation != expected_validation
        or canonical_json(validation) != contents["validation.json"]
    ):
        raise ValueError("validation mismatch")
    # Pydantic parses its strict JSON representation, including numeric map keys and dates.
    from app.forecasting.schemas import SelectionResult as SelectionMetadata

    parsed = SelectionMetadata.model_validate_json(canonical_json(metadata))
    models = {}
    for horizon in config.horizons:
        boosters = []
        for lead in range(1, horizon + 1):
            body = contents[f"models/h{horizon}-l{lead}.json"]
            _decode_json(body.decode("utf-8"))
            booster = xgb.Booster()
            booster.load_model(bytearray(body))
            _validate_model(booster, parsed.candidates[horizon])
            boosters.append(booster)
        models[horizon] = DirectModels(candidate=parsed.candidates[horizon], boosters=boosters)
    selection = SelectionResult(**parsed.model_dump(), models=models)
    _revalidate(dataset, selection)
    for horizon in config.horizons:
        windows = make_windows(dataset, "validation", horizon)
        rows, clips = _rows(dataset, windows, "xgboost", models[horizon])
        key = f"{horizon}:{parsed.candidates[horizon].max_depth}"
        if (
            score(rows) != parsed.validation_metrics[horizon]
            or clips != parsed.candidate_clips[key]
        ):
            raise ValueError("model and validation mismatch")
    return VerifiedSelection(selection_id=selection_id, path=root, selection=selection)


def verify_selection(path: Path, *, dataset: ForecastDataset) -> VerifiedSelection:
    return _read_selection(_owned_root(path), dataset)


def publish_selection(
    selection: SelectionResult, root: Path, *, dataset: ForecastDataset
) -> PublishedSelection:
    selection_id, files = _selection_contents(selection, dataset)
    root = _checked(root, must_exist=False)
    workspace = Path(__file__).resolve().parents[2]
    allowed = workspace / "artifacts" / "forecasting"
    pytest_root = Path(tempfile.gettempdir()) / f"pytest-of-{getpass.getuser()}"
    if not root.is_relative_to(allowed) and not root.is_relative_to(pytest_root):
        raise ValueError("unsafe output root")
    root.mkdir(parents=True, exist_ok=True)
    root = _checked(root)
    lock = root / ".publish.lock"
    token = uuid.uuid4().hex
    try:
        with lock.open("x", encoding="ascii") as stream:
            stream.write(token)
    except FileExistsError:
        raise ValueError("publication busy") from None
    stage = None
    try:
        target = root / selection_id
        if target.exists():
            verified = verify_selection(target, dataset=dataset)
            if verified.selection_id != selection_id or any(
                _checked(target / name).read_bytes() != body for name, body in files.items()
            ):
                raise ValueError("selection conflict")
            return PublishedSelection(selection_id=selection_id, path=target, reused=True)
        stage = root / (".staging-" + uuid.uuid4().hex)
        stage.mkdir(mode=0o700)
        (stage / "models").mkdir(mode=0o700)
        for name, body in files.items():
            with (stage / name).open("xb") as stream:
                stream.write(body)
                stream.flush()
                os.fsync(stream.fileno())
        _read_selection(stage, dataset, require_name=False)
        stage.rename(target)
        stage = None
        return PublishedSelection(selection_id=selection_id, path=target, reused=False)
    finally:
        if stage is not None and stage.exists():
            for name in files:
                path = stage / name
                if path.exists():
                    _checked(path).unlink()
            if (stage / "models").exists():
                _checked(stage / "models").rmdir()
            _checked(stage).rmdir()
        if lock.exists() and _checked(lock).read_text(encoding="ascii") == token:
            lock.unlink()


def _write_owned(root, object_id, files, verify):
    root = _checked(root, must_exist=False)
    workspace = Path(__file__).resolve().parents[2]
    allowed = workspace / "artifacts" / "forecasting"
    pytest_root = Path(tempfile.gettempdir()) / f"pytest-of-{getpass.getuser()}"
    if not root.is_relative_to(allowed) and not root.is_relative_to(pytest_root):
        raise ValueError("unsafe output root")
    root.mkdir(parents=True, exist_ok=True)
    root = _checked(root)
    token = uuid.uuid4().hex
    lock = root / ".publish.lock"
    try:
        with lock.open("x", encoding="ascii") as stream:
            stream.write(token)
    except FileExistsError:
        raise ValueError("publication busy") from None
    stage = None
    try:
        target = root / object_id
        if target.exists():
            verify(target, True)
            for name, body in files.items():
                if name != "receipt.json" and _checked(target / name).read_bytes() != body:
                    raise ValueError("artifact conflict")
            return target, True
        stage = root / (".staging-" + uuid.uuid4().hex)
        stage.mkdir(mode=0o700)
        if any(name.startswith("models/") for name in files):
            (stage / "models").mkdir(mode=0o700)
        for name, body in files.items():
            with (stage / name).open("xb") as stream:
                stream.write(body)
                stream.flush()
                os.fsync(stream.fileno())
        verify(stage, False)
        stage.rename(target)
        stage = None
        return target, False
    finally:
        if stage is not None and stage.exists():
            for name in files:
                candidate = stage / name
                if candidate.exists():
                    _checked(candidate).unlink()
            if (stage / "models").exists():
                _checked(stage / "models").rmdir()
            _checked(stage).rmdir()
        if lock.exists() and _checked(lock).read_text(encoding="ascii") == token:
            lock.unlink()


def _ordered_rows(rows):
    return tuple(
        sorted(
            rows, key=lambda row: (row.horizon, row.algorithm, row.series_key, row.origin, row.lead)
        )
    )


def _validate_rows(rows, config, kind, metric_values):
    if len(rows) > 50000 or tuple(rows) != _ordered_rows(rows):
        raise ValueError("prediction ordering or size")
    groups = {}
    for row in rows:
        if (
            row.horizon not in config.horizons
            or row.unit != config.unit
            or ((row.actual is None) != (kind == "forecast"))
        ):
            raise ValueError("prediction contract")
        key = (row.horizon, row.algorithm, row.series_key, row.origin)
        groups.setdefault(key, []).append(row)
    if kind == "forecast":
        identities = {(row.series_key, row.origin) for row in rows}
        if len(identities) != 1:
            raise ValueError("forecast requires one nonempty series and origin")
        series, origin = next(iter(identities))
        required = {
            (horizon, algorithm, series, origin)
            for horizon in config.horizons
            for algorithm in ("persistence", "seasonal_naive", "xgboost")
        }
        if set(groups) != required:
            raise ValueError("forecast horizon population mismatch")
    else:
        holdout = config.partitions[2]
        if any(not holdout.start <= row.target_date < holdout.end for row in rows):
            raise ValueError("evaluation target outside holdout")
    for (horizon, _algorithm, series, origin), members in groups.items():
        if tuple(row.lead for row in members) != tuple(range(1, horizon + 1)):
            raise ValueError("incomplete horizon group")
        for other in ("persistence", "seasonal_naive", "xgboost"):
            counterpart = groups.get((horizon, other, series, origin))
            if counterpart is None or tuple(r.actual for r in counterpart) != tuple(
                r.actual for r in members
            ):
                raise ValueError("algorithm population mismatch")
    if kind == "evaluation":
        expected = {}
        for horizon in config.horizons:
            for algorithm in ("persistence", "seasonal_naive", "xgboost"):
                members = tuple(
                    row for row in rows if row.horizon == horizon and row.algorithm == algorithm
                )
                expected[f"{algorithm}:{horizon}"] = score(members).model_dump(mode="json")
        if expected != metric_values:
            raise ValueError("metric mismatch")


def _run_contents(result, dataset, selection):
    if not isinstance(result, (EvaluationResult, ForecastResult)):
        raise ValueError("invalid run")
    checked = verify_selection(selection.path, dataset=dataset)
    if checked.selection_id != selection.selection_id:
        raise ValueError("selection mismatch")
    kind = "evaluation" if isinstance(result, EvaluationResult) else "forecast"
    config = dataset.config
    fit_windows = _revalidate(dataset, checked.selection)
    if result.refit_window_hashes != {h: _hash(windows) for h, windows in fit_windows.items()} or (
        result.trained_through
        != max(w.target_dates[-1] for windows in fit_windows.values() for w in windows)
    ):
        raise ValueError("refit window identity mismatch")
    if kind == "forecast" and config.mode != "operational":
        raise ValueError("operational forecast required")
    rows = _ordered_rows(result.rows)
    metrics = (
        {key: value.model_dump(mode="json") for key, value in result.metrics.items()}
        if kind == "evaluation"
        else None
    )
    _validate_rows(rows, config, kind, metrics)
    clip_count = 0
    if kind == "evaluation":
        for horizon in config.horizons:
            expected = make_windows(dataset, "final_holdout", horizon)
            if result.exclusions[horizon] != _possible_origins(config.partitions[2], horizon) - len(
                expected
            ):
                raise ValueError("exclusion mismatch")
            actual = [
                row for row in rows if row.horizon == horizon and row.algorithm == "persistence"
            ]
            if [(row.origin, row.target_date, row.actual) for row in actual] != [
                (window.origin, day, value)
                for window in expected
                for day, value in zip(window.target_dates, window.target_values, strict=True)
            ]:
                raise ValueError("labels do not match verified source")
            for algorithm in ("persistence", "seasonal_naive", "xgboost"):
                expected_rows, clipped = _rows(dataset, expected, algorithm, result.models[horizon])
                clip_count += clipped
                actual_rows = tuple(
                    row for row in rows if row.horizon == horizon and row.algorithm == algorithm
                )
                if actual_rows != expected_rows:
                    raise ValueError("prediction mismatch")
    else:
        origins = {row.origin for row in rows}
        if len(origins) != 1:
            raise ValueError("single origin required")
        origin = next(iter(origins))
        if (
            checked.selection.selection_through >= origin
            or result.trained_through > origin
            or (
                config.protocol.refit_information_cutoff
                > business_day_bounds(origin, config.business_timezone)[1]
            )
        ):
            raise ValueError("forecast time mismatch")
        for horizon in config.horizons:
            item = make_origin(dataset, origin, horizon)
            for algorithm in ("persistence", "seasonal_naive", "xgboost"):
                if algorithm == "xgboost":
                    values, clipped = _predict_with_clips(
                        result.models[horizon], item.history_values, item.target_dates
                    )
                    clip_count += clipped
                else:
                    values = predict_baseline(item, algorithm)
                actual = tuple(
                    row.prediction
                    for row in rows
                    if row.horizon == horizon and row.algorithm == algorithm
                )
                if actual != values:
                    raise ValueError("forecast prediction mismatch")
    if clip_count != result.clips:
        raise ValueError("clip count mismatch")
    contents = {"predictions.jsonl": b"".join(canonical_json(row) for row in rows)}
    if kind == "evaluation":
        contents["metrics.json"] = canonical_json(metrics)
    else:
        contents["binding.json"] = canonical_json(config.binding)
    if set(result.models) != set(config.horizons):
        raise ValueError("missing models")
    for horizon in config.horizons:
        models = result.models[horizon]
        if (
            models.candidate != checked.selection.candidates[horizon]
            or len(models.boosters) != horizon
        ):
            raise ValueError("model mismatch")
        for lead, booster in enumerate(models.boosters, 1):
            contents[f"models/h{horizon}-l{lead}.json"] = bytes(booster.save_raw(raw_format="json"))
    metadata = result.model_dump(mode="json", exclude={"models", "rows", "metrics"})
    identity = {
        "schema_version": "forecast-run/1",
        "kind": kind,
        "selection_id": checked.selection_id,
        "selection_through": checked.selection.selection_through,
        "model_candidates": {
            str(h): candidate.model_dump(mode="json")
            for h, candidate in checked.selection.candidates.items()
        },
        "config": config.model_dump(mode="json"),
        "software_sha256": checked.selection.software_sha256,
        "knowledge_bound": dataset.knowledge_bound,
        "admission_cutoff": dataset.admission_cutoff,
        "result": metadata,
        "artifacts": {name: _sha(body) for name, body in contents.items()},
    }
    run_id = "frv1-" + _sha(canonical_json(identity))
    contents["manifest.json"] = canonical_json({**identity, "run_id": run_id})
    contents["receipt.json"] = canonical_json({"generated_at": datetime.now(UTC)})
    if sum(map(len, contents.values())) > MAX_ARTIFACT_BYTES:
        raise ValueError("run too large")
    return run_id, contents


def _verify_run(path, require_name):
    import xgboost as xgb

    root = _checked(path)
    raw = _bounded_read(_checked(root / "manifest.json"), MAX_ARTIFACT_BYTES)
    manifest = _decode_json(raw.decode("utf-8"))
    keys = {
        "schema_version",
        "kind",
        "selection_id",
        "selection_through",
        "model_candidates",
        "config",
        "software_sha256",
        "knowledge_bound",
        "admission_cutoff",
        "result",
        "artifacts",
        "run_id",
    }
    if (
        set(manifest) != keys
        or manifest["schema_version"] != "forecast-run/1"
        or (
            canonical_json(manifest) != raw
            or manifest["kind"] not in ("evaluation", "forecast")
            or re.fullmatch(r"fsv1-[0-9a-f]{64}", manifest["selection_id"]) is None
            or re.fullmatch(r"[0-9a-f]{64}", manifest["software_sha256"]) is None
        )
    ):
        raise ValueError("invalid run manifest")
    identity = {key: value for key, value in manifest.items() if key != "run_id"}
    run_id = "frv1-" + _sha(canonical_json(identity))
    if manifest["run_id"] != run_id or (require_name and root.name != run_id):
        raise ValueError("run identity mismatch")
    config = ForecastConfig.model_validate_json(canonical_json(manifest["config"]))
    if set(manifest["model_candidates"]) != {str(h) for h in config.horizons}:
        raise ValueError("run candidate set mismatch")
    candidates = {
        int(h): ModelConfig.model_validate_json(canonical_json(candidate))
        for h, candidate in manifest["model_candidates"].items()
    }
    if any(candidate not in config.candidates for candidate in candidates.values()):
        raise ValueError("run candidate mismatch")
    names = {f"h{h}-l{lead}.json" for h in config.horizons for lead in range(1, h + 1)}
    additional = "metrics.json" if manifest["kind"] == "evaluation" else "binding.json"
    if {item.name for item in root.iterdir()} != {
        "manifest.json",
        "receipt.json",
        "predictions.jsonl",
        "models",
        additional,
    } or ({item.name for item in _checked(root / "models").iterdir()} != names):
        raise ValueError("run file set mismatch")
    artifacts = {"predictions.jsonl", additional, *(f"models/{name}" for name in names)}
    if set(manifest["artifacts"]) != artifacts:
        raise ValueError("run artifact set mismatch")
    total = len(raw)
    contents = {}
    for name in sorted(artifacts):
        body = _bounded_read(_checked(root / name), MAX_ARTIFACT_BYTES - total)
        total += len(body)
        if _sha(body) != manifest["artifacts"][name]:
            raise ValueError("run hash mismatch")
        contents[name] = body
    for name in names:
        body = contents[f"models/{name}"]
        _decode_json(body.decode("utf-8"))
        model = xgb.Booster()
        model.load_model(bytearray(body))
        horizon = int(name.split("-")[0][1:])
        _validate_model(model, candidates[horizon])
    rows = tuple(
        PredictionRow.model_validate_json(line)
        for line in contents["predictions.jsonl"].splitlines()
    )
    if b"".join(canonical_json(row) for row in rows) != contents["predictions.jsonl"]:
        raise ValueError("noncanonical predictions")
    value = _decode_json(contents[additional].decode("utf-8"))
    if canonical_json(value) != contents[additional]:
        raise ValueError("noncanonical artifact")
    if manifest["kind"] == "forecast" and (
        config.mode != "operational"
        or OperationalBinding.model_validate_json(contents[additional]) != config.binding
    ):
        raise ValueError("binding mismatch")
    _validate_rows(
        rows, config, manifest["kind"], value if manifest["kind"] == "evaluation" else None
    )
    selection_through = date.fromisoformat(manifest["selection_through"])
    result_data = {**manifest["result"], "rows": [row.model_dump(mode="json") for row in rows]}
    if manifest["kind"] == "evaluation":
        result_data["metrics"] = value
        result_meta = EvaluationMetadata.model_validate_json(canonical_json(result_data))
        part = config.partitions[2]
        if selection_through >= part.start or any(
            not part.start <= row.target_date < part.end for row in rows
        ):
            raise ValueError("evaluation boundary mismatch")
        if set(result_meta.exclusions) != set(config.horizons):
            raise ValueError("exclusion set mismatch")
        for horizon in config.horizons:
            possible = _possible_origins(part, horizon)
            observed = sum(
                row.horizon == horizon and row.algorithm == "persistence" for row in rows
            )
            excluded = result_meta.exclusions[horizon]
            if excluded < 0 or excluded > possible or observed != (possible - excluded) * horizon:
                raise ValueError("exclusion count mismatch")
        source_cutoff = (
            datetime.fromisoformat(manifest["admission_cutoff"].replace("Z", "+00:00"))
            if manifest["admission_cutoff"]
            else None
        )
        source_bound = (
            datetime.fromisoformat(manifest["knowledge_bound"].replace("Z", "+00:00"))
            if manifest["knowledge_bound"]
            else None
        )
        expected_cutoff = (
            config.protocol.refit_information_cutoff
            if config.mode == "operational"
            else source_cutoff
        )
        if (
            result_meta.admission_cutoff,
            result_meta.knowledge_bound,
            result_meta.training_information_cutoff,
        ) != (source_cutoff, source_bound, expected_cutoff):
            raise ValueError("run knowledge time mismatch")
    else:
        result_meta = ForecastMetadata.model_validate_json(canonical_json(result_data))
        if (
            not rows
            or len({row.origin for row in rows}) != 1
            or selection_through >= rows[0].origin
            or (result_meta.trained_through > rows[0].origin)
        ):
            raise ValueError("forecast boundary mismatch")
        if result_meta.training_information_cutoff != config.protocol.refit_information_cutoff or (
            result_meta.training_information_cutoff
            > business_day_bounds(rows[0].origin, config.business_timezone)[1]
        ):
            raise ValueError("forecast cutoff mismatch")
    if result_meta.clips < 0 or result_meta.trained_through >= config.partitions[2].start:
        raise ValueError("invalid run metadata")
    receipt_raw = _bounded_read(_checked(root / "receipt.json"), 1024)
    receipt = _decode_json(receipt_raw.decode("utf-8"))
    if set(receipt) != {"generated_at"}:
        raise ValueError("invalid receipt")
    generated = datetime.fromisoformat(receipt["generated_at"].replace("Z", "+00:00"))
    if generated.utcoffset() != timedelta(0) or canonical_json(receipt) != receipt_raw:
        raise ValueError("receipt requires UTC time")
    return VerifiedRun(run_id=run_id, path=root, manifest=manifest)


def verify_run(path: Path) -> VerifiedRun:
    return _verify_run(_owned_root(path), True)


def publish_run(
    result, root: Path, *, dataset: ForecastDataset, selection: VerifiedSelection
) -> PublishedRun:
    run_id, files = _run_contents(result, dataset, selection)
    path, reused = _write_owned(root, run_id, files, _verify_run)
    return PublishedRun(run_id=run_id, path=path, reused=reused)


def publish_catalog(
    run: VerifiedRun, root: Path, *, dataset: ForecastDataset, selection: VerifiedSelection
) -> str:
    from app.forecasting.repository import verify_catalog_run

    verified = verify_run(run.path)
    selected = verify_selection(selection.path, dataset=dataset)
    manifest = verified.manifest
    config = ForecastConfig.model_validate_json(canonical_json(manifest["config"]))
    if (
        config != dataset.config
        or selected.selection_id != manifest["selection_id"]
        or (selected.selection.software_sha256 != manifest["software_sha256"])
    ):
        raise ValueError("source or selection mismatch")
    kind = manifest["kind"]
    predictions = _bounded_read(_checked(run.path / "predictions.jsonl"), MAX_ARTIFACT_BYTES)
    rows = tuple(PredictionRow.model_validate_json(line) for line in predictions.splitlines())
    import xgboost as xgb

    restored_models = {}
    for horizon in config.horizons:
        boosters = []
        for lead in range(1, horizon + 1):
            body = _bounded_read(
                _checked(run.path / f"models/h{horizon}-l{lead}.json"), MAX_ARTIFACT_BYTES
            )
            booster = xgb.Booster()
            booster.load_model(bytearray(body))
            boosters.append(booster)
        restored_models[horizon] = DirectModels(
            candidate=selected.selection.candidates[horizon], boosters=boosters
        )
    meta = {**manifest["result"], "rows": [row.model_dump(mode="json") for row in rows]}
    if kind == "evaluation":
        metrics_bytes = _bounded_read(_checked(run.path / "metrics.json"), MAX_ARTIFACT_BYTES)
        meta["metrics"] = _decode_json(metrics_bytes.decode("utf-8"))
        parsed = EvaluationMetadata.model_validate_json(canonical_json(meta))
        restored = EvaluationResult(**parsed.model_dump(), models=restored_models)
    else:
        parsed = ForecastMetadata.model_validate_json(canonical_json(meta))
        restored = ForecastResult(**parsed.model_dump(), models=restored_models)
    reconstructed_id, _ = _run_contents(restored, dataset, selected)
    if reconstructed_id != verified.run_id:
        raise ValueError("source and run identity mismatch")
    receipt = _decode_json(_bounded_read(_checked(run.path / "receipt.json"), 1024).decode("utf-8"))
    files = {"predictions.jsonl": predictions}
    public_binding = None
    if config.binding is not None:
        body = canonical_json(config.binding)
        private = _decode_json(body.decode("utf-8"))
        public_binding = {
            name: private[name]
            for name in (
                "product_id",
                "warehouse_id",
                "product_key",
                "warehouse_key",
                "unit",
                "data_version",
                "approved_at",
                "available_at",
            )
        }
        public_binding["binding_sha256"] = _sha(body)
    if kind == "evaluation":
        files["metrics.json"] = _bounded_read(
            _checked(run.path / "metrics.json"), MAX_ARTIFACT_BYTES
        )
    else:
        files["binding.json"] = canonical_json(public_binding)
    result = manifest["result"]
    identity = {
        "schema_version": "forecast-public-run/1",
        "run_id": verified.run_id,
        "source_manifest_sha256": _sha(_checked(run.path / "manifest.json").read_bytes()),
        "kind": kind,
        "mode": config.mode,
        "dataset_class": config.dataset_class,
        "data_version": config.data_version,
        "target": config.target,
        "reporting_scope": config.reporting_scope,
        "unit": config.unit,
        "protocol": config.protocol.model_dump(mode="json"),
        "knowledge_time_mode": config.knowledge_time_mode,
        "business_timezone": config.business_timezone,
        "trained_through": result["trained_through"],
        "training_information_cutoff": result["training_information_cutoff"],
        "knowledge_bound": manifest["knowledge_bound"],
        "admission_cutoff": manifest["admission_cutoff"],
        "origin_start": min((row.origin for row in rows), default=None),
        "origin_end": max((row.origin for row in rows), default=None),
        "horizons": config.horizons,
        "generated_at": receipt["generated_at"],
        "limitations": dataset.limitations,
        "row_count": len(rows),
        "binding": public_binding,
        "artifacts": {name: _sha(body) for name, body in files.items()},
    }
    files["public-manifest.json"] = canonical_json(
        {**identity, "projection_sha256": _sha(canonical_json(identity))}
    )
    path, _ = _write_owned(
        Path(root) / config.mode,
        verified.run_id,
        files,
        lambda p, require_name: verify_catalog_run(
            p, allow_fixture=config.dataset_class == "fixture", require_name=require_name
        ),
    )
    return path.name
