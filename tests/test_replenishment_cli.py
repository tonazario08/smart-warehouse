"""Offline CLI must reject incomplete or unadmitted invocations safely."""

import json
import os
import subprocess
import sys


def test_cli_missing_args_is_structured_and_nonzero():
    result = subprocess.run(
        [sys.executable, "-m", "app.replenishment.cli", "run"],
        capture_output=True,
        text=True,
        env=os.environ.copy(),
        timeout=30,
    )
    assert result.returncode == 2
    assert json.loads(result.stderr)["code"] == "INPUT_SCHEMA"
    assert result.stdout == ""


def test_real_owned_fixture_cli_run_verify_publish_requires_opt_in():
    import uuid
    from pathlib import Path

    from app.analytics.export import canonical_json
    from tests.replenishment_helpers import operational_context

    workspace = Path(__file__).resolve().parents[1]
    ident = "cli-fixture-" + uuid.uuid4().hex
    forecast_root = workspace / "artifacts" / "forecasting" / ident
    bundle_root = workspace / "artifacts" / "demand-data" / ident / "bundles"
    output = workspace / "artifacts" / "replenishment" / ident
    forecast_root.mkdir(parents=True, exist_ok=False)
    output.mkdir(parents=True, exist_ok=False)
    bundle, forecast, auth, config = operational_context(forecast_root, bundle_root=bundle_root)
    config_path, auth_path = output / "config.json", output / "authorization.json"
    config_path.write_bytes(canonical_json(config.model_dump(mode="json")))
    auth_path.write_bytes(canonical_json(auth.model_dump(mode="json")))
    env = os.environ.copy()
    for key in ("ANALYTICS_DATABASE_URL", "TEST_DATABASE_URL", "TEST_MIGRATION_DATABASE_URL"):
        env.pop(key, None)

    def invoke(*args):
        return subprocess.run(
            [sys.executable, "-m", "app.replenishment.cli", *map(str, args)],
            capture_output=True,
            text=True,
            env=env,
            timeout=600,
        )

    base = (
        "run",
        "--forecast-dir",
        forecast,
        "--bundle",
        bundle,
        "--config",
        config_path,
        "--authorization",
        auth_path,
        "--output-root",
        output / "runs",
    )
    denied = invoke(*base)
    assert denied.returncode == 3 and json.loads(denied.stderr)["code"] == "INPUT_UNADMITTED"
    assert not (output / "runs").exists()
    from datetime import date

    stale_path = output / "stale-config.json"
    stale_path.write_bytes(
        canonical_json(
            config.model_copy(update={"evaluation_end": date(2023, 2, 1)}).model_dump(mode="json")
        )
    )
    stale = invoke(
        "run",
        "--forecast-dir",
        forecast,
        "--bundle",
        bundle,
        "--config",
        stale_path,
        "--authorization",
        auth_path,
        "--output-root",
        output / "stale-runs",
        "--allow-fixture",
    )
    assert stale.returncode == 2 and json.loads(stale.stderr)["code"] == "FORECAST_STALE"
    assert not (output / "stale-runs").exists()
    created = invoke(*base, "--allow-fixture")
    assert created.returncode == 0, created.stderr
    run_id = json.loads(created.stdout)["run_id"]
    run = output / "runs" / run_id
    denied = invoke("verify", "--run-dir", run, "--authorization", auth_path)
    assert denied.returncode == 3 and json.loads(denied.stderr)["code"] == "INPUT_UNADMITTED"
    checked = invoke("verify", "--run-dir", run, "--authorization", auth_path, "--allow-fixture")
    assert checked.returncode == 0 and json.loads(checked.stdout)["run_id"] == run_id
    denied = invoke(
        "publish",
        "--run-dir",
        run,
        "--authorization",
        auth_path,
        "--catalog-root",
        output / "catalog",
    )
    assert denied.returncode == 3 and not (output / "catalog").exists()
    published = invoke(
        "publish",
        "--run-dir",
        run,
        "--authorization",
        auth_path,
        "--catalog-root",
        output / "catalog",
        "--allow-fixture",
    )
    assert published.returncode == 0 and json.loads(published.stdout)["run_id"] == run_id
    reconciled = subprocess.run(
        [
            sys.executable,
            "-m",
            "tests.reconcile_replenishment_run",
            "--run-dir",
            str(run),
            "--forecast-dir",
            str(forecast),
            "--bundle",
            str(bundle),
            "--config",
            str(config_path),
            "--authorization",
            str(auth_path),
        ],
        capture_output=True,
        text=True,
        env=env,
        timeout=600,
    )
    assert reconciled.returncode == 0, reconciled.stderr
    assert json.loads(reconciled.stdout) == {"status": "reconciled", "cases": 36, "days": 6408}
