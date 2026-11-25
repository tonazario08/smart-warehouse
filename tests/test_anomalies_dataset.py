import math

import pytest

from app.anomalies.dataset import load_anomaly_dataset
from app.anomalies.features import build_feature_snapshot
from tests.anomalies_helpers import bundle, config


def test_feature_history_is_known_and_seven_complete_days(tmp_path):
    published = bundle(tmp_path)
    snapshot = build_feature_snapshot(
        load_anomaly_dataset(config(published.data_version), published.path)
    )
    first = snapshot.samples[0]
    assert first.event_id == "e7"
    assert first.values == pytest.approx(
        (math.log1p(8), 12 / 23, 3 / 6, math.log1p(4), math.log1p(7), math.log1p(8 / 5))
    )


def test_missing_coverage_is_not_zero(tmp_path):
    published = bundle(tmp_path, missing_day=0)
    snapshot = build_feature_snapshot(
        load_anomaly_dataset(config(published.data_version), published.path)
    )
    assert all(not sample.event_id == "e7" for sample in snapshot.samples)
    assert snapshot.exclusions["MISSING_COVERAGE"] >= 1


def test_fixture_requires_explicit_opt_in(tmp_path):
    published = bundle(tmp_path)
    with pytest.raises(ValueError):
        load_anomaly_dataset(
            config(published.data_version).model_copy(update={"allow_fixture": False}),
            published.path,
        )


def test_future_events_do_not_change_prior_features(tmp_path):
    published = bundle(tmp_path)
    dataset = load_anomaly_dataset(config(published.data_version), published.path)
    before = build_feature_snapshot(dataset)
    changed = dataset.model_copy(
        update={
            "events": dataset.events
            + (dataset.events[-1].model_copy(update={"event_id": "future", "quantity": 2000}),)
        }
    )
    after = build_feature_snapshot(changed)
    assert [s for s in before.samples if s.event_id == "e7"] == [
        s for s in after.samples if s.event_id == "e7"
    ]


def test_unknown_past_movement_is_not_a_known_zero(tmp_path):
    published = bundle(tmp_path)
    dataset = load_anomaly_dataset(config(published.data_version), published.path)
    unknown = dataset.events[0].model_copy(update={"event_id": "unknown", "kind": "unknown"})
    dataset = dataset.model_copy(update={"events": dataset.events + (unknown,)})
    snapshot = build_feature_snapshot(dataset)
    assert all(sample.event_id != "e7" for sample in snapshot.samples)


def test_nontarget_event_is_excluded_from_scoring(tmp_path):
    published = bundle(tmp_path, include_inbound=True)
    dataset = load_anomaly_dataset(config(published.data_version), published.path)
    result = build_feature_snapshot(dataset)
    assert all(s.event_id != "inbound" for s in result.samples)
    assert result.exclusions["NON_TARGET"] == 1


def test_same_day_event_does_not_enter_history(tmp_path):
    published = bundle(tmp_path)
    dataset = load_anomaly_dataset(config(published.data_version), published.path)
    before = build_feature_snapshot(dataset)
    extra = dataset.events[7].model_copy(update={"event_id": "same-day", "quantity": 999})
    after = build_feature_snapshot(dataset.model_copy(update={"events": dataset.events + (extra,)}))
    assert next(s.values for s in before.samples if s.event_id == "e7") == next(
        s.values for s in after.samples if s.event_id == "e7"
    )


def test_coverage_must_be_known_at_event_information_time(tmp_path):
    from datetime import timedelta

    published = bundle(tmp_path)
    dataset = load_anomaly_dataset(config(published.data_version), published.path)
    proof = dataset.admission.coverage[0].model_copy(
        update={"available_at": dataset.events[7].available_at + timedelta(seconds=1)}
    )
    admission = dataset.admission.model_copy(
        update={"coverage": (proof,) + dataset.admission.coverage[1:]}
    )
    snapshot = build_feature_snapshot(dataset.model_copy(update={"admission": admission}))
    assert all(s.event_id != "e7" for s in snapshot.samples)


def test_complete_empty_day_is_valid_zero(tmp_path):
    published = bundle(tmp_path)
    dataset = load_anomaly_dataset(config(published.data_version), published.path)
    dataset = dataset.model_copy(
        update={"events": tuple(e for e in dataset.events if e.event_id != "e0")}
    )
    sample = next(s for s in build_feature_snapshot(dataset).samples if s.event_id == "e7")
    assert sample.values[3] == pytest.approx(math.log1p(27 / 7))
    assert sample.values[4] == pytest.approx(math.log1p(6))


def test_config_before_admission_cutoff_is_rejected(tmp_path):
    from datetime import timedelta

    published = bundle(tmp_path)
    cfg = config(published.data_version).model_copy(
        update={"created_at": config(published.data_version).created_at - timedelta(days=1)}
    )
    with pytest.raises(ValueError):
        load_anomaly_dataset(cfg, published.path)


def test_extreme_date_rejected():
    from datetime import UTC, date, datetime

    from app.anomalies.schemas import Partition

    with pytest.raises(ValueError):
        Partition(
            name="train",
            start=date.min,
            end=date(1, 1, 2),
            information_cutoff=datetime(2, 1, 1, tzinfo=UTC),
        )


def test_simultaneous_multiseries_events_are_canonical_and_labels_bound(tmp_path):
    from app.anomalies.schemas import Label

    published = bundle(tmp_path, multi=True)
    cfg = config(published.data_version).model_copy(
        update={
            "labels": (
                Label(
                    namespace="fixture",
                    product_key="product-2",
                    warehouse_key="warehouse-2",
                    unit="cái",
                    event_id="second-e7",
                    label="anomaly",
                ),
            )
        }
    )
    result = build_feature_snapshot(load_anomaly_dataset(cfg, published.path))
    events = [s for s in result.samples if s.event_id in ("e7", "second-e7")]
    assert len(events) == 2
    assert [s.source_record_key for s in events] == sorted(s.source_record_key for s in events)
    assert {s.event_id: s.label for s in events} == {"e7": None, "second-e7": "anomaly"}
