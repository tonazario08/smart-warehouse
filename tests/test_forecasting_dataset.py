import hashlib
import json
from datetime import UTC, date, datetime

import pytest

from app.analytics.export import publish_bundle
from app.analytics.schemas import Admission
from app.analytics.semantics import prepare_dataset, prepare_reported_dataset
from app.forecasting.baselines import predict_baseline
from app.forecasting.dataset import load_dataset
from app.forecasting.features import make_windows
from app.forecasting.schemas import OperationalBinding, Partition
from tests.demand_data_helpers import (
    admission_values,
    batch,
    event,
    reported_inputs,
    reported_rows,
    software,
)
from tests.forecasting_helpers import config
from tests.test_demand_data_export import reported_prepared


def test_fixture_requires_opt_in_and_verified_version_preserves_source(tmp_path):
    bundle = publish_bundle(reported_prepared(), tmp_path / "bundles")
    before = {p.name: p.read_bytes() for p in bundle.path.iterdir()}
    cfg = config(data_version=bundle.data_version)
    with pytest.raises(ValueError):
        load_dataset(bundle.path, cfg)
    loaded = load_dataset(bundle.path, cfg, allow_fixture=True)
    assert len(loaded.observations) == 1096
    assert loaded.config.dataset_class == "fixture"
    assert loaded.knowledge_bound == datetime(2026, 10, 20, 8, tzinfo=UTC)
    assert loaded.admission_cutoff == datetime(2026, 10, 23, 8, tzinfo=UTC)
    identity = [
        "fixture:reported",
        "mevgal:product2",
        "mevgal:company",
        "unit",
        "reported_daily_unit_sales",
        "company_aggregate",
    ]
    encoded = json.dumps(identity, ensure_ascii=False, separators=(",", ":")) + "\n"
    assert loaded.series_key == "fsk1-" + hashlib.sha256(encoded.encode()).hexdigest()
    assert {p.name: p.read_bytes() for p in bundle.path.iterdir()} == before
    with pytest.raises(ValueError):
        load_dataset(bundle.path, config(), allow_fixture=True)


def test_operational_binding_must_match_verified_mapping_and_policy(tmp_path):
    values = admission_values()
    values["source"]["availability_policy_ref"] = "fixture-policy"
    prepared = prepare_dataset(Admission(**values), batch(event()), software())
    bundle = publish_bundle(prepared, tmp_path / "bundles")
    binding = OperationalBinding(
        schema_version="forecast-binding/1",
        data_version=bundle.data_version,
        product_key="product-1",
        warehouse_key="warehouse-1",
        product_id=1,
        warehouse_id=1,
        unit="cái",
        approved_at=datetime(2026, 10, 18, tzinfo=UTC),
        available_at=datetime(2026, 10, 18, tzinfo=UTC),
        permission_ref="fixture-permission",
    )
    partitions = tuple(
        Partition(name=name, start=date(2026, 10, day), end=date(2026, 10, day + 1))
        for name, day in (("train", 19), ("validation", 20), ("final_holdout", 21))
    )
    cfg = config(
        mode="operational",
        target="gross_fulfilled_units",
        reporting_scope="warehouse",
        knowledge_time_mode="historical_as_of",
        data_version=bundle.data_version,
        unit="cái",
        binding=binding,
        business_timezone="Asia/Ho_Chi_Minh",
        partitions=partitions,
    )
    assert len(load_dataset(bundle.path, cfg, allow_fixture=True).observations) == 3
    bad = binding.model_copy(update={"warehouse_key": "wrong"})
    with pytest.raises(ValueError, match="binding"):
        load_dataset(bundle.path, cfg.model_copy(update={"binding": bad}), allow_fixture=True)
    unsupported = config(
        mode="operational",
        target="gross_fulfilled_units",
        reporting_scope="warehouse",
        knowledge_time_mode="historical_as_of",
        data_version=bundle.data_version,
        unit="cái",
        binding=binding,
        business_timezone="Asia/Ho_Chi_Minh",
    )
    with pytest.raises(ValueError, match="source"):
        load_dataset(bundle.path, unsupported, allow_fixture=True)


def test_verified_series_identity_is_unambiguous_bounded_and_snapshot_stable(tmp_path):
    def load(product, warehouse, namespace="fixture", snapshot="snapshot-1"):
        values = admission_values()
        values["source"].update(
            namespace=namespace, snapshot_id=snapshot, availability_policy_ref="fixture-policy"
        )
        values["mappings"][0].update(product_key=product, warehouse_key=warehouse)
        bundle = publish_bundle(
            prepare_dataset(Admission(**values), batch(event()), software()), tmp_path / "bundles"
        )
        binding = OperationalBinding(
            schema_version="forecast-binding/1",
            data_version=bundle.data_version,
            product_key=product,
            warehouse_key=warehouse,
            product_id=1,
            warehouse_id=1,
            unit="cái",
            approved_at=datetime(2026, 10, 18, tzinfo=UTC),
            available_at=datetime(2026, 10, 18, tzinfo=UTC),
            permission_ref="fixture-permission",
        )
        partitions = tuple(
            Partition(name=name, start=date(2026, 10, day), end=date(2026, 10, day + 1))
            for name, day in (("train", 19), ("validation", 20), ("final_holdout", 21))
        )
        cfg = config(
            mode="operational",
            target="gross_fulfilled_units",
            reporting_scope="warehouse",
            knowledge_time_mode="historical_as_of",
            data_version=bundle.data_version,
            unit="cái",
            binding=binding,
            business_timezone="Asia/Ho_Chi_Minh",
            partitions=partitions,
        )
        return load_dataset(bundle.path, cfg, allow_fixture=True).series_key

    first = load("a:b", "c")
    encoded = (
        json.dumps(
            ["fixture", "a:b", "c", "cái", "gross_fulfilled_units", "warehouse"],
            ensure_ascii=False,
            separators=(",", ":"),
        )
        + "\n"
    )
    assert first == "fsk1-" + hashlib.sha256(encoded.encode()).hexdigest()
    assert first != load("a", "b:c")
    assert first != load("a:b", "c", namespace="fixture:other")
    assert first == load("a:b", "c", snapshot="snapshot-2")
    assert len(load("p" * 128, "w" * 128)) == 69


def test_verified_large_integer_survives_window_and_baseline_without_rounding(tmp_path):
    exact = 9_007_199_254_740_993
    rows = reported_rows()
    rows[27]["reported_quantity"] = exact
    rows[28]["reported_quantity"] = exact
    bundle = publish_bundle(
        prepare_reported_dataset(*reported_inputs(rows), software()), tmp_path / "bundles"
    )
    loaded = load_dataset(bundle.path, config(data_version=bundle.data_version), allow_fixture=True)
    observation = next(row for row in loaded.observations if row.day == date(2020, 1, 28))
    assert type(observation.value) is int and observation.value == exact
    window = next(w for w in make_windows(loaded, "train", 1) if w.origin == date(2020, 1, 28))
    assert type(window.history_values[-1]) is int and window.history_values[-1] == exact
    assert type(window.target_values[0]) is int and window.target_values[0] == exact
    assert predict_baseline(window, "persistence") == (exact,)
    assert type(predict_baseline(window, "persistence")[0]) is int
