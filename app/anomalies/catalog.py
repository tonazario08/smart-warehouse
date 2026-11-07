"""Canonical, bounded public fixture catalogs, without raw source identities."""

import hashlib
import os
import re
import tempfile
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, model_validator

from app.analytics.export import canonical_json
from app.analytics.ingestion import _bounded_read, checked_path
from app.analytics.schemas import AwareTime, Checksum, Contract, Identifier
from app.anomalies.schemas import FEATURE_ORDER

MAX_BYTES = 8 * 1024 * 1024
Finite = Annotated[float, Field(allow_inf_nan=False)]
Probability = Annotated[float, Field(allow_inf_nan=False, ge=0, le=1)]


class PublicExplanation(Contract):
    state: Literal["available", "unavailable"]
    reason: (
        Literal["EXPLAINER_MISSING", "EXPLAINER_ERROR", "ADDITIVITY_MISMATCH", "MODEL_UNAVAILABLE"]
        | None
    )
    base_value: Finite | None
    contributions: tuple[Finite, Finite, Finite, Finite, Finite, Finite] | None
    residual: Finite | None


class PublicAlert(Contract):
    source_record_key: str = Field(pattern=r"^aek1-[0-9a-f]{64}$")
    occurred_at: AwareTime
    partition: Literal["train", "validation", "final_holdout"]
    score: Probability
    features: tuple[Finite, Finite, Finite, Finite, Finite, Finite]
    explanation: PublicExplanation


class PublicPartition(Contract):
    name: Literal["train", "validation", "final_holdout"]
    start: date
    end: date
    information_cutoff: AwareTime


class PublicMetrics(Contract):
    label_type: Literal["synthetic"]
    unlabeled: int = Field(ge=0, le=256)
    tp: int = Field(ge=0, le=256)
    fp: int = Field(ge=0, le=256)
    fn: int = Field(ge=0, le=256)
    tn: int = Field(ge=0, le=256)
    precision: Probability | None
    recall: Probability | None

    @model_validator(mode="after")
    def valid_metrics(self):
        expected_precision = (
            self.tp / (self.tp + self.fp) if self.tp + self.fp and not self.unlabeled else None
        )
        expected_recall = (
            self.tp / (self.tp + self.fn) if self.tp + self.fn and not self.unlabeled else None
        )
        if self.precision != expected_precision or self.recall != expected_recall:
            raise ValueError("inconsistent metrics")
        return self


