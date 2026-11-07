import pytest
from pydantic import ValidationError

from app.anomalies.scoring import fit_and_score
from tests.anomalies_helpers import snapshot


def test_constant_training_data_is_unavailable():
    result = fit_and_score(snapshot(constant=True))
    assert result.state == "unavailable"
    assert result.reason == "CONSTANT_TRAIN"


def test_final_holdout_cannot_change_threshold():
    first = fit_and_score(snapshot())
    changed = fit_and_score(snapshot(holdout_offset=1000))
    assert first.state == "available"
    assert first.threshold == changed.threshold
    assert first.scores[:228] == changed.scores[:228]


def test_feature_order_mismatch_is_rejected():
    with pytest.raises(ValidationError):
        type(snapshot())(**{**snapshot().model_dump(), "feature_order": ("other",)})


def test_unlabeled_holdout_does_not_claim_metrics():
    original = snapshot()
    samples = tuple(
        s.model_copy(update={"label": None}) if s.partition == "final_holdout" else s
        for s in original.samples
    )
    result = fit_and_score(original.model_copy(update={"samples": samples}))
    assert result.synthetic_metrics["precision"] is None
    assert result.synthetic_metrics["recall"] is None
    assert result.synthetic_metrics["unlabeled"] == 3


def test_missing_normal_validation_is_unavailable():
    original = snapshot()
    samples = tuple(
        s.model_copy(update={"label": None}) if s.partition == "validation" else s
        for s in original.samples
    )
    assert (
        fit_and_score(original.model_copy(update={"samples": samples})).reason
        == "INSUFFICIENT_NORMAL_VALIDATION"
    )


def test_fit_is_deterministic_including_provenance():
    first, second = fit_and_score(snapshot()), fit_and_score(snapshot())
    assert first.scores == second.scores
    assert first.threshold == second.threshold
    assert first.metadata == second.metadata


def test_too_few_training_rows_is_unavailable():
    original = snapshot()
    samples = tuple(s for i, s in enumerate(original.samples) if i != 0)
    assert (
        fit_and_score(original.model_copy(update={"samples": samples})).reason
        == "INSUFFICIENT_TRAIN"
    )


def test_model_package_missing_is_unavailable(monkeypatch):
    import builtins

    original_import = builtins.__import__

    def without_sklearn(name, *args, **kwargs):
        if name == "sklearn.ensemble":
            raise ImportError("not installed")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", without_sklearn)
    assert fit_and_score(snapshot()).reason == "MODEL_DEPENDENCY_MISSING"


def test_snapshot_rejects_late_validation_information():
    from datetime import timedelta

    original = snapshot()
    index = next(i for i, s in enumerate(original.samples) if s.partition == "validation")
    late = original.samples[index].model_copy(
        update={
            "available_at": original.config.partitions[1].information_cutoff + timedelta(seconds=1)
        }
    )
    samples = list(original.samples)
    samples[index] = late
    with pytest.raises(ValidationError):
        fit_and_score(original.model_copy(update={"samples": tuple(samples)}))


def test_future_sample_cannot_be_reassigned_to_train():
    original = snapshot()
    late = original.samples[-1].model_copy(update={"partition": "train"})
    changed = original.model_copy(update={"samples": original.samples[:-1] + (late,)})
    with pytest.raises(ValidationError):
        fit_and_score(changed)


def test_impossible_calendar_feature_is_rejected():
    original = snapshot()
    values = list(original.samples[0].values)
    values[1] = 1.5
    changed = original.samples[0].model_copy(update={"values": tuple(values)})
    with pytest.raises(ValidationError):
        fit_and_score(original.model_copy(update={"samples": (changed,) + original.samples[1:]}))
