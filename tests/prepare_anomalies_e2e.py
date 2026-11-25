"""Create isolated synthetic M9 catalogs through verified M5 and the real model."""

import argparse
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from app.analytics.export import publish_bundle
from app.analytics.ingestion import checked_path
from app.analytics.schemas import Admission, EventRecord
from app.analytics.semantics import prepare_dataset
from app.anomalies.catalog import publish_run, verify_run
from app.anomalies.dataset import load_anomaly_dataset
from app.anomalies.features import build_feature_snapshot
from app.anomalies.schemas import AnomalyConfig, Label, Partition
from app.anomalies.scoring import fit_and_score
from tests.demand_data_helpers import admission_values, batch, software


def prepare(root: Path):
    root = checked_path(root, must_exist=False)
    workspace = Path(__file__).resolve().parents[1]
    if root.exists() or root.is_relative_to(workspace) or root == Path(root.anchor):
        raise ValueError("new external fixture directory required")
    root.mkdir(parents=False)
    bundles, catalog = root / "bundles", root / "catalog"
    bundles.mkdir()
    catalog.mkdir()
    start, end = date(2026, 1, 1), date(2026, 1, 21)
    values = admission_values()
    values.update(
        business_timezone="UTC",
        window_start=start,
        window_end=end,
        cutoff=datetime(2026, 1, 21, tzinfo=UTC),
    )
    template = {
        **values["mappings"][0],
        "valid_from": start,
        "valid_to": end,
        "available_at": datetime(2025, 12, 31, tzinfo=UTC),
    }
    values["mappings"] = tuple(
        {
            **template,
            "source_product": f"p{k}",
            "source_warehouse": f"w{k}",
            "product_key": f"product-{k}",
            "warehouse_key": f"warehouse-{k}",
        }
        for k in (1, 2)
    )
    values["coverage"] = tuple(
        {
            "source_product": f"p{k}",
            "source_warehouse": f"w{k}",
            "business_date": start + timedelta(days=day),
            "status": "complete",
            "available_at": datetime(2026, 1, 2, tzinfo=UTC) + timedelta(days=day),
        }
        for k in (1, 2)
        for day in range(20)
    )
    events, labels = [], []
    for k in (1, 2):
        for day in range(20):
            for index in range(30):
                event_id = f"fixture-{k}-{day}-{index}"
                injected = (k == 1 and day == 8 and index == 0) or (day >= 16 and index == 0)
                at = datetime(2026, 1, 1, 23 if injected else 12, tzinfo=UTC) + timedelta(
                    days=day, minutes=index
                )
                events.append(
                    EventRecord(
                        event_id=event_id,
                        source_product=f"p{k}",
                        source_warehouse=f"w{k}",
                        unit="cái",
                        kind="sale",
                        quantity=10000 if injected else 1 + (index % 7),
                        occurred_at=at,
                        available_at=at + timedelta(minutes=1),
                    )
                )
                labels.append(
                    Label(
                        namespace="fixture",
                        product_key=f"product-{k}",
                        warehouse_key=f"warehouse-{k}",
                        unit="cái",
                        event_id=event_id,
                        label="anomaly" if injected or (k == 1 and 11 <= day <= 14) else "normal",
                    )
                )
    published = publish_bundle(
        prepare_dataset(Admission(**values), batch(*events), software()), bundles
    )
    parts = tuple(
        Partition(
            name=name,
            start=date(2026, 1, a),
            end=date(2026, 1, b),
            information_cutoff=datetime(2026, 1, b, tzinfo=UTC),
        )
        for name, a, b in (("train", 8, 12), ("validation", 12, 16), ("final_holdout", 16, 20))
    )
    config = AnomalyConfig(
        data_version=published.data_version,
        allow_fixture=True,
        created_at=datetime(2026, 1, 21, tzinfo=UTC),
        partitions=parts,
        labels=tuple(labels),
    )
    result = fit_and_score(build_feature_snapshot(load_anomaly_dataset(config, published.path)))
    if result.state != "available":
        raise ValueError("fixture model unavailable")
    available = publish_run(result, catalog)
    if not any(
        a.explanation.state == "available" for a in verify_run(catalog, available).payload.alerts
    ):
        raise ValueError("fixture has no actual SHAP explanation")
    import shap

    original = shap.ExactExplainer

    def fail(*args, **kwargs):
        raise RuntimeError("synthetic explainer failure")

    try:
        shap.ExactExplainer = fail
        unavailable = publish_run(result, catalog)
    finally:
        shap.ExactExplainer = original
    if not any(
        a.explanation.reason == "EXPLAINER_ERROR"
        for a in verify_run(catalog, unavailable).payload.alerts
    ):
        raise ValueError("fixture failure path missing")
    empty_events = tuple(
        event.model_copy(
            update={
                "quantity": 4,
                "occurred_at": event.occurred_at.replace(hour=12),
                "available_at": event.available_at.replace(hour=12),
            }
        )
        for event in events
        if int(event.event_id.rsplit("-", 1)[1]) < 20
    )
    empty_bundle = publish_bundle(
        prepare_dataset(Admission(**values), batch(*empty_events), software()), bundles
    )
    empty_labels = tuple(
        label.model_copy(update={"label": "normal"})
        for label in labels
        if int(label.event_id.rsplit("-", 1)[1]) < 20
    )
    empty_config = AnomalyConfig.model_validate(
        config.model_copy(
            update={"data_version": empty_bundle.data_version, "labels": empty_labels}
        ).model_dump()
    )
    empty_result = fit_and_score(
        build_feature_snapshot(load_anomaly_dataset(empty_config, empty_bundle.path))
    )
    empty = publish_run(empty_result, catalog)
    if verify_run(catalog, empty).payload.alerts:
        raise ValueError("empty fixture unexpectedly produced alerts")
    print(f"available={available}\nunavailable={unavailable}\nempty={empty}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--root", type=Path, required=True, help="New external directory owned by runner"
    )
    args = parser.parse_args()
    prepare(args.root)


if __name__ == "__main__":
    main()
