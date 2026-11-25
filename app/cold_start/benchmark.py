"""Deterministic train-only clustering and retrospective benchmark."""

import hashlib
from datetime import UTC, datetime, time, timedelta
from statistics import median

from app.analytics.export import canonical_json
from app.cold_start.schemas import ColdStartReport, Prediction, Provenance


class ColdStartUnavailable(ValueError):
    reason_code = "NO_ELIGIBLE_TRAINING_SNAPSHOTS"


def cutoff(day):
    return datetime.combine(day + timedelta(days=1), time.min, UTC)


def vectors(train):
    categories = sorted(
        {s.sku.snapshot.category for s in train if s.sku.snapshot.category is not None}
    )
    suppliers = sorted(
        {s.sku.snapshot.supplier for s in train if s.sku.snapshot.supplier is not None}
    )

    def encode(s):
        snap = s.sku.snapshot
        return (
            tuple(int(snap.category == c) for c in categories)
            + (
                int(snap.category is None),
                int(snap.category is not None and snap.category not in categories),
            )
            + tuple(int(snap.supplier == c) for c in suppliers)
            + (
                int(snap.supplier is None),
                int(snap.supplier is not None and snap.supplier not in suppliers),
            )
        )

    return encode


def distance(a, b):
    return sum((x - y) ** 2 for x, y in zip(a, b, strict=True))


def fit(points, k):
    centers = [points[0]]
    while len(centers) < k:
        candidate = max(points, key=lambda p: min(distance(p, c) for c in centers))
        if candidate in centers:
            return None
        centers.append(candidate)
    for _ in range(50):
        labels = tuple(min(range(k), key=lambda i: (distance(p, centers[i]), i)) for p in points)
        groups = [
            [p for p, label in zip(points, labels, strict=True) if label == i] for i in range(k)
        ]
        if any(not g for g in groups):
            return None
        new = [tuple(sum(col) / len(g) for col in zip(*g, strict=True)) for g in groups]
        if new == centers:
            return tuple(new)
        centers = new
    return None


def total(series, origin, horizon):
    rows = {r.day: r for r in series.observations}
    dates = [origin - timedelta(days=i) for i in range(horizon)]
    if any(
        d not in rows
        or rows[d].value is None
        or rows[d].available_at is None
        or rows[d].available_at > cutoff(origin)
        for d in dates
    ):
        return None
    return sum(rows[d].value for d in dates)


def predict(target, train, encode, centers, origin, horizon):
    snap = target.sku.snapshot
    if snap.available_at > cutoff(origin) or not (snap.category or snap.supplier):
        return None, None, "insufficient_metadata", ()
    cluster = min(range(len(centers)), key=lambda i: (distance(encode(target), centers[i]), i))
    valid = [(s, total(s, origin, horizon)) for s in train]
    valid = [
        (s, v) for s, v in valid if v is not None and s.sku.snapshot.available_at <= cutoff(origin)
    ]
    same_category = [
        (s, v)
        for s, v in valid
        if snap.category is not None and s.sku.snapshot.category == snap.category
    ]
    same_cluster = [
        (s, v)
        for s, v in valid
        if min(range(len(centers)), key=lambda i: (distance(encode(s), centers[i]), i)) == cluster
    ]
    base = same_category if len(same_category) >= 3 else valid
    baseline = float(median(v for _, v in base)) if len(base) >= 3 else None
    for name, group in (
        ("cluster", same_cluster),
        ("category", same_category),
        ("all_train", valid),
    ):
        if len(group) >= 3:
            return (
                float(median(v for _, v in group)),
                baseline,
                name,
                tuple(s.sku.product_key for s, _ in group),
            )
    return None, baseline, "insufficient_references", ()


def actual(target, origin, horizon, known_by):
    rows = {r.day: r for r in target.observations}
    dates = [origin + timedelta(days=i) for i in range(1, horizon + 1)]
    if any(
        d not in rows
        or rows[d].value is None
        or rows[d].available_at is None
        or rows[d].available_at > known_by
        for d in dates
    ):
        return None
    return sum(rows[d].value for d in dates)


