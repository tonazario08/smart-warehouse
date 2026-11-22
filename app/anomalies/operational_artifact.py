"""Strict data-only snapshot of a reviewed Isolation Forest; no object deserialization."""

import hashlib
import hmac
import json
import math
import os
import re
import stat
from dataclasses import dataclass
from pathlib import Path

from app.analytics.ingestion import _decode_json, checked_path
from app.analytics.schemas import PipelineError
from app.anomalies.explanations import Explanation
from app.anomalies.schemas import FEATURE_ORDER

SCHEMA = "operational-isolation-forest/1"
FEATURE_VERSION = "anomaly-features/1"
METHOD = "-IsolationForest.score_samples"
MAX_BYTES = 4 * 1024 * 1024
MAX_TREES = 100
MAX_SAMPLES = 256
MAX_DEPTH = 8
MAX_BACKGROUND = 16
VERSIONS = {"scikit-learn": "1.9.1", "numpy": "2.5.4", "scipy": "1.18.1", "shap": "0.52.0"}
_KEYS = {
    "schema",
    "model_version",
    "feature_version",
    "feature_order",
    "method",
    "threshold",
    "training_digest",
    "approval_id",
    "artifact_class",
    "background",
    "background_digest",
    "versions",
    "max_samples",
    "trees",
}
_ASSUMPTIONS = "Independent masking over the approved background; attribution is not causal."


class ArtifactInvalid(ValueError):
    """The artifact is unavailable or does not satisfy the runtime trust contract."""


def _json(value):
    return json.dumps(value, sort_keys=True, allow_nan=False, separators=(",", ":")).encode()


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _hex(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value)


def _identifier(value):
    return isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,95}", value)


def _number(value):
    if type(value) not in (int, float) or not -1e9 <= value <= 1e9 or not math.isfinite(value):
        raise ArtifactInvalid("invalid numeric value")
    return float(value)


def _integer(value, minimum, maximum):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ArtifactInvalid("invalid integer value")
    return value


def _background(value):
    if type(value) is not list or not 1 <= len(value) <= MAX_BACKGROUND:
        raise ArtifactInvalid("invalid background size")
    if any(type(row) is not list or len(row) != len(FEATURE_ORDER) for row in value):
        raise ArtifactInvalid("invalid background shape")
    return tuple(tuple(_number(x) for x in row) for row in value)


@dataclass(frozen=True)
class _Node:
    feature: int
    left: int
    right: int
    threshold: float
    samples: int


def _tree(value, max_samples):
    if type(value) is not list or not 1 <= len(value) <= 2 * max_samples - 1:
        raise ArtifactInvalid("invalid tree size")
    nodes = []
    for raw in value:
        if type(raw) is not list or len(raw) != 5:
            raise ArtifactInvalid("invalid node shape")
        feature, left, right, threshold, samples = raw
        node = _Node(
            _integer(feature, -1, len(FEATURE_ORDER) - 1),
            _integer(left, -1, len(value) - 1),
            _integer(right, -1, len(value) - 1),
            _number(threshold),
            _integer(samples, 1, max_samples),
        )
        if node.feature == -1 and (node.left, node.right, node.threshold) != (-1, -1, 0.0):
            raise ArtifactInvalid("invalid leaf")
        if node.feature >= 0 and (min(node.left, node.right) <= 0 or node.left == node.right):
            raise ArtifactInvalid("invalid branch")
        nodes.append(node)
    if nodes[0].samples != max_samples:
        raise ArtifactInvalid("invalid root sample count")
    seen, frontier = set(), [(0, 0)]
    while frontier:
        index, depth = frontier.pop()
        if depth > MAX_DEPTH or index in seen:
            raise ArtifactInvalid("invalid tree topology")
        seen.add(index)
        node = nodes[index]
        if node.feature >= 0:
            if nodes[node.left].samples + nodes[node.right].samples != node.samples:
                raise ArtifactInvalid("invalid branch sample counts")
            frontier.extend(((node.left, depth + 1), (node.right, depth + 1)))
    if len(seen) != len(nodes):
        raise ArtifactInvalid("unreachable tree node")
    return tuple(nodes)


