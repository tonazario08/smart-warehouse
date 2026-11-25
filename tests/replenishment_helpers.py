"""Builders for explicitly synthetic replenishment verification."""

import json
import os
import subprocess
import sys
from datetime import UTC, date, datetime, timedelta


def fixture_binding(data_version, *, product_id=1, warehouse_id=2):
    from app.forecasting.schemas import OperationalBinding

    return OperationalBinding(
        schema_version="forecast-binding/1",
        data_version=data_version,
        product_key="product-1",
        warehouse_key="warehouse-1",
        product_id=product_id,
        warehouse_id=warehouse_id,
        unit="unit",
        approved_at=datetime(2019, 12, 31, tzinfo=UTC),
        available_at=datetime(2019, 12, 31, tzinfo=UTC),
        permission_ref="synthetic-private",
    )


def operational_evaluation(tmp_path, *, bundle_root=None, product_id=1, warehouse_id=2):
    from app.analytics.export import canonical_json, publish_bundle
    from app.analytics.schemas import Admission, DailyRecord
    from app.analytics.semantics import prepare_dataset
    from app.forecasting.schemas import ForecastConfig, Partition
    from tests.demand_data_helpers import admission_values, batch, software
    from tests.forecasting_helpers import config

    start, end = date(2020, 1, 1), date(2023, 1, 1)
    values = admission_values(
        window_start=start,
        window_end=end,
        coverage=(),
        business_timezone="UTC",
        cutoff=datetime(2023, 1, 2, tzinfo=UTC),
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
    bundle_root = bundle_root or tmp_path / "bundles"
    bundle = publish_bundle(
        prepare_dataset(Admission(**values), batch(*records), software()), bundle_root
    )
    binding = fixture_binding(bundle.data_version, product_id=product_id, warehouse_id=warehouse_id)
    partitions = tuple(
        Partition(name=name, start=date(year, 1, 1), end=date(year + 1, 1, 1))
        for name, year in (("train", 2020), ("validation", 2021), ("final_holdout", 2022))
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
    config_file = tmp_path / "config.json"
    config_file.write_bytes(canonical_json(cfg))
    env = os.environ.copy()
    for key in ("ANALYTICS_DATABASE_URL", "TEST_DATABASE_URL", "TEST_MIGRATION_DATABASE_URL"):
        env.pop(key, None)
    env["FORECAST_APPROVED_BUNDLE_ROOT"] = str(bundle_root)
    for key in (
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS",
        "NUMEXPR_NUM_THREADS",
    ):
        env[key] = "1"

    def invoke(*args):
        process = subprocess.Popen(
            [sys.executable, "-m", "app.forecasting.cli", *map(str, args), "--allow-fixture"],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            output, error = process.communicate(timeout=600)
        except subprocess.TimeoutExpired:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=15,
                    check=False,
                )
            else:
                process.kill()
            process.communicate()
            raise AssertionError("fixture CLI timed out") from None
        if process.returncode:
            raise AssertionError("fixture CLI failed: " + error[:500])
        return json.loads(output)

    selections, runs, catalog = tmp_path / "selection", tmp_path / "runs", tmp_path / "catalog"
    selection = (
        selections
        / invoke(
            "tune", "--bundle", bundle.path, "--config", config_file, "--output-root", selections
        )["selection_id"]
    )
    run = (
        runs
        / invoke(
            "evaluate", "--bundle", bundle.path, "--selection-dir", selection, "--output-root", runs
        )["run_id"]
    )
    invoke("verify", "--run-dir", run)
    invoke(
        "publish",
        "--run-dir",
        run,
        "--catalog-root",
        catalog,
        "--bundle",
        bundle.path,
        "--selection-dir",
        selection,
    )
    return bundle.path, catalog / "operational" / run.name


def operational_context(tmp_path, *, bundle_root=None, product_id=1, warehouse_id=2):
    """Build a genuine fixture evaluation and strict M7 authorization/config."""
    import hashlib
    from datetime import date
    from decimal import Decimal

    from app.forecasting.repository import verify_catalog_run
    from app.replenishment.schemas import CostInputs, InputAuthorization, StudyConfig

    bundle, forecast = operational_evaluation(
        tmp_path, bundle_root=bundle_root, product_id=product_id, warehouse_id=warehouse_id
    )
    public = verify_catalog_run(forecast, allow_fixture=True)

    def sha(p):
        return hashlib.sha256(p.read_bytes()).hexdigest()

    hashes = {
        n: sha(bundle / n)
        for n in ("manifest.json", "observations.jsonl", "quality.json", "records.jsonl")
    }
    public_hash = sha(forecast / "public-manifest.json")
    auth = InputAuthorization(
        schema_version="replenishment-input-authorization/1",
        mode="operational",
        dataset_class="fixture",
        approved_bundle_root=bundle.parent,
        bundle_path=bundle,
        bundle_hashes=hashes,
        approved_forecast_root=forecast.parent,
        forecast_dir=forecast,
        public_manifest_sha256=public_hash,
        source_manifest_sha256=public.manifest.source_manifest_sha256,
        forecast_run_id=public.manifest.run_id,
        allow_fixture=True,
        expected_fixture_binding=(product_id, warehouse_id, "unit"),
    )
    cfg = StudyConfig(
        schema_version="replenishment-study/1",
        mode="operational",
        dataset_class="fixture",
        target="gross_fulfilled_units",
        reporting_scope="warehouse",
        unit="unit",
        data_version=public.manifest.data_version,
        forecast_run_id=public.manifest.run_id,
        source_manifest_sha256=public.manifest.source_manifest_sha256,
        public_manifest_sha256=public_hash,
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
    return bundle, forecast, auth, cfg
