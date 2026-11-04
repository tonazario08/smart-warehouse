import json

import pytest

from app.analytics.export import publish_bundle
from app.forecasting.artifacts import (
    publish_run,
    publish_selection,
    verify_run,
    verify_selection,
)
from app.forecasting.dataset import load_dataset
from app.forecasting.evaluation import evaluate_holdout, tune
from tests.forecasting_helpers import config
from tests.test_demand_data_export import reported_prepared


def _resealed_public_copy(source, parent, transform, *, empty_metrics=False):
    import hashlib
    import shutil

    from app.analytics.export import canonical_json
    from app.forecasting.evaluation import score

    target = parent / source.parent.name / source.name
    target.parent.mkdir(parents=True)
    shutil.copytree(source, target)
    manifest_path = target / "public-manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    rows = [json.loads(line) for line in (target / "predictions.jsonl").read_bytes().splitlines()]
    rows = transform(rows)
    body = b"".join(canonical_json(row) for row in rows)
    (target / "predictions.jsonl").write_bytes(body)
    manifest["row_count"] = len(rows)
    manifest["origin_start"] = min((row["origin"] for row in rows), default=None)
    manifest["origin_end"] = max((row["origin"] for row in rows), default=None)
    manifest["artifacts"]["predictions.jsonl"] = hashlib.sha256(body).hexdigest()
    if empty_metrics:
        metrics = {
            f"{algorithm}:{horizon}": score(()).model_dump(mode="json")
            for horizon in manifest["horizons"]
            for algorithm in ("persistence", "seasonal_naive", "xgboost")
        }
        metrics_body = canonical_json(metrics)
        (target / "metrics.json").write_bytes(metrics_body)
        manifest["artifacts"]["metrics.json"] = hashlib.sha256(metrics_body).hexdigest()
    identity = {key: value for key, value in manifest.items() if key != "projection_sha256"}
    manifest["projection_sha256"] = hashlib.sha256(canonical_json(identity)).hexdigest()
    manifest_path.write_bytes(canonical_json(manifest))
    return target


def _shift_rows(rows, offset):
    from datetime import date

    for row in rows:
        row["origin"] = (date.fromisoformat(row["origin"]) + offset).isoformat()
        row["target_date"] = (date.fromisoformat(row["target_date"]) + offset).isoformat()
    return rows


def _resealed_private_copy(source, parent, transform):
    import hashlib
    import shutil

    from app.analytics.export import canonical_json

    parent.mkdir(parents=True)
    staged = parent / "staged"
    shutil.copytree(source, staged)
    manifest_path = staged / "manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    rows = [json.loads(line) for line in (staged / "predictions.jsonl").read_bytes().splitlines()]
    body = b"".join(canonical_json(row) for row in transform(rows))
    (staged / "predictions.jsonl").write_bytes(body)
    manifest["artifacts"]["predictions.jsonl"] = hashlib.sha256(body).hexdigest()
    identity = {key: value for key, value in manifest.items() if key != "run_id"}
    manifest["run_id"] = "frv1-" + hashlib.sha256(canonical_json(identity)).hexdigest()
    manifest_path.write_bytes(canonical_json(manifest))
    target = parent / manifest["run_id"]
    staged.rename(target)
    return target


@pytest.fixture(scope="module")
def synthetic_selection(tmp_path_factory):
    root = tmp_path_factory.mktemp("forecast-selection")
    bundle = publish_bundle(reported_prepared(), root / "bundle")
    cfg = config(data_version=bundle.data_version)
    dataset = load_dataset(bundle.path, cfg, allow_fixture=True)
    return root, dataset, tune(dataset, cfg)


def test_selection_is_immutable_reusable_and_model_hashes_are_checked(synthetic_selection):
    root, dataset, selection = synthetic_selection
    output = root / "output"
    published = publish_selection(selection, output, dataset=dataset)
    original = {
        p.relative_to(published.path): p.read_bytes()
        for p in published.path.rglob("*")
        if p.is_file()
    }
    assert (
        verify_selection(published.path, dataset=dataset).selection.data_version
        == dataset.config.data_version
    )
    assert publish_selection(selection, output, dataset=dataset).path == published.path
    assert {
        p.relative_to(published.path): p.read_bytes()
        for p in published.path.rglob("*")
        if p.is_file()
    } == original
    model = next(p for p in published.path.rglob("*.json") if p.parent.name == "models")
    assert json.loads(model.read_text(encoding="utf-8"))
    model.write_bytes(model.read_bytes() + b" ")
    with pytest.raises(ValueError):
        verify_selection(published.path, dataset=dataset)
    model.write_bytes(original[model.relative_to(published.path)])