class PublicPayload(Contract):
    schema_version: Literal["anomaly-public/1"] = "anomaly-public/1"
    dataset_class: Literal["fixture"] = "fixture"
    input_version: str = Field(pattern=r"^ddv1-[0-9a-f]{64}$")
    feature_version: Literal["anomaly-features/1"] = "anomaly-features/1"
    model_version: Literal["isolation-forest/1"] = "isolation-forest/1"
    feature_order: tuple[str, ...]
    score_definition: Literal["-IsolationForest.score_samples"]
    created_at: AwareTime
    partitions: tuple[PublicPartition, PublicPartition, PublicPartition]
    seed: Literal[42]
    package_versions: dict[Identifier, Identifier]
    source_hashes: dict[Identifier, Checksum]
    background_digest: Checksum
    exclusions: dict[Identifier, Annotated[int, Field(ge=0, le=10000)]]
    sample_count: int = Field(ge=0, le=2816)
    partition_counts: dict[
        Literal["train", "validation", "final_holdout"], Annotated[int, Field(ge=0, le=2048)]
    ]
    threshold: Probability
    metrics: PublicMetrics
    real_precision_recall: Literal["NOT VERIFIED"] = "NOT VERIFIED"
    alerts: tuple[PublicAlert, ...] = Field(max_length=2816)

    @model_validator(mode="after")
    def consistency(self):
        if self.feature_order != FEATURE_ORDER or len(self.alerts) > self.sample_count:
            raise ValueError("inconsistent feature order or count")
        if self.package_versions != {
            "numpy": "2.5.4",
            "scipy": "1.18.1",
            "scikit-learn": "1.9.1",
            "shap": "0.52.0",
        }:
            raise ValueError("invalid package versions")
        if set(self.source_hashes) != {
            "records.jsonl",
            "observations.jsonl",
            "quality.json",
            "source",
        }:
            raise ValueError("invalid source provenance")
        a, b, c = self.partitions
        if (
            (a.name, b.name, c.name) != ("train", "validation", "final_holdout")
            or any(
                p.start >= p.end
                or p.information_cutoff < datetime.combine(p.end, datetime.min.time(), UTC)
                for p in self.partitions
            )
            or a.end > b.start
            or b.end > c.start
            or a.information_cutoff > datetime.combine(b.start, datetime.min.time(), UTC)
            or b.information_cutoff > datetime.combine(c.start, datetime.min.time(), UTC)
            or c.information_cutoff > self.created_at
        ):
            raise ValueError("invalid partition timing")
        if (
            set(self.partition_counts) != {"train", "validation", "final_holdout"}
            or self.partition_counts["train"] < 128
            or not 100 <= self.partition_counts["validation"] <= 512
            or self.partition_counts["final_holdout"] > 256
            or sum(self.partition_counts.values()) != self.sample_count
            or self.metrics.tp
            + self.metrics.fp
            + self.metrics.fn
            + self.metrics.tn
            + self.metrics.unlabeled
            != self.partition_counts["final_holdout"]
        ):
            raise ValueError("inconsistent partition counts")
        keys = [a.source_record_key for a in self.alerts]
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate alert")
        for a in self.alerts:
            e = a.explanation
            part = next(p for p in self.partitions if p.name == a.partition)
            if not part.start <= a.occurred_at.astimezone(UTC).date() < part.end:
                raise ValueError("alert outside partition")
            if (
                a.score <= self.threshold
                or any(x < 0 for x in a.features)
                or a.features[1] > 1
                or a.features[2] > 1
            ):
                raise ValueError("invalid alert")
            if e.state == "available":
                if (
                    e.reason is not None
                    or e.base_value is None
                    or e.contributions is None
                    or e.residual is None
                ):
                    raise ValueError("invalid attribution")
                residual = abs(e.base_value + sum(e.contributions) - a.score)
                if residual > 1e-8 or abs(residual - e.residual) > 1e-12:
                    raise ValueError("inconsistent attribution")
            elif (
                e.reason is None
                or e.base_value is not None
                or e.contributions is not None
                or e.residual is not None
            ):
                raise ValueError("invalid unavailable explanation")
        return self


@dataclass(frozen=True)
class PublicAnomalyRun:
    run_id: str
    payload: PublicPayload


def _root(root: Path) -> Path:
    root = checked_path(Path(root))
    try:
        home = Path.home().resolve()
    except RuntimeError:
        home = None
    if not root.is_dir() or root == Path(root.anchor) or root == home:
        raise ValueError("unsafe catalog root")
    workspace = Path(__file__).resolve().parents[2]
    if root.is_relative_to(workspace) and not root.is_relative_to(
        workspace / "artifacts" / "anomalies"
    ):
        raise ValueError("unsafe catalog root")
    return root


