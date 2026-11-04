"""Behavioral checks for authorized source admission."""

import hashlib
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest


def test_authorization_rejects_relative_roots_before_read(tmp_path):
    from app.replenishment.inputs import validate_authorization_paths
    from app.replenishment.schemas import InputAuthorization

    hashes = {
        name: "a" * 64
        for name in ("manifest.json", "observations.jsonl", "quality.json", "records.jsonl")
    }
    auth = InputAuthorization(
        schema_version="replenishment-input-authorization/1",
        mode="research",
        dataset_class="research",
        approved_bundle_root=Path("relative"),
        bundle_path=Path("relative/bundle"),
        bundle_hashes=hashes,
        approved_forecast_root=tmp_path,
        forecast_dir=tmp_path / "run",
        public_manifest_sha256="b" * 64,
        source_manifest_sha256="c" * 64,
        forecast_run_id="frv1-" + "d" * 64,
        allow_fixture=False,
    )
    with pytest.raises(ValueError):
        validate_authorization_paths(auth)


def test_operational_evaluation_fixture_can_feed_replenishment(tmp_path):
    from app.forecasting.repository import verify_catalog_run
    from app.replenishment.inputs import load_inputs
    from app.replenishment.schemas import CostInputs, InputAuthorization, StudyConfig
    from tests.replenishment_helpers import operational_evaluation

    bundle, forecast = operational_evaluation(tmp_path)
    public = verify_catalog_run(forecast, allow_fixture=True)
    assert public.manifest.dataset_class == "fixture"
    assert public.manifest.mode == "operational"
    assert public.manifest.kind == "evaluation"
    assert set(public.manifest.horizons) == {1, 7}
    assert {row.algorithm for row in public.rows} == {"persistence", "seasonal_naive", "xgboost"}
    assert all(row.actual is not None for row in public.rows)
    assert public.binding.product_id == 1 and public.binding.warehouse_id == 2

    def sha(p):
        return hashlib.sha256(p.read_bytes()).hexdigest()

    hashes = {
        name: sha(bundle / name)
        for name in ("manifest.json", "observations.jsonl", "quality.json", "records.jsonl")
    }
    pubhash = sha(forecast / "public-manifest.json")
    auth = InputAuthorization(
        schema_version="replenishment-input-authorization/1",
        mode="operational",
        dataset_class="fixture",
        approved_bundle_root=bundle.parent,
        bundle_path=bundle,
        bundle_hashes=hashes,
        approved_forecast_root=forecast.parent,
        forecast_dir=forecast,
        public_manifest_sha256=pubhash,
        source_manifest_sha256=public.manifest.source_manifest_sha256,
        forecast_run_id=public.manifest.run_id,
        allow_fixture=True,
        expected_fixture_binding=(1, 2, "unit"),
    )
    config = StudyConfig(
        schema_version="replenishment-study/1",
        mode="operational",
        dataset_class="fixture",
        target="gross_fulfilled_units",
        reporting_scope="warehouse",
        unit="unit",
        data_version=public.manifest.data_version,
        forecast_run_id=public.manifest.run_id,
        source_manifest_sha256=public.manifest.source_manifest_sha256,
        public_manifest_sha256=pubhash,
        calibration_start=date(2022, 1, 1),
        calibration_end=date(2022, 7, 1),
        evaluation_start=date(2022, 7, 1),
        evaluation_end=date(2023, 1, 1),
        nominal_coverage=Decimal(".90"),
        service_probabilities=(Decimal(".80"), Decimal(".90"), Decimal(".95")),
        minimum_samples=30,
        lead_times=(1, 7),
        warmup_days=7,
        costs=CostInputs(
            ordering_cost=Decimal("100000"),
            holding_cost=Decimal("20000"),
            currency="VND",
            holding_period="year",
        ),
        initial_on_hand=10000,
        initial_pipeline=(),
        reservations=0,
        backlog=0,
        temporal_availability_convention="synthetic as-of",
        disclosures=("fixture only",),
    )
    inputs = load_inputs(forecast, bundle, config, auth)
    assert len(inputs.forecast.rows) > 1000 and len(inputs.observations) == 1096
    assert inputs.forecast.manifest.run_id == public.manifest.run_id
    from app.replenishment.calibration import calibrate

    calibration = calibrate(inputs, config)
    assert len(calibration.entries) == 6
    assert all(len(entry.windows) >= 30 for entry in calibration.entries)
    assert calibration.annual_demand == Decimal("730")
    altered = tuple(
        row.model_copy(update={"actual": 999})
        if row.target_date >= config.evaluation_start
        else row
        for row in inputs.forecast.rows
    )
    changed = inputs.model_copy(
        update={"forecast": inputs.forecast.model_copy(update={"rows": altered})}
    )
    assert calibrate(changed, config) == calibration
    with pytest.raises(ValueError):
        load_inputs(
            forecast, bundle, config, auth.model_copy(update={"source_manifest_sha256": "0" * 64})
        )
    with pytest.raises(ValueError):
        load_inputs(forecast, bundle, config, auth.model_copy(update={"allow_fixture": False}))
    with pytest.raises(ValueError):
        load_inputs(
            forecast, bundle, config, auth.model_copy(update={"bundle_path": bundle.parent})
        )
    (bundle / "quality.json").write_bytes(b"{}")
    with pytest.raises(ValueError, match="bundle hash mismatch"):
        load_inputs(forecast, bundle, config, auth)


def test_existing_unowned_roots_are_rejected_before_source_read(tmp_path, monkeypatch):
    from app.replenishment.inputs import validate_authorization_paths
    from app.replenishment.schemas import InputAuthorization

    bundle = tmp_path / "bundle"
    forecast = tmp_path / "run"
    bundle.mkdir()
    forecast.mkdir()
    hashes = {
        name: "a" * 64
        for name in ("manifest.json", "observations.jsonl", "quality.json", "records.jsonl")
    }
    auth = InputAuthorization(
        schema_version="replenishment-input-authorization/1",
        mode="research",
        dataset_class="research",
        approved_bundle_root=tmp_path,
        bundle_path=bundle,
        bundle_hashes=hashes,
        approved_forecast_root=tmp_path,
        forecast_dir=forecast,
        public_manifest_sha256="b" * 64,
        source_manifest_sha256="c" * 64,
        forecast_run_id="frv1-" + "d" * 64,
        allow_fixture=False,
    )
    # Research source roots are fixed, even when another directory is readable.
    with pytest.raises(ValueError):
        validate_authorization_paths(auth)


def test_fixture_temp_root_requires_running_test(tmp_path, monkeypatch):
    from app.replenishment.inputs import validate_authorization_paths
    from app.replenishment.schemas import InputAuthorization

    bundle = tmp_path / "bundle"
    forecast = tmp_path / "run"
    bundle.mkdir()
    forecast.mkdir()
    hashes = {
        name: "a" * 64
        for name in ("manifest.json", "observations.jsonl", "quality.json", "records.jsonl")
    }
    auth = InputAuthorization(
        schema_version="replenishment-input-authorization/1",
        mode="operational",
        dataset_class="fixture",
        approved_bundle_root=tmp_path,
        bundle_path=bundle,
        bundle_hashes=hashes,
        approved_forecast_root=tmp_path,
        forecast_dir=forecast,
        public_manifest_sha256="b" * 64,
        source_manifest_sha256="c" * 64,
        forecast_run_id="frv1-" + "d" * 64,
        allow_fixture=True,
        expected_fixture_binding=(1, 2, "unit"),
    )
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    with pytest.raises(ValueError):
        validate_authorization_paths(auth)