def test_unsafe_workspace_root_is_rejected(synthetic_selection, monkeypatch):
    from pathlib import Path

    _, dataset, selection = synthetic_selection
    original = Path.mkdir

    def prevent_unapproved_write(path, *args, **kwargs):
        if path == Path.cwd() / "unapproved-output":
            raise AssertionError("attempted unapproved write")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", prevent_unapproved_write)
    with pytest.raises(ValueError, match="unsafe"):
        publish_selection(selection, Path.cwd() / "unapproved-output", dataset=dataset)


def test_selection_lock_limit_unknown_file_and_interruption_cleanup(
    synthetic_selection, monkeypatch
):
    from pathlib import Path

    import app.forecasting.artifacts as artifacts

    root, dataset, selection = synthetic_selection
    locked = root / "locked"
    locked.mkdir()
    (locked / ".publish.lock").write_text("other", encoding="ascii")
    with pytest.raises(ValueError, match="busy"):
        publish_selection(selection, locked, dataset=dataset)
    assert sorted(p.name for p in locked.iterdir()) == [".publish.lock"]
    with monkeypatch.context() as context:
        context.setattr(artifacts, "MAX_ARTIFACT_BYTES", 64)
        with pytest.raises(ValueError, match="too large"):
            publish_selection(selection, root / "oversized", dataset=dataset)
    selected = publish_selection(selection, root / "unknown", dataset=dataset)
    extra = selected.path / "unexpected.txt"
    extra.write_text("extra", encoding="utf-8")
    with pytest.raises(ValueError, match="file set"):
        verify_selection(selected.path, dataset=dataset)
    extra.unlink()
    destination = root / "interrupted"
    original = Path.open

    def interrupted(path, *args, **kwargs):
        if path.name == "validation.json" and args and args[0] == "xb":
            raise OSError("synthetic interruption")
        return original(path, *args, **kwargs)

    with monkeypatch.context() as context:
        context.setattr(Path, "open", interrupted)
        with pytest.raises(OSError):
            publish_selection(selection, destination, dataset=dataset)
    assert list(destination.iterdir()) == []