def _projection(result) -> PublicPayload:
    import numpy as np

    from app.anomalies.explanations import explain
    from app.anomalies.schemas import FeatureSnapshot

    if result.state != "available" or result.threshold is None:
        raise ValueError("model unavailable")
    snapshot = FeatureSnapshot.model_validate(result.snapshot.model_dump())
    if len(snapshot.samples) != len(result.scores):
        raise ValueError("score count mismatch")
    train = [s.values for s in snapshot.samples if s.partition == "train"]
    normal = [
        s.values for s in snapshot.samples if s.partition == "validation" and s.label == "normal"
    ]
    if len(train) < 128 or len(normal) < 100 or result.model is None:
        raise ValueError("invalid model inputs")
    params = result.model.get_params()
    required = {
        "n_estimators": 100,
        "max_samples": min(256, len(train)),
        "contamination": "auto",
        "max_features": 1.0,
        "bootstrap": False,
        "random_state": 42,
        "n_jobs": 1,
    }
    if any(params[name] != value for name, value in required.items()):
        raise ValueError("model parameter mismatch")
    expected = tuple(
        float(v)
        for v in -result.model.score_samples(np.asarray([s.values for s in snapshot.samples]))
    )
    threshold = float(
        np.quantile(-result.model.score_samples(np.asarray(normal)), 0.99, method="higher")
    )
    if (
        expected != result.scores
        or threshold != result.threshold
        or tuple(train[:16]) != result.background
    ):
        raise ValueError("model score or threshold mismatch")
    if (
        hashlib.sha256(canonical_json(result.background)).hexdigest()
        != result.metadata["background_digest"]
    ):
        raise ValueError("background digest mismatch")
    labeled = [
        (s.label, score > threshold)
        for s, score in zip(snapshot.samples, expected, strict=True)
        if s.partition == "final_holdout" and s.label is not None
    ]
    counts = {
        "tp": sum(label == "anomaly" and flag for label, flag in labeled),
        "fp": sum(label == "normal" and flag for label, flag in labeled),
        "fn": sum(label == "anomaly" and not flag for label, flag in labeled),
        "tn": sum(label == "normal" and not flag for label, flag in labeled),
        "unlabeled": sum(
            s.partition == "final_holdout" and s.label is None for s in snapshot.samples
        ),
    }
    if any(result.synthetic_metrics[name] != value for name, value in counts.items()):
        raise ValueError("holdout metrics mismatch")
    alerts = []
    for index, (sample, score) in enumerate(zip(snapshot.samples, result.scores, strict=True)):
        if score > result.threshold:
            e = explain(result, index)
            alerts.append(
                PublicAlert(
                    source_record_key=sample.source_record_key,
                    occurred_at=sample.occurred_at,
                    partition=sample.partition,
                    score=score,
                    features=sample.values,
                    explanation=PublicExplanation(
                        state=e.state,
                        reason=e.reason,
                        base_value=e.base_value,
                        contributions=e.contributions,
                        residual=e.residual,
                    ),
                )
            )
    meta = result.metadata
    parts = tuple(
        PublicPartition(
            name=p.name, start=p.start, end=p.end, information_cutoff=p.information_cutoff
        )
        for p in snapshot.config.partitions
    )
    return PublicPayload(
        input_version=snapshot.config.data_version,
        feature_order=FEATURE_ORDER,
        score_definition="-IsolationForest.score_samples",
        created_at=snapshot.config.created_at,
        partitions=parts,
        seed=snapshot.config.seed,
        package_versions=meta["package_versions"],
        source_hashes=snapshot.source_hashes,
        background_digest=meta["background_digest"],
        exclusions=snapshot.exclusions,
        sample_count=len(snapshot.samples),
        partition_counts={
            p.name: sum(s.partition == p.name for s in snapshot.samples)
            for p in snapshot.config.partitions
        },
        threshold=result.threshold,
        metrics=PublicMetrics(**result.synthetic_metrics),
        alerts=tuple(alerts),
    )


def publish_run(result, root: Path) -> str:
    root = _root(root)
    body = canonical_json(_projection(result))
    if len(body) > MAX_BYTES:
        raise ValueError("catalog too large")
    run_id = "arv1-" + hashlib.sha256(body).hexdigest()
    target = root / f"{run_id}.json"
    fd, name = tempfile.mkstemp(prefix=".anomaly-", suffix=".stage", dir=root)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(name, target)
        except FileExistsError:
            verify_run(root, run_id)
    finally:
        os.unlink(name)
    return run_id


def verify_run(root: Path, run_id: str) -> PublicAnomalyRun:
    if not re.fullmatch(r"arv1-[0-9a-f]{64}", run_id):
        raise ValueError("invalid run id")
    root = _root(root)
    path = checked_path(root / f"{run_id}.json")
    body = _bounded_read(path, MAX_BYTES)
    if hashlib.sha256(body).hexdigest() != run_id[5:]:
        raise ValueError("catalog digest mismatch")
    payload = PublicPayload.model_validate_json(body)
    if canonical_json(payload) != body:
        raise ValueError("noncanonical catalog")
    return PublicAnomalyRun(run_id, payload)