def _numpy():
    try:
        import numpy as np
    except ImportError as error:
        raise ArtifactInvalid("numeric runtime unavailable") from error
    if np.__version__ != VERSIONS["numpy"]:
        raise ArtifactInvalid("numeric runtime version mismatch")
    return np


def _correction(np, sample_counts):
    """The expected additional path for a terminal leaf with repeated samples."""
    counts = np.asarray(sample_counts, dtype=np.float64)
    result = np.zeros_like(counts)
    result[counts == 2] = 1
    mask = counts > 2
    n = counts[mask]
    result[mask] = 2 * (np.log(n - 1) + np.euler_gamma) - 2 * (n - 1) / n
    return result


@dataclass(frozen=True)
class Artifact:
    digest: str
    model_version: str
    feature_version: str
    threshold: float
    artifact_class: str
    training_digest: str
    approval_id: str
    background: tuple[tuple[float, ...], ...]
    background_digest: str
    max_samples: int
    trees: tuple[tuple[_Node, ...], ...]
    feature_order = FEATURE_ORDER
    method = METHOD

    def _scores(self, values):
        np = _numpy()
        rows = np.asarray(values, dtype=np.float64)
        if rows.ndim != 2 or rows.shape[1] != len(FEATURE_ORDER) or len(rows) > 1024:
            raise ArtifactInvalid("invalid scoring shape")
        if not np.all(np.isfinite(rows)) or np.any(np.abs(rows) > 1e9):
            raise ArtifactInvalid("invalid scoring values")
        # scikit-learn's tree input is float32 and branch thresholds are float64.
        rows = rows.astype(np.float32)
        depths = np.zeros(len(rows), dtype=np.float64)
        sample_lengths = _correction(np, range(self.max_samples + 1))
        for tree in self.trees:
            for row_index, row in enumerate(rows):
                node, depth = tree[0], 0
                while node.feature >= 0:
                    branch = node.left if float(row[node.feature]) <= node.threshold else node.right
                    node, depth = tree[branch], depth + 1
                # Match the stored path node count (root included) before sklearn subtracts one.
                depths[row_index] += (depth + 1) + sample_lengths[node.samples] - 1.0
        denominator = len(self.trees) * sample_lengths[self.max_samples]
        return 2 ** -(depths / denominator)

    def score(self, values) -> float:
        return float(self._scores([values])[0])

    def explain(self, values, score: float) -> Explanation:
        try:
            import shap
        except ImportError:
            return Explanation("unavailable", "EXPLAINER_MISSING", assumptions=_ASSUMPTIONS)
        if shap.__version__ != VERSIONS["shap"]:
            return Explanation("unavailable", "EXPLAINER_VERSION", assumptions=_ASSUMPTIONS)
        try:
            np = _numpy()
            if not math.isfinite(score) or abs(score - self.score(values)) > 1e-12:
                return Explanation("unavailable", "SCORE_MISMATCH", assumptions=_ASSUMPTIONS)
            masker = shap.maskers.Independent(np.asarray(self.background), max_samples=16)
            explainer = shap.ExactExplainer(self._scores, masker)
            output = explainer(np.asarray([values]), max_evals=64)
            base = float(output.base_values[0])
            contributions = tuple(float(x) for x in output.values[0])
            residual = abs(base + sum(contributions) - score)
            if (
                len(contributions) != len(FEATURE_ORDER)
                or not all(math.isfinite(x) for x in (base, residual, *contributions))
                or residual > 1e-8
            ):
                return Explanation("unavailable", "ADDITIVITY_MISMATCH", assumptions=_ASSUMPTIONS)
            return Explanation(
                "available",
                base_value=base,
                contributions=contributions,
                score=score,
                residual=residual,
                assumptions=_ASSUMPTIONS,
            )
        except Exception:
            return Explanation("unavailable", "EXPLAINER_ERROR", assumptions=_ASSUMPTIONS)


