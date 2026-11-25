import hashlib
from datetime import UTC, date, datetime, timedelta

from app.analytics.export import publish_bundle
from app.analytics.schemas import Admission, EventRecord
from app.analytics.semantics import prepare_dataset
from tests.demand_data_helpers import admission_values, batch, software


def bundle(tmp_path, missing_day=None, include_inbound=False, dense=False, multi=False):
    start = date(2026, 1, 1)
    end = start + timedelta(days=20)
    values = admission_values()
    values.update(
        business_timezone="UTC",
        window_start=start,
        window_end=end,
        cutoff=datetime(2026, 1, 21, tzinfo=UTC),
    )
    values["mappings"] = (
        {
            **values["mappings"][0],
            "valid_from": start,
            "valid_to": end,
            "available_at": datetime(2025, 12, 31, tzinfo=UTC),
        },
    )
    values["coverage"] = tuple(
        {
            "source_product": "p1",
            "source_warehouse": "w1",
            "business_date": start + timedelta(days=i),
            "status": "complete",
            "available_at": datetime(2026, 1, 2, tzinfo=UTC) + timedelta(days=i),
        }
        for i in range(20)
        if i != missing_day
    )
    events = tuple(
        EventRecord(
            event_id=f"e{i}",
            source_product="p1",
            source_warehouse="w1",
            unit="cái",
            kind="sale",
            quantity=i + 1,
            occurred_at=datetime(2026, 1, 1, 12, tzinfo=UTC) + timedelta(days=i),
            available_at=datetime(2026, 1, 1, 13, tzinfo=UTC) + timedelta(days=i),
        )
        for i in range(20)
    )
    if multi:
        values["mappings"] += (
            {
                **values["mappings"][0],
                "source_product": "p2",
                "source_warehouse": "w2",
                "product_key": "product-2",
                "warehouse_key": "warehouse-2",
            },
        )
        values["coverage"] += tuple(
            {**proof, "source_product": "p2", "source_warehouse": "w2"}
            for proof in values["coverage"]
        )
        events += tuple(
            event.model_copy(
                update={
                    "event_id": f"second-{event.event_id}",
                    "source_product": "p2",
                    "source_warehouse": "w2",
                }
            )
            for event in events
        )
    if dense:
        events = tuple(
            event.model_copy(
                update={"event_id": f"{event.event_id}-{i}", "quantity": event.quantity + i}
            )
            for event in events
            for i in range(35)
        )
    if include_inbound:
        events += (events[7].model_copy(update={"event_id": "inbound", "kind": "inbound"}),)
    return publish_bundle(
        prepare_dataset(Admission(**values), batch(*events), software()), tmp_path
    )


def config(data_version):
    from app.anomalies.schemas import AnomalyConfig, Partition

    return AnomalyConfig(
        data_version=data_version,
        allow_fixture=True,
        created_at=datetime(2026, 1, 21, tzinfo=UTC),
        partitions=(
            Partition(
                name="train",
                start=date(2026, 1, 8),
                end=date(2026, 1, 12),
                information_cutoff=datetime(2026, 1, 12, tzinfo=UTC),
            ),
            Partition(
                name="validation",
                start=date(2026, 1, 12),
                end=date(2026, 1, 16),
                information_cutoff=datetime(2026, 1, 16, tzinfo=UTC),
            ),
            Partition(
                name="final_holdout",
                start=date(2026, 1, 16),
                end=date(2026, 1, 21),
                information_cutoff=datetime(2026, 1, 21, tzinfo=UTC),
            ),
        ),
    )


def snapshot(constant=False, holdout_offset=0):
    from app.anomalies.schemas import FeatureSnapshot, Sample

    cfg = config("ddv1-" + "a" * 64)
    samples = []
    for part, count, day in (("train", 128, 8), ("validation", 100, 12), ("final_holdout", 3, 16)):
        for i in range(count):
            value = (
                1.0
                if constant
                else float((i % 17) + (holdout_offset if part == "final_holdout" else 0))
            )
            samples.append(
                Sample(
                    source_record_key="aek1-" + hashlib.sha256(f"{part}-{i}".encode()).hexdigest(),
                    event_id=f"{part}-{i}",
                    partition=part,
                    occurred_at=datetime(2026, 1, day, tzinfo=UTC),
                    available_at=datetime(2026, 1, day, tzinfo=UTC),
                    values=(
                        value,
                        (1.0 if constant else i % 17) / 23,
                        (1.0 if constant else i % 7) / 6,
                        value / 10,
                        value / 8,
                        value / 5,
                    ),
                    label="anomaly" if part == "final_holdout" and i == 2 else "normal",
                )
            )
    return FeatureSnapshot(
        config=cfg,
        source_hashes={"source": "b" * 64},
        samples=tuple(sorted(samples, key=lambda s: (s.occurred_at, s.source_record_key))),
        exclusions={},
    )
