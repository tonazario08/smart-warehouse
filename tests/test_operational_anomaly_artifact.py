import hashlib

import numpy as np
import pytest
from sklearn.ensemble import IsolationForest

from app.anomalies.operational_artifact import ArtifactInvalid, export_sklearn, load_artifact


def test_real_forest_parity_and_gate(tmp_path):
    data = np.random.default_rng(42).random((128, 6))
    model = IsolationForest(n_estimators=8, max_features=0.5, random_state=42).fit(data)
    value = data[0]
    expected = float(-model.score_samples(value.reshape(1, -1))[0])
    body = export_sklearn(
        model,
        model_version="test/1",
        threshold=expected,
        background=data[:4],
        artifact_class="synthetic_test",
        training_digest="1" * 64,
        approval_id="isolated-test",
    )
    path = tmp_path / "artifact.json"
    path.write_bytes(body)
    digest = hashlib.sha256(body).hexdigest()
    with pytest.raises(ArtifactInvalid):
        load_artifact(path, digest)
    fallback = load_artifact(path, digest, allow_synthetic_test=True)
    assert fallback.score(value) == expected == fallback.threshold
    np.testing.assert_array_equal(
        [fallback.score(row) for row in data[:12]], -model.score_samples(data[:12])
    )
    proof = fallback.explain(value, expected)
    assert proof.state == "available"
    assert proof.score == expected
    assert abs(proof.base_value + sum(proof.contributions) - expected) <= 1e-8


@pytest.fixture(scope="module")
def operational_body():
    rng = np.random.default_rng(182)
    data = rng.random((256, 6))
    # At least one repeated-point leaf exercises the statistical path correction.
    data[100:] = data[99]
    model = IsolationForest(n_estimators=100, random_state=42).fit(data)
    probes = np.vstack((data[:50], rng.random((48, 6)), np.full((1, 6), 20)))
    scores = -model.score_samples(probes)
    threshold = float(scores[np.argsort(scores)[len(scores) // 2]])
    return (
        export_sklearn(
            model,
            model_version="release/001",
            threshold=threshold,
            background=data[:2],
            artifact_class="operational",
            training_digest="2" * 64,
            approval_id="review-001",
        ),
        probes,
        scores,
    )


def test_scoring_boundary_full_forest_and_repeated_leaves(tmp_path, operational_body):
    raw, probes, expected = operational_body
    path = tmp_path / "approved.json"
    path.write_bytes(raw)
    artifact = load_artifact(path, hashlib.sha256(raw).hexdigest())
    actual = np.array([artifact.score(row) for row in probes])
    np.testing.assert_array_equal(actual, expected)
    np.testing.assert_array_equal(actual > artifact.threshold, expected > artifact.threshold)
    assert any(actual < artifact.threshold)
    assert any(actual == artifact.threshold)
    assert any(actual > artifact.threshold)


@pytest.mark.parametrize(
    "change",
    [
        {"model_version": "../artifact"},
        {"schema": "foreign"},
        {"feature_order": ["hour_fraction"]},
        {"threshold": True},
        {"method": "external-calculation"},
        {"artifact_class": "fixture"},
        {"max_samples": 1},
        {"max_samples": 257},
        {"background_digest": "0" * 64},
        {"approval_id": ""},
        {"trees": [[[0, 0, 0, 0, 256]]]},
        {"trees": [[[-1, -1, -1, 0, 256], [-1, -1, -1, 0, 1]]]},
        {"executable": "__import__"},
    ],
)
def test_rejects_invalid_documents_even_when_digest_matches(tmp_path, operational_body, change):
    import json

    body, _, _ = operational_body
    updated = json.loads(body) | change
    raw = json.dumps(updated).encode()
    path = tmp_path / "invalid.json"
    path.write_bytes(raw)
    with pytest.raises(ArtifactInvalid):
        load_artifact(path, hashlib.sha256(raw).hexdigest())


def test_enabled_digest_does_not_allow_changed_or_duplicate_documents(tmp_path, operational_body):
    body, _, _ = operational_body
    file = tmp_path / "artifact.json"
    file.write_bytes(body + b" ")
    with pytest.raises(ArtifactInvalid, match="digest"):
        load_artifact(file, hashlib.sha256(body).hexdigest())
    duplicate = b'{"threshold":0,' + body[1:]
    file.write_bytes(duplicate)
    with pytest.raises(ArtifactInvalid):
        load_artifact(file, hashlib.sha256(duplicate).hexdigest())


def test_rejects_nonfinite_scores_and_wrong_explanation_score(tmp_path, operational_body):
    raw, probes, _ = operational_body
    path = tmp_path / "approved.json"
    path.write_bytes(raw)
    artifact = load_artifact(path, hashlib.sha256(raw).hexdigest())
    with pytest.raises(ArtifactInvalid):
        artifact.score([0, 0, float("nan"), 0, 0, 0])
    explanation = artifact.explain(probes[0], 0.01)
    assert explanation.state == "unavailable" and explanation.reason == "SCORE_MISMATCH"
    assert explanation.base_value is None and explanation.contributions is None
