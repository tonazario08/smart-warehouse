import pytest

from app.anomalies.explanations import explain
from app.anomalies.scoring import fit_and_score
from tests.anomalies_helpers import snapshot


def test_shap_reconstructs_displayed_score():
    result = fit_and_score(snapshot())
    explanation = explain(result, 0)
    assert explanation.state == "available"
    assert explanation.base_value + sum(explanation.contributions) == pytest.approx(
        result.scores[0], abs=1e-8
    )


def test_explainer_failure_is_explicit(monkeypatch):
    import shap

    result = fit_and_score(snapshot())

    def fail(*args, **kwargs):
        raise RuntimeError("broken explainer")

    monkeypatch.setattr(shap, "ExactExplainer", fail)
    explanation = explain(result, 0)
    assert explanation.state == "unavailable"
    assert explanation.reason == "EXPLAINER_ERROR"
    assert explanation.contributions is None


def test_additivity_mismatch_is_unavailable(monkeypatch):
    import numpy as np
    import shap

    result = fit_and_score(snapshot())

    class BadExplainer:
        def __init__(self, *args, **kwargs):
            pass

        def __call__(self, *args, **kwargs):
            class Output:
                base_values = np.array([0.0])
                values = np.array([[0.0] * 6])

            return Output()

    monkeypatch.setattr(shap, "ExactExplainer", BadExplainer)
    explanation = explain(result, 0)
    assert explanation.reason == "ADDITIVITY_MISMATCH"
    assert explanation.contributions is None


def test_explainer_missing_is_explicit(monkeypatch):
    import sys

    result = fit_and_score(snapshot())
    monkeypatch.setitem(sys.modules, "shap", None)
    explanation = explain(result, 0)
    assert explanation.reason == "EXPLAINER_MISSING"
    assert explanation.contributions is None


def test_actual_m5_bundle_through_shap(tmp_path):
    from app.anomalies.dataset import load_anomaly_dataset
    from app.anomalies.features import build_feature_snapshot
    from app.anomalies.schemas import Label
    from tests.anomalies_helpers import bundle, config

    published = bundle(tmp_path, dense=True)
    base = config(published.data_version)
    labels = tuple(
        Label(
            namespace="fixture",
            product_key="product-1",
            warehouse_key="warehouse-1",
            unit="cái",
            event_id=f"e{day}-{i}",
            label="normal",
        )
        for day in range(11, 15)
        for i in range(35)
    )
    cfg = base.model_copy(update={"labels": labels})
    features = build_feature_snapshot(load_anomaly_dataset(cfg, published.path))
    result = fit_and_score(features)
    assert result.state == "available"
    explanation = explain(result, 0)
    assert explanation.state == "available"
    assert explanation.residual <= 1e-8
