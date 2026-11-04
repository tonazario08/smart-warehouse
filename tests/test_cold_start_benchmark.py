from app.cold_start.benchmark import evaluate_cold_start
from app.cold_start.dataset import load_fixture_dataset
from tests.cold_start_helpers import fixture_config


def test_zero_is_a_prediction_and_wape_has_zero_denominator(tmp_path):
    cfg = fixture_config(tmp_path, quantity=0)
    result = evaluate_cold_start(load_fixture_dataset(cfg, tmp_path))
    assert result.metrics["1"].compared > 0
    assert result.metrics["1"].wape is None
    assert any(p.prediction == 0 for p in result.predictions)


def test_fewer_than_three_references_has_no_prediction(tmp_path):
    cfg = fixture_config(tmp_path, count=4)
    result = evaluate_cold_start(load_fixture_dataset(cfg, tmp_path))
    assert all(p.prediction is None for p in result.predictions)


def test_holdout_values_and_future_reference_values_do_not_change_predictions(tmp_path):
    cfg = fixture_config(tmp_path)
    ds = load_fixture_dataset(cfg, tmp_path)
    original = evaluate_cold_start(ds)
    changed = []
    for s in ds.series:
        rows = tuple(
            r.model_copy(update={"value": 99}) if s.sku.split == "holdout" else r
            for r in s.observations
        )
        changed.append(s.model_copy(update={"observations": rows}))
    altered = evaluate_cold_start(ds.model_copy(update={"series": tuple(reversed(changed))}))
    assert original.predictions == altered.predictions
    assert original.selected_k == altered.selected_k


def test_late_snapshot_and_masked_reference_are_excluded(tmp_path):
    from datetime import UTC, datetime

    cfg = fixture_config(tmp_path, count=5)
    ds = load_fixture_dataset(cfg, tmp_path)
    changed = []
    for s in ds.series:
        if s.sku.product_key == "product-0":
            snapshot = s.sku.snapshot.model_copy(
                update={"available_at": datetime(2026, 1, 20, tzinfo=UTC)}
            )
            s = s.model_copy(update={"sku": s.sku.model_copy(update={"snapshot": snapshot})})
        changed.append(s)
    result = evaluate_cold_start(ds.model_copy(update={"series": tuple(changed)}))
    assert all(p.prediction is None for p in result.predictions)

    changed = []
    for s in ds.series:
        if s.sku.product_key == "product-0":
            s = s.model_copy(
                update={
                    "observations": tuple(
                        r.model_copy(update={"value": None}) for r in s.observations
                    )
                }
            )
        changed.append(s)
    result = evaluate_cold_start(ds.model_copy(update={"series": tuple(changed)}))
    assert all(p.prediction is None for p in result.predictions)


def test_report_provenance_timing_and_counts_are_typed_and_order_independent(tmp_path):
    cfg = fixture_config(tmp_path)
    ds = load_fixture_dataset(cfg, tmp_path)
    report = evaluate_cold_start(ds)
    assert report.namespace == "fixture"
    assert report.target == "gross_fulfilled_units"
    assert report.unit == "cái" and report.warehouse_key == "warehouse-1"
    assert [p.data_version for p in report.provenance] == [s.sku.data_version for s in ds.series]
    assert all(len(p.snapshot_digest) == 64 for p in report.provenance)
    assert report.train_cutoff < report.validation_cutoff <= report.created_at
    assert (
        report.metrics["1"].excluded_prediction
        == report.metrics["1"].samples - report.metrics["1"].predicted
    )
    assert all(
        p.confidence in ("cluster", "category", "all_train", "unavailable")
        for p in report.predictions
    )
    reordered = ds.model_copy(
        update={
            "series": tuple(reversed(ds.series)),
            "config": cfg.model_copy(update={"skus": tuple(reversed(cfg.skus))}),
        }
    )
    assert report.model_dump_json() == evaluate_cold_start(reordered).model_dump_json()


