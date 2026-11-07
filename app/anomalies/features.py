"""Build temporal features using only evidence known at the event's information time."""

import hashlib
import math
from collections import Counter
from datetime import UTC, timedelta

from app.analytics.export import canonical_json
from app.anomalies.schemas import AnomalyDataset, FeatureSnapshot, Sample


def build_feature_snapshot(dataset: AnomalyDataset) -> FeatureSnapshot:
    admission, config = dataset.admission, dataset.config
    labels = {
        (x.namespace, x.product_key, x.warehouse_key, x.unit, x.event_id): x.label
        for x in config.labels
    }
    samples, exclusions = [], Counter()
    ordered = sorted(
        dataset.events,
        key=lambda e: (e.occurred_at, e.source_product, e.source_warehouse, e.unit, e.event_id),
    )
    for event in ordered:
        day = event.occurred_at.astimezone(UTC).date()
        partition = next((p for p in config.partitions if p.start <= day < p.end), None)
        if partition is None:
            continue
        if admission.source.kind_map[event.kind] != "customer_fulfillment":
            exclusions["NON_TARGET"] += 1
            continue
        if event.available_at is None or event.available_at > partition.information_cutoff:
            exclusions["EVENT_UNAVAILABLE"] += 1
            continue
        info = event.available_at
        mapping = next(
            (
                m
                for m in admission.mappings
                if m.source_product == event.source_product
                and m.source_warehouse == event.source_warehouse
                and m.unit == event.unit
                and m.valid_from <= day < m.valid_to
                and m.available_at <= info
            ),
            None,
        )
        if mapping is None:
            exclusions["MAPPING_UNAVAILABLE"] += 1
            continue
        past_days = [day - timedelta(days=i) for i in range(1, 8)]
        proofs = [
            next(
                (
                    p
                    for p in admission.coverage
                    if p.source_product == event.source_product
                    and p.source_warehouse == event.source_warehouse
                    and p.business_date == d
                    and p.status == "complete"
                    and p.available_at <= info
                ),
                None,
            )
            for d in past_days
        ]
        if any(p is None for p in proofs) or any(
            not (mapping.valid_from <= d < mapping.valid_to) for d in past_days
        ):
            exclusions["MISSING_COVERAGE"] += 1
            continue
        past = [
            e
            for e in ordered
            if e.source_product == event.source_product
            and e.source_warehouse == event.source_warehouse
            and e.unit == event.unit
            and e.occurred_at.astimezone(UTC).date() in past_days
        ]
        if any(e.available_at is None or e.available_at > info for e in past):
            exclusions["HISTORY_UNAVAILABLE"] += 1
            continue
        if any(
            admission.source.kind_map[e.kind] == "unclassified"
            and e.kind not in admission.source.outside_target_kinds
            for e in past
        ):
            exclusions["UNCLASSIFIED_HISTORY"] += 1
            continue
        past = [e for e in past if admission.source.kind_map[e.kind] == "customer_fulfillment"]
        mean = sum(e.quantity for e in past) / 7
        utc = event.occurred_at.astimezone(UTC)
        values = (
            math.log1p(event.quantity),
            utc.hour / 23,
            utc.weekday() / 6,
            math.log1p(mean),
            math.log1p(len(past)),
            math.log1p(event.quantity / (1 + mean)),
        )
        key = (
            admission.source.namespace,
            mapping.product_key,
            mapping.warehouse_key,
            event.unit,
            event.event_id,
        )
        samples.append(
            Sample(
                source_record_key="aek1-" + hashlib.sha256(canonical_json(key)).hexdigest(),
                event_id=event.event_id,
                partition=partition.name,
                occurred_at=event.occurred_at,
                available_at=event.available_at,
                values=values,
                label=labels.get(key),
            )
        )
    return FeatureSnapshot(
        config=config,
        source_hashes=dataset.source_hashes,
        samples=tuple(sorted(samples, key=lambda s: (s.occurred_at, s.source_record_key))),
        exclusions=dict(exclusions),
    )