def test_private_evaluation_and_public_projection_are_distinct_and_checked(synthetic_selection):
    import subprocess
    import sys

    from app.forecasting.artifacts import publish_catalog
    from app.forecasting.repository import verify_catalog_run

    root, dataset, selection = synthetic_selection
    selected = publish_selection(selection, root / "selection-output", dataset=dataset)
    verified = verify_selection(selected.path, dataset=dataset)
    evaluated = evaluate_holdout(dataset, verified.selection)
    run = publish_run(evaluated, root / "runs", dataset=dataset, selection=verified)
    original = verify_run(run.path)
    assert original.run_id == run.run_id
    assert len(list((run.path / "models").glob("*.json"))) == 8
    catalog = root / "catalog"
    projected = publish_catalog(original, catalog, dataset=dataset, selection=verified)
    assert projected == run.run_id
    public = verify_catalog_run(catalog / "research" / run.run_id, allow_fixture=True)
    assert public.manifest.dataset_class == "fixture"
    from datetime import timedelta

    outside = _resealed_public_copy(
        catalog / "research" / run.run_id,
        root / "shifted-eval",
        lambda rows: _shift_rows(rows, timedelta(days=365)),
    )
    with pytest.raises(ValueError):
        verify_catalog_run(outside, allow_fixture=True)
    empty = _resealed_public_copy(
        catalog / "research" / run.run_id, root / "empty-eval", lambda rows: [], empty_metrics=True
    )
    assert verify_catalog_run(empty, allow_fixture=True).rows == ()
    assert set(p.name for p in (catalog / "research" / run.run_id).iterdir()) == {
        "public-manifest.json",
        "predictions.jsonl",
        "metrics.json",
    }
    assert not list((catalog / "research" / run.run_id).rglob("models"))
    with pytest.raises(ValueError):
        verify_catalog_run(catalog / "research" / run.run_id)
    code = """
import importlib.metadata, sys
original = importlib.metadata.version
def version(name):
    if name.lower() in {'xgboost', 'numpy', 'scipy'}:
        raise importlib.metadata.PackageNotFoundError(name)
    return original(name)
importlib.metadata.version = version
from app.forecasting.repository import verify_catalog_run
result = verify_catalog_run(sys.argv[1], allow_fixture=True)
assert result.manifest.dataset_class == 'fixture'
from pathlib import Path
from types import SimpleNamespace
from fastapi.testclient import TestClient
from app.auth.dependencies import get_current_user
from app.core.config import Settings
from app.main import create_app
from app.models import UserRole
settings = Settings(app_env='test', database_url='sqlite+pysqlite:///:memory:',
    jwt_secret_key='test-only-jwt-secret-with-at-least-32-characters',
    forecast_catalog_root=Path(sys.argv[1]).parent.parent, forecast_allow_fixture=True,
    _env_file=None)
application = create_app(settings)
application.dependency_overrides[get_current_user] = lambda: SimpleNamespace(role=UserRole.ADMIN)
with TestClient(application) as client:
    response = client.get('/api/v1/forecasts/status?mode=research')
    assert response.status_code == 200
    assert response.json()['latest']['fixture_label'] == 'Dữ liệu kiểm thử'
    assert client.get('/api/v1/forecasts/runs/' + result.manifest.run_id).status_code == 200
    prediction = client.get('/api/v1/forecasts/runs/' + result.manifest.run_id +
        '/predictions?horizon=7&algorithm=xgboost&page=1&page_size=2')
    assert prediction.status_code == 200
    assert len(prediction.json()['items']) == 2
assert 'xgboost' not in sys.modules and 'numpy' not in sys.modules and 'scipy' not in sys.modules
"""
    process = subprocess.run(
        [sys.executable, "-c", code, str(catalog / "research" / run.run_id)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert process.returncode == 0, process.stderr
    import hashlib

    from app.analytics.export import canonical_json

    public_path = catalog / "research" / run.run_id
    predictions = public_path / "predictions.jsonl"
    lines = predictions.read_bytes().splitlines()
    first = json.loads(lines[0])
    first["prediction"] += 1
    body = canonical_json(first) + b"".join(line + b"\n" for line in lines[1:])
    predictions.write_bytes(body)
    manifest_path = public_path / "public-manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    manifest["artifacts"]["predictions.jsonl"] = hashlib.sha256(body).hexdigest()
    identity = {key: value for key, value in manifest.items() if key != "projection_sha256"}
    manifest["projection_sha256"] = hashlib.sha256(canonical_json(identity)).hexdigest()
    manifest_path.write_bytes(canonical_json(manifest))
    with pytest.raises(ValueError, match="metrics"):
        verify_catalog_run(public_path, allow_fixture=True)


def test_private_evaluation_round_trip_and_run_tamper(synthetic_selection):
    root, dataset, selection = synthetic_selection
    selected = publish_selection(selection, root / "selection-output", dataset=dataset)
    verified = verify_selection(selected.path, dataset=dataset)
    evaluated = evaluate_holdout(dataset, verified.selection)
    run = publish_run(evaluated, root / "private-runs", dataset=dataset, selection=verified)
    assert verify_run(run.path).run_id == run.run_id
    from datetime import timedelta

    shifted = _resealed_private_copy(
        run.path, root / "private-eval-shifted", lambda rows: _shift_rows(rows, timedelta(days=365))
    )
    with pytest.raises(ValueError):
        verify_run(shifted)
    assert publish_run(evaluated, root / "private-runs", dataset=dataset, selection=verified).reused
    predictions = run.path / "predictions.jsonl"
    original = predictions.read_bytes()
    predictions.write_bytes(original + b" ")
    with pytest.raises(ValueError):
        verify_run(run.path)


def test_cli_synthetic_tune_evaluate_verify_publish_and_failure(synthetic_selection):
    import os
    import subprocess
    import sys

    from app.analytics.export import canonical_json
    from tests.forecasting_helpers import config

    root, dataset, _ = synthetic_selection
    source_root = root / "bundle"
    bundle = source_root / dataset.config.data_version
    config_file = root / "config.json"
    config_file.write_bytes(canonical_json(config(data_version=dataset.config.data_version)))
    env = os.environ.copy()
    env["FORECAST_APPROVED_BUNDLE_ROOT"] = str(source_root)

    def run(*arguments):
        return subprocess.run(
            [sys.executable, "-m", "app.forecasting.cli", *map(str, arguments)],
            capture_output=True,
            text=True,
            env=env,
            timeout=600,
        )

    denied = run(
        "tune", "--bundle", bundle, "--config", config_file, "--output-root", root / "denied"
    )
    assert denied.returncode == 3
    assert json.loads(denied.stderr)["code"] == "INPUT_UNADMITTED"
    mismatched = root / "mismatched-config.json"
    mismatched.write_bytes(
        canonical_json(config(data_version=dataset.config.data_version, dataset_class="research"))
    )
    invalid = run(
        "tune", "--bundle", bundle, "--config", mismatched, "--output-root", root / "invalid"
    )
    assert invalid.returncode == 2

    selection_root = root / "cli-selection"
    tuned = run(
        "tune",
        "--bundle",
        bundle,
        "--config",
        config_file,
        "--output-root",
        selection_root,
        "--allow-fixture",
    )
    assert tuned.returncode == 0, tuned.stderr
    selection = selection_root / json.loads(tuned.stdout)["selection_id"]
    runs = root / "cli-runs"
    evaluated = run(
        "evaluate",
        "--bundle",
        bundle,
        "--selection-dir",
        selection,
        "--output-root",
        runs,
        "--allow-fixture",
    )
    assert evaluated.returncode == 0, evaluated.stderr
    run_path = runs / json.loads(evaluated.stdout)["run_id"]
    assert run("verify", "--run-dir", run_path, "--allow-fixture").returncode == 0
    assert run("verify", "--run-dir", run_path).returncode == 3
    published = run(
        "publish",
        "--bundle",
        bundle,
        "--selection-dir",
        selection,
        "--run-dir",
        run_path,
        "--catalog-root",
        root / "cli-catalog",
        "--allow-fixture",
    )
    assert published.returncode == 0, published.stderr
    bad_binding = root / "invalid-binding.json"
    bad_binding.write_text("{}", encoding="utf-8")
    failed = run(
        "forecast",
        "--bundle",
        bundle,
        "--selection-dir",
        selection,
        "--output-root",
        runs,
        "--binding",
        bad_binding,
        "--origin",
        "2022-02-01",
        "--allow-fixture",
    )
    assert failed.returncode == 2
    receipt = next((runs / "attempts").glob("*.json"))
    assert (
        run(
            "publish-failure", "--attempt", receipt, "--catalog-root", root / "cli-catalog"
        ).returncode
        == 3
    )
    result = run(
        "publish-failure",
        "--attempt",
        receipt,
        "--catalog-root",
        root / "cli-catalog",
        "--allow-fixture",
    )
    assert result.returncode == 0, result.stderr
    missing = run("verify", "--run-dir", root / "missing", "--allow-fixture")
    assert missing.returncode == 5 and json.loads(missing.stderr)["code"] == "IO_UNAVAILABLE"

    # Inject only the fitting boundary; the CLI still verifies the real synthetic bundle.
    for exception, expected, code in (
        ("ValueError('no eligible train or validation windows')", 3, "INPUT_UNADMITTED"),
        ("RuntimeError('private exception data')", 6, "FIT_FAILED"),
    ):
        script = """
import sys
import app.forecasting.evaluation as evaluation
def fail(*args, **kwargs):
    raise EXCEPTION
evaluation.tune = fail
from app.forecasting.cli import main
raise SystemExit(main(sys.argv[1:]))
""".replace("EXCEPTION", exception)
        failure = subprocess.run(
            [
                sys.executable,
                "-c",
                script,
                "tune",
                "--bundle",
                str(bundle),
                "--config",
                str(config_file),
                "--output-root",
                str(root / f"failure-{expected}"),
                "--allow-fixture",
            ],
            capture_output=True,
            text=True,
            env=env,
            timeout=600,
        )
        assert failure.returncode == expected
        assert json.loads(failure.stderr)["code"] == code
        assert "private exception data" not in failure.stderr
    publication = """
import sys
import app.forecasting.artifacts as artifacts
def fail(*args, **kwargs):
    raise ValueError('publication busy')
artifacts.publish_selection = fail
from app.forecasting.cli import main
raise SystemExit(main(sys.argv[1:]))
"""
    conflict = subprocess.run(
        [
            sys.executable,
            "-c",
            publication,
            "tune",
            "--bundle",
            str(bundle),
            "--config",
            str(config_file),
            "--output-root",
            str(root / "failure-4"),
            "--allow-fixture",
        ],
        capture_output=True,
        text=True,
        env=env,
        timeout=600,
    )
    assert conflict.returncode == 4 and json.loads(conflict.stderr)["code"] == "OUTPUT_CONFLICT"
    assert "private conflict data" not in conflict.stderr


def test_operational_fixture_cli_forecast_public_binding_and_freshness(tmp_path):
    import os
    import subprocess
    import sys
    from datetime import UTC, date, datetime, timedelta
    from types import SimpleNamespace

    from fastapi.testclient import TestClient

    from app.analytics.export import canonical_json
    from app.analytics.schemas import Admission, DailyRecord
    from app.analytics.semantics import prepare_dataset
    from app.auth.dependencies import get_current_user
    from app.core.config import Settings
    from app.db.session import get_session
    from app.forecasting.schemas import ForecastConfig, OperationalBinding, Partition
    from app.main import create_app
    from app.models import Product, UserRole, Warehouse
    from tests.demand_data_helpers import admission_values, batch, software
    from tests.forecasting_helpers import config

    start, end = date(2020, 1, 1), date(2022, 3, 2)
    values = admission_values(
        window_start=start,
        window_end=end,
        coverage=(),
        business_timezone="UTC",
        cutoff=datetime(2022, 3, 2, tzinfo=UTC),
    )
    values["source"].update(representation="daily", availability_policy_ref="fixture-policy")
    values["mappings"][0].update(
        valid_from=start, valid_to=end, unit="unit", available_at=datetime(2019, 12, 31, tzinfo=UTC)
    )
    records = []
    day = start
    while day < end:
        records.append(
            DailyRecord(
                observation_id="day:" + day.isoformat(),
                source_product="p1",
                source_warehouse="w1",
                unit="unit",
                business_date=day,
                quantity=2,
                coverage="complete",
                available_at=datetime.combine(day + timedelta(days=1), datetime.min.time(), UTC),
            )
        )
        day += timedelta(days=1)
    source_root = tmp_path / "bundles"
    bundle = publish_bundle(
        prepare_dataset(Admission(**values), batch(*records), software()), source_root
    )
    binding = OperationalBinding(
        schema_version="forecast-binding/1",
        data_version=bundle.data_version,
        product_key="product-1",
        warehouse_key="warehouse-1",
        product_id=1,
        warehouse_id=2,
        unit="unit",
        approved_at=datetime(2019, 12, 31, tzinfo=UTC),
        available_at=datetime(2019, 12, 31, tzinfo=UTC),
        permission_ref="synthetic-private",
    )
    partitions = (
        Partition(name="train", start=start, end=date(2021, 1, 1)),
        Partition(name="validation", start=date(2021, 1, 1), end=date(2022, 1, 1)),
        Partition(name="final_holdout", start=date(2022, 1, 1), end=end),
    )
    cfg = config(
        mode="operational",
        data_version=bundle.data_version,
        target="gross_fulfilled_units",
        reporting_scope="warehouse",
        knowledge_time_mode="historical_as_of",
        unit="unit",
        binding=binding,
        business_timezone="UTC",
        partitions=partitions,
    )
    payload = cfg.model_dump()
    payload["protocol"].update(
        train_information_cutoff=datetime(2021, 1, 1, tzinfo=UTC),
        selection_information_cutoff=datetime(2022, 1, 1, tzinfo=UTC),
        refit_information_cutoff=datetime(2022, 1, 1, tzinfo=UTC),
    )
    cfg = ForecastConfig.model_validate(payload)
    config_file, binding_file = tmp_path / "config.json", tmp_path / "binding.json"
    config_file.write_bytes(canonical_json(cfg))
    binding_file.write_bytes(canonical_json(binding))
    env = os.environ.copy()
    env["FORECAST_APPROVED_BUNDLE_ROOT"] = str(source_root)

    def invoke(*args):
        result = subprocess.run(
            [sys.executable, "-m", "app.forecasting.cli", *map(str, args)],
            capture_output=True,
            text=True,
            env=env,
            timeout=600,
        )
        assert result.returncode == 0, result.stderr
        return json.loads(result.stdout)

    selections, runs, catalog = tmp_path / "selection", tmp_path / "runs", tmp_path / "catalog"
    selection_id = invoke(
        "tune",
        "--bundle",
        bundle.path,
        "--config",
        config_file,
        "--output-root",
        selections,
        "--allow-fixture",
    )["selection_id"]
    selection = selections / selection_id
    run_id = invoke(
        "forecast",
        "--bundle",
        bundle.path,
        "--selection-dir",
        selection,
        "--output-root",
        runs,
        "--binding",
        binding_file,
        "--origin",
        "2022-03-01",
        "--allow-fixture",
    )["run_id"]
    run_path = runs / run_id
    assert len(list((run_path / "models").glob("*.json"))) == 8
    rows = [
        json.loads(line)
        for line in (run_path / "predictions.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert len(rows) == 24 and all(row["actual"] is None for row in rows)
    for case, transform in (
        ("private-missing", lambda items: [row for row in items if row["horizon"] == 1]),
        ("private-empty", lambda items: []),
        (
            "private-before-training",
            lambda items: _shift_rows(items, date(2020, 12, 31) - date(2022, 3, 1)),
        ),
    ):
        modified = _resealed_private_copy(run_path, tmp_path / case, transform)
        with pytest.raises(ValueError):
            verify_run(modified)
    invoke(
        "publish",
        "--bundle",
        bundle.path,
        "--selection-dir",
        selection,
        "--run-dir",
        run_path,
        "--catalog-root",
        catalog,
        "--allow-fixture",
    )
    public = catalog / "operational" / run_id
    assert "synthetic-private" not in (public / "binding.json").read_text(encoding="utf-8")

    class Session:
        unit = "unit"

        def get(self, model, identifier):
            if model is Product and identifier == 1:
                return SimpleNamespace(id=1, name="Fixture", sku="renamed", unit=self.unit)
            if model is Warehouse and identifier == 2:
                return SimpleNamespace(id=2, name="Fixture warehouse", code="RENAMED")
            return None

    session = Session()
    from app.forecasting.repository import ForecastRepository, verify_catalog_run
    from app.forecasting.service import ForecastService

    projected = verify_catalog_run(public, allow_fixture=True)
    for case, transform in (
        ("missing", lambda items: [row for row in items if row["horizon"] == 1]),
        ("empty", lambda items: []),
        (
            "before-training",
            lambda items: _shift_rows(items, date(2020, 12, 31) - date(2022, 3, 1)),
        ),
    ):
        modified = _resealed_public_copy(public, tmp_path / case, transform)
        with pytest.raises(ValueError):
            verify_catalog_run(modified, allow_fixture=True)
    fresh = ForecastService(
        ForecastRepository(catalog, allow_fixture=True),
        session,
        clock=lambda: datetime(2022, 3, 2, 12, tzinfo=UTC),
    )._view(projected)
    assert fresh["stale"] is False
    settings = Settings(
        app_env="test",
        database_url="sqlite+pysqlite:///:memory:",
        jwt_secret_key="test-only-jwt-secret",
        forecast_catalog_root=catalog,
        forecast_allow_fixture=True,
        _env_file=None,
    )
    app = create_app(settings)
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(role=UserRole.WAREHOUSE)
    app.dependency_overrides[get_session] = lambda: session
    with TestClient(app) as client:
        detail = client.get("/api/v1/forecasts/runs/" + run_id)
        assert detail.status_code == 200 and detail.json()["fixture_label"] == "Dữ liệu kiểm thử"
        assert detail.json()["stale"] is True
        assert "synthetic-private" not in detail.text
        session.unit = "changed"
        assert client.get("/api/v1/forecasts/runs/" + run_id).status_code == 409


def test_independent_reconciler_calendar_baselines_and_metrics():
    from datetime import date, timedelta

    from tests.reconcile_forecasting_run import expected_windows, metric_report, validate_rows

    start = date(2022, 1, 1)
    days = {start + timedelta(days=i): i % 5 for i in range(-28, 20)}
    days[start + timedelta(days=3)] = None
    windows = expected_windows(days, start, start + timedelta(days=10), 7)
    assert not windows  # missing target excludes all four possible origins
    days[start + timedelta(days=3)] = 0
    windows = expected_windows(days, start, start + timedelta(days=10), 7)
    assert len(windows) == 4
    origin, history, targets = windows[0]
    rows = []
    for algorithm in ('persistence', 'seasonal_naive', 'xgboost'):
        for lead, (day, actual) in enumerate(targets, 1):
            prediction = history[-1] if algorithm == 'persistence' else history[-8 + lead]
            rows.append(dict(
                series_key='series', origin=origin.isoformat(), target_date=day.isoformat(),
                lead=lead, horizon=7, algorithm=algorithm, prediction=prediction,
                actual=actual, unit='unit',
            ))
    validate_rows(rows, windows[:1], 7, 'series', 'unit')
    rows[0]['prediction'] += 1
    with pytest.raises(ValueError):
        validate_rows(rows, windows[:1], 7, 'series', 'unit')
    report = metric_report([dict(series_key='series', origin='2022-01-01', actual=0, prediction=2)])
    assert report['mae'] == 2 and report['wape'] is None
    assert report['wape_reason'] == 'ZERO_ACTUAL_TOTAL'
    assert report['origin_total_mae'] == 2 and report['per_series']['series'] == [1, 2, None]


def test_independent_reconciler_detects_metric_and_population_tampering():
    from tests.reconcile_forecasting_run import compare_metrics, metric_report

    rows = [dict(series_key='s', origin='2022-01-01', actual=2, prediction=1),
            dict(series_key='s', origin='2022-01-01', actual=0, prediction=3)]
    expected = metric_report(rows)
    assert expected['count'] == 2 and expected['origin_count'] == 1
    assert expected['mae'] == 2 and expected['wape'] == 2 and expected['origin_total_mae'] == 2
    compare_metrics(expected, expected)
    for key in ('count', 'origin_count', 'mae', 'wape', 'origin_total_mae', 'per_series'):
        changed = dict(expected)
        changed[key] = {} if key == 'per_series' else 99
        with pytest.raises(ValueError):
            compare_metrics(changed, expected)


def test_independent_reconciler_against_verified_synthetic_run(synthetic_selection, monkeypatch):
    from tests.reconcile_forecasting_run import reconcile

    root, dataset, selection = synthetic_selection
    selected = publish_selection(selection, root / 'selected-for-reconcile', dataset=dataset)
    verified = verify_selection(selected.path, dataset=dataset)
    result = evaluate_holdout(dataset, verified.selection)
    run = publish_run(result, root / 'artifacts' / 'forecasting' / 'runs',
                      dataset=dataset, selection=verified)
    bundle = root / 'bundle' / dataset.config.data_version
    monkeypatch.setenv('FORECAST_APPROVED_BUNDLE_ROOT', str(bundle.parent))
    monkeypatch.chdir(root)
    with pytest.raises(ValueError):
        reconcile(bundle, run.path)
    summary = reconcile(bundle, run.path, allow_fixture=True)
    assert summary['run_id'] == run.run_id
    assert summary['counts']['final_holdout:1'] == sum(
        row.horizon == 1 and row.algorithm == 'persistence' for row in result.rows
    )
    assert summary['calendar_days'] == len(dataset.observations)
    def change_baseline(rows):
        next(row for row in rows if row['algorithm'] == 'persistence')['prediction'] += 1
        return rows

    altered = _resealed_private_copy(
        run.path, root / 'artifacts' / 'forecasting' / 'tampered', change_baseline
    )
    with pytest.raises(ValueError):
        reconcile(bundle, altered, allow_fixture=True)
    monkeypatch.setenv('FORECAST_APPROVED_BUNDLE_ROOT', str(bundle))
    with pytest.raises(ValueError):
        reconcile(bundle, run.path, allow_fixture=True)