def test_reference_availability_exact_cutoff_and_one_microsecond_late(tmp_path):
    from datetime import timedelta

    from app.cold_start.benchmark import cutoff, total

    ds = load_fixture_dataset(fixture_config(tmp_path), tmp_path)
    s = ds.series[0]
    origin = s.observations[10].day

    def with_time(t):
        return s.model_copy(
            update={
                "observations": tuple(
                    r.model_copy(update={"available_at": t}) if r.day == origin else r
                    for r in s.observations
                )
            }
        )

    assert total(with_time(cutoff(origin)), origin, 1) == 1
    assert total(with_time(cutoff(origin) + timedelta(microseconds=1)), origin, 1) is None


def test_no_training_snapshots_has_typed_unavailable_reason(tmp_path):
    from datetime import UTC, datetime

    import pytest

    from app.cold_start.benchmark import ColdStartUnavailable

    cfg = fixture_config(tmp_path)
    changed = tuple(
        s.model_copy(
            update={
                "snapshot": s.snapshot.model_copy(
                    update={"available_at": datetime(2026, 1, 20, tzinfo=UTC)}
                )
            }
        )
        if s.split == "train"
        else s
        for s in cfg.skus
    )
    ds = load_fixture_dataset(cfg.model_copy(update={"skus": changed}), tmp_path)
    with pytest.raises(ColdStartUnavailable) as exc:
        evaluate_cold_start(ds)
    assert exc.value.reason_code == "NO_ELIGIBLE_TRAINING_SNAPSHOTS"


def test_future_reference_values_and_late_validation_actuals_cannot_affect_prior_outputs(tmp_path):
    from datetime import timedelta

    from app.cold_start.benchmark import cutoff

    ds = load_fixture_dataset(fixture_config(tmp_path), tmp_path)
    original = evaluate_cold_start(ds)
    boundary = ds.config.partitions[2].start + timedelta(days=4)
    changed = []
    for s in ds.series:
        rows = []
        for r in s.observations:
            if s.sku.split == "train" and r.day >= boundary:
                r = r.model_copy(update={"value": 999})
            if s.sku.split == "validation" and r.day >= ds.config.partitions[1].start:
                r = r.model_copy(
                    update={
                        "value": 999,
                        "available_at": cutoff(ds.config.partitions[1].end)
                        + timedelta(microseconds=1),
                    }
                )
            rows.append(r)
        changed.append(s.model_copy(update={"observations": tuple(rows)}))
    result = evaluate_cold_start(ds.model_copy(update={"series": tuple(changed)}))
    for old, new in zip(original.predictions, result.predictions, strict=True):
        if old.origin < boundary:
            assert old == new
    assert result.selection_reason == "no_common_validation_samples"


def test_extreme_partition_dates_do_not_overflow(tmp_path):
    from datetime import UTC, date, datetime, time, timedelta

    ds = load_fixture_dataset(fixture_config(tmp_path), tmp_path)
    end = date.max - timedelta(days=2)
    parts = tuple(
        p.model_copy(
            update={
                "start": end - timedelta(days=35 - i * 12),
                "end": end - timedelta(days=24 - i * 12),
            }
        )
        for i, p in enumerate(ds.config.partitions)
    )
    cfg = ds.config.model_copy(
        update={
            "partitions": parts,
            "created_at": datetime.combine(end + timedelta(days=1), time.min, UTC),
        }
    )
    report = evaluate_cold_start(ds.model_copy(update={"config": cfg}))
    assert report.metrics["7"].samples == 6


def test_missing_metadata_is_no_result_and_cluster_ties_are_deterministic(tmp_path):
    from app.cold_start.benchmark import fit

    ds = load_fixture_dataset(fixture_config(tmp_path), tmp_path)
    changed = []
    for s in ds.series:
        if s.sku.split == "holdout":
            snapshot = s.sku.snapshot.model_copy(update={"category": None, "supplier": None})
            s = s.model_copy(update={"sku": s.sku.model_copy(update={"snapshot": snapshot})})
        changed.append(s)
    report = evaluate_cold_start(ds.model_copy(update={"series": tuple(changed)}))
    assert all(
        p.reason == "insufficient_metadata" and p.confidence == "unavailable"
        for p in report.predictions
    )
    assert fit([(0, 0), (0, 0)], 2) is None
    assert fit([(0, 0), (2, 0), (1, 0)], 2) == ((0.5, 0.0), (2.0, 0.0))
