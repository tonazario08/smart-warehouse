from datetime import UTC, date, datetime, time, timedelta

from app.analytics.export import publish_bundle
from app.analytics.schemas import Admission
from app.analytics.semantics import prepare_dataset
from tests.demand_data_helpers import admission_values, batch, event, software


def fixture_config(
    root, count=6, quantity=1, namespace_override=None, no_policy=False, masked_day=None
):
    from app.cold_start.schemas import ColdStartConfig, Partition, SkuInput, Snapshot

    start = date(2026, 1, 1)
    end = start + timedelta(days=36)
    items = []
    for i in range(count):
        product = f"product-{i}"
        values = admission_values()
        values.update(
            business_timezone="UTC",
            window_start=start,
            window_end=end,
            cutoff=datetime(2026, 2, 10, tzinfo=UTC),
        )
        values["source"]["availability_policy_ref"] = None if no_policy else "fixture-policy"
        if namespace_override is not None and i == 0:
            values["source"]["namespace"] = namespace_override
        values["mappings"] = (
            {
                **values["mappings"][0],
                "product_key": product,
                "valid_from": start,
                "valid_to": end,
                "available_at": datetime(2025, 12, 1, tzinfo=UTC),
            },
        )
        values["coverage"] = tuple(
            {
                "source_product": "p1",
                "source_warehouse": "w1",
                "business_date": start + timedelta(days=j),
                "status": "unknown" if j == masked_day else "complete",
                "available_at": datetime.combine(start + timedelta(days=j + 1), time.min, UTC),
            }
            for j in range(36)
        )
        records = (
            tuple(
                event(
                    event_id=f"e-{j}",
                    quantity=quantity,
                    occurred_at=datetime.combine(start + timedelta(days=j), time(12), UTC),
                    available_at=datetime.combine(start + timedelta(days=j), time(13), UTC),
                )
                for j in range(36)
            )
            if quantity
            else ()
        )
        bundle = publish_bundle(
            prepare_dataset(Admission(**values), batch(*records), software()), root
        )
        items.append(
            SkuInput(
                bundle_path=bundle.path.name,
                data_version=bundle.data_version,
                product_key=product,
                warehouse_key="warehouse-1",
                unit="cái",
                split="train" if i < count - 2 else ("validation" if i == count - 2 else "holdout"),
                snapshot=Snapshot(
                    category="a", supplier="s", available_at=datetime(2025, 12, 1, tzinfo=UTC)
                ),
            )
        )
    return ColdStartConfig(
        skus=tuple(items),
        partitions=(
            Partition(name="train", start=start, end=start + timedelta(days=11)),
            Partition(
                name="validation", start=start + timedelta(days=12), end=start + timedelta(days=23)
            ),
            Partition(
                name="holdout", start=start + timedelta(days=24), end=end - timedelta(days=1)
            ),
        ),
        created_at=datetime(2026, 2, 10, tzinfo=UTC),
    )
