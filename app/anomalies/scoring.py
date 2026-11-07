"""Offline Isolation Forest scoring; never imported by HTTP paths."""

import hashlib
from dataclasses import dataclass
from importlib.metadata import version

from app.analytics.export import canonical_json
from app.anomalies.schemas import FEATURE_ORDER, FeatureSnapshot


@dataclass(frozen=True)
class AnomalyRunResult:
    state: str
    reason: str | None
    snapshot: FeatureSnapshot
    scores: tuple[float, ...] = ()
    threshold: float | None = None
    model: object = None
    background: tuple[tuple[float, ...], ...] = ()
    metadata: object = None
    synthetic_metrics: object = None


def fit_and_score(snapshot: FeatureSnapshot) -> AnomalyRunResult:
    # Revalidate untrusted model_copy(update=...) inputs as well.
    snapshot = FeatureSnapshot.model_validate(snapshot.model_dump())
    train = [s.values for s in snapshot.samples if s.partition == "train"]
    normal = [
        s.values for s in snapshot.samples if s.partition == "validation" and s.label == "normal"
    ]
    if len(train) < 128:
        return AnomalyRunResult("unavailable", "INSUFFICIENT_TRAIN", snapshot)
    if len(normal) < 100:
        return AnomalyRunResult("unavailable", "INSUFFICIENT_NORMAL_VALIDATION", snapshot)
    try:
        import numpy as np
        from sklearn.ensemble import IsolationForest
    except ImportError:
        return AnomalyRunResult("unavailable", "MODEL_DEPENDENCY_MISSING", snapshot)
    x = np.asarray(train, dtype=float)
    if np.all(x == x[0]):
        return AnomalyRunResult("unavailable", "CONSTANT_TRAIN", snapshot)
    model = IsolationForest(
        n_estimators=100,
        max_samples=min(256, len(train)),
        contamination="auto",
        max_features=1.0,
        bootstrap=False,
        random_state=42,
        n_jobs=1,
    )
    model.fit(x)
    threshold = float(np.quantile(-model.score_samples(np.asarray(normal)), 0.99, method="higher"))
    scores = tuple(
        float(v) for v in -model.score_samples(np.asarray([s.values for s in snapshot.samples]))
    )
    background = tuple(train[:16])
    metadata = {
        "model_version": "isolation-forest/1",
        "feature_order": FEATURE_ORDER,
        "background_digest": hashlib.sha256(canonical_json(background)).hexdigest(),
        "score_definition": "-IsolationForest.score_samples",
        "seed": 42,
        "package_versions": {p: version(p) for p in ("scikit-learn", "shap", "numpy", "scipy")},
        "source_hashes": snapshot.source_hashes,
        "config": snapshot.config.model_dump(mode="json"),
        "exclusions": snapshot.exclusions,
        "dataset_class": "fixture",
        "real_precision_recall": "NOT VERIFIED",
    }
    pairs = [
        (s.label, score > threshold)
        for s, score in zip(snapshot.samples, scores, strict=True)
        if s.partition == "final_holdout" and s.label is not None
    ]
    tp = sum(label == "anomaly" and flag for label, flag in pairs)
    fp = sum(label == "normal" and flag for label, flag in pairs)
    fn = sum(label == "anomaly" and not flag for label, flag in pairs)
    tn = sum(label == "normal" and not flag for label, flag in pairs)
    unlabeled = sum(s.partition == "final_holdout" and s.label is None for s in snapshot.samples)
    metrics = {
        "label_type": "synthetic",
        "unlabeled": unlabeled,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "precision": tp / (tp + fp) if tp + fp and not unlabeled else None,
        "recall": tp / (tp + fn) if tp + fn and not unlabeled else None,
    }
    return AnomalyRunResult(
        "available", None, snapshot, scores, threshold, model, background, metadata, metrics
    )