def _parse(value, digest, allow_synthetic_test):
    if type(value) is not dict or set(value) != _KEYS:
        raise ArtifactInvalid("invalid artifact keys")
    if (
        value["schema"] != SCHEMA
        or value["feature_version"] != FEATURE_VERSION
        or value["feature_order"] != list(FEATURE_ORDER)
        or value["method"] != METHOD
        or value["versions"] != VERSIONS
        or not _identifier(value["model_version"])
        or not _identifier(value["approval_id"])
        or not _hex(value["training_digest"])
    ):
        raise ArtifactInvalid("invalid model contract")
    kind = value["artifact_class"]
    if kind != "operational" and not (kind == "synthetic_test" and allow_synthetic_test is True):
        raise ArtifactInvalid("artifact class unavailable")
    threshold = _number(value["threshold"])
    if not 0.0 <= threshold <= 1.0:
        raise ArtifactInvalid("invalid threshold")
    background = _background(value["background"])
    if (
        not _hex(value["background_digest"])
        or _sha(_json(background)) != value["background_digest"]
    ):
        raise ArtifactInvalid("invalid background digest")
    max_samples = _integer(value["max_samples"], 2, MAX_SAMPLES)
    if type(value["trees"]) is not list or not 1 <= len(value["trees"]) <= MAX_TREES:
        raise ArtifactInvalid("invalid forest size")
    trees = tuple(_tree(tree, max_samples) for tree in value["trees"])
    return Artifact(
        digest,
        value["model_version"],
        FEATURE_VERSION,
        threshold,
        kind,
        value["training_digest"],
        value["approval_id"],
        background,
        value["background_digest"],
        max_samples,
        trees,
    )


def load_artifact(path, expected_digest: str, *, allow_synthetic_test=False) -> Artifact:
    """Read a single trusted local, digest-pinned regular file; never call an object loader."""
    if not _hex(expected_digest):
        raise ArtifactInvalid("invalid approved digest")
    try:
        candidate = checked_path(Path(path))
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
        flags |= getattr(os, "O_BINARY", 0)
        fd = os.open(candidate, flags)
        with os.fdopen(fd, "rb") as stream:
            info = os.fstat(stream.fileno())
            if not stat.S_ISREG(info.st_mode) or not 1 <= info.st_size <= MAX_BYTES:
                raise ArtifactInvalid("invalid artifact file")
            raw = stream.read(MAX_BYTES + 1)
        if not 1 <= len(raw) <= MAX_BYTES or not hmac.compare_digest(_sha(raw), expected_digest):
            raise ArtifactInvalid("approved artifact digest mismatch")
        return _parse(_decode_json(raw.decode("utf-8")), expected_digest, allow_synthetic_test)
    except (OSError, PipelineError, UnicodeError, RecursionError, TypeError) as error:
        raise ArtifactInvalid("invalid artifact file") from error


def export_sklearn(
    model, *, model_version, threshold, background, artifact_class, training_digest, approval_id
) -> bytes:
    """Offline producer; runtime never deserializes or fits a Python estimator."""
    import sklearn
    from sklearn.ensemble import IsolationForest

    if type(model) is not IsolationForest or sklearn.__version__ != VERSIONS["scikit-learn"]:
        raise ArtifactInvalid("unsupported estimator version")
    if getattr(model, "n_features_in_", None) != len(FEATURE_ORDER):
        raise ArtifactInvalid("invalid estimator feature count")
    trees = []
    for estimator, features in zip(model.estimators_, model.estimators_features_, strict=True):
        tree = estimator.tree_
        trees.append(
            [
                [
                    int(features[feature]) if feature >= 0 else -1,
                    int(tree.children_left[i]),
                    int(tree.children_right[i]),
                    float(tree.threshold[i]) if feature >= 0 else 0.0,
                    int(tree.n_node_samples[i]),
                ]
                for i, feature in enumerate(tree.feature)
            ]
        )
    background = [[float(x) for x in row] for row in background]
    document = {
        "schema": SCHEMA,
        "model_version": model_version,
        "feature_version": FEATURE_VERSION,
        "feature_order": list(FEATURE_ORDER),
        "method": METHOD,
        "threshold": float(threshold),
        "training_digest": training_digest,
        "approval_id": approval_id,
        "versions": VERSIONS,
        "artifact_class": artifact_class,
        "background": background,
        "background_digest": _sha(_json(background)),
        "trees": trees,
        "max_samples": int(model.max_samples_),
    }
    raw = _json(document)
    if len(raw) > MAX_BYTES:
        raise ArtifactInvalid("invalid artifact size")
    _parse(document, _sha(raw), True)
    return raw