def evaluate_cold_start(dataset):
    parts = {p.name: p for p in dataset.config.partitions}
    if dataset.config.created_at < cutoff(parts["holdout"].end):
        raise ValueError("created_at precedes holdout endpoint")
    train_cutoff = cutoff(parts["train"].end)
    train = sorted(
        (
            s
            for s in dataset.series
            if s.sku.split == "train"
            and s.sku.snapshot.available_at <= train_cutoff
            and (s.sku.snapshot.category or s.sku.snapshot.supplier)
        ),
        key=lambda s: s.sku.product_key,
    )
    if not train:
        raise ColdStartUnavailable("no eligible training snapshots")
    encode = vectors(train)
    points = [encode(s) for s in train]
    candidates = {
        k: c for k in range(1, min(3, len(set(points))) + 1) if (c := fit(points, k)) is not None
    }

    def generate(split, centers, horizons):
        partition = parts[split]
        for target in sorted(
            (s for s in dataset.series if s.sku.split == split), key=lambda s: s.sku.product_key
        ):
            for h in horizons:
                origin = partition.start - timedelta(days=1)
                while origin + timedelta(days=h) <= partition.end:
                    pred, base, source, keys = predict(target, train, encode, centers, origin, h)
                    yield (
                        Prediction(
                            sku=target.sku.product_key,
                            split=split,
                            origin=origin,
                            horizon=h,
                            prediction=pred,
                            baseline=base,
                            reference_source=source,
                            reference_keys=keys,
                            confidence=source if pred is not None else "unavailable",
                            reason=None if pred is not None else source,
                        ),
                        target,
                    )
                    origin += timedelta(days=1)

    scores = {}
    selection_data = {}
    for k, centers in candidates.items():
        selection_data[k] = {
            (p.sku, p.origin): (
                p.prediction,
                actual(t, p.origin, 7, cutoff(parts["validation"].end)),
            )
            for p, t in generate("validation", centers, (7,))
        }
    common = set.intersection(
        *(
            set(key for key, (p, a) in rows.items() if p is not None and a is not None)
            for rows in selection_data.values()
        )
    )
    if common:
        for k, rows in selection_data.items():
            scores[k] = sum(abs(rows[key][0] - rows[key][1]) for key in sorted(common)) / len(
                common
            )
        selected = min(scores, key=lambda k: (scores[k], k))
        reason = "validation_common_horizon_7_mae"
    else:
        selected, reason = 1, "no_common_validation_samples"
    predictions = []
    scored = {}
    for p, t in generate("holdout", candidates[selected], (1, 7)):
        predictions.append(p)
        scored[(p.sku, p.origin, p.horizon)] = actual(
            t, p.origin, p.horizon, dataset.config.created_at
        )
    metrics = {}
    for h in (1, 7):
        rows = [p for p in predictions if p.horizon == h]
        comparable = [
            (p, scored[(p.sku, p.origin, h)])
            for p in rows
            if p.prediction is not None
            and p.baseline is not None
            and scored[(p.sku, p.origin, h)] is not None
        ]
        denominator = sum(a for _, a in comparable)
        n = len(comparable)
        metrics[str(h)] = {
            "samples": len(rows),
            "predicted": sum(p.prediction is not None for p in rows),
            "baseline_predicted": sum(p.baseline is not None for p in rows),
            "actual": sum(scored[(p.sku, p.origin, h)] is not None for p in rows),
            "compared": n,
            "actual_sum": denominator,
            "excluded_prediction": len(rows) - sum(p.prediction is not None for p in rows),
            "excluded_baseline": len(rows) - sum(p.baseline is not None for p in rows),
            "excluded_actual": len(rows)
            - sum(scored[(p.sku, p.origin, h)] is not None for p in rows),
            "excluded_comparison": len(rows) - n,
            "category_count": len(
                {
                    s.sku.snapshot.category
                    for s in dataset.series
                    for p, _ in comparable
                    if s.sku.product_key == p.sku and s.sku.snapshot.category is not None
                }
            ),
            "mae": sum(abs(p.prediction - a) for p, a in comparable) / n if n else None,
            "baseline_mae": sum(abs(p.baseline - a) for p, a in comparable) / n if n else None,
            "wape": sum(abs(p.prediction - a) for p, a in comparable) / denominator
            if denominator
            else None,
            "baseline_wape": sum(abs(p.baseline - a) for p, a in comparable) / denominator
            if denominator
            else None,
        }
    return ColdStartReport(
        created_at=dataset.config.created_at,
        namespace=dataset.namespace,
        target=dataset.config.target,
        unit=dataset.series[0].sku.unit,
        warehouse_key=dataset.series[0].sku.warehouse_key,
        train_cutoff=train_cutoff,
        validation_cutoff=cutoff(parts["validation"].end),
        provenance=tuple(
            Provenance(
                product_key=s.sku.product_key,
                split=s.sku.split,
                data_version=s.sku.data_version,
                snapshot=s.sku.snapshot,
                snapshot_digest=hashlib.sha256(canonical_json(s.sku.snapshot)).hexdigest(),
                admission_cutoff=s.admission_cutoff,
            )
            for s in sorted(dataset.series, key=lambda s: s.sku.product_key)
        ),
        partitions=dataset.config.partitions,
        selected_k=selected,
        selection_reason=reason,
        metrics=metrics,
        predictions=tuple(predictions),
    )
