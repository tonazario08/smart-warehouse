import pytest

from app.analytics.schemas import PipelineError
from app.cold_start.dataset import load_fixture_dataset
from tests.cold_start_helpers import fixture_config


def test_loads_verified_fixture_and_rejects_tampering(tmp_path):
    cfg = fixture_config(tmp_path)
    loaded = load_fixture_dataset(cfg, tmp_path)
    assert len(loaded.series) == 6
    path = tmp_path / cfg.skus[0].bundle_path / "observations.jsonl"
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises((ValueError, PipelineError)):
        load_fixture_dataset(cfg, tmp_path)


def test_rejects_duplicate_and_unsafe_paths(tmp_path):
    cfg = fixture_config(tmp_path)
    with pytest.raises((ValueError, PipelineError)):
        load_fixture_dataset(cfg.model_copy(update={"skus": cfg.skus + (cfg.skus[0],)}), tmp_path)
    bad = cfg.skus[0].model_copy(update={"bundle_path": "../outside"})
    with pytest.raises((ValueError, PipelineError)):
        load_fixture_dataset(cfg.model_copy(update={"skus": (bad,) + cfg.skus[1:]}), tmp_path)


def test_rejects_early_report_time_unbounded_values_and_mismatched_identity(tmp_path):
    from datetime import UTC, datetime

    from pydantic import ValidationError

    from app.cold_start.schemas import Observation, SkuInput

    cfg = fixture_config(tmp_path)
    with pytest.raises(ValueError):
        load_fixture_dataset(
            cfg.model_copy(update={"created_at": datetime(2026, 1, 1, tzinfo=UTC)}), tmp_path
        )
    with pytest.raises(ValidationError):
        Observation(
            day=cfg.partitions[0].start, value=-1, available_at=datetime(2026, 1, 1, tzinfo=UTC)
        )
    with pytest.raises(ValidationError):
        SkuInput.model_validate({**cfg.skus[0].model_dump(), "product_key": "x" * 1000})
    bad = cfg.skus[0].model_copy(update={"unit": "wrong"})
    with pytest.raises(ValueError):
        load_fixture_dataset(cfg.model_copy(update={"skus": (bad,) + cfg.skus[1:]}), tmp_path)


def test_real_bundles_reject_namespace_and_missing_availability_policy(tmp_path):
    for name, kwargs in (
        ("namespace", {"namespace_override": "other-fixture"}),
        ("policy", {"no_policy": True}),
    ):
        root = tmp_path / name
        root.mkdir()
        cfg = fixture_config(root, **kwargs)
        with pytest.raises(ValueError):
            load_fixture_dataset(cfg, root)


def test_real_bundle_mask_is_not_a_zero_target(tmp_path):
    from app.cold_start.benchmark import total

    cfg = fixture_config(tmp_path, quantity=0, masked_day=8)
    ds = load_fixture_dataset(cfg, tmp_path)
    row = ds.series[0].observations[8]
    assert row.value is None
    assert total(ds.series[0], row.day, 1) is None


def test_report_time_cannot_precede_snapshot_or_bundle_admission(tmp_path):
    from datetime import UTC, datetime

    cfg = fixture_config(tmp_path)
    earlier = cfg.model_copy(update={"created_at": datetime(2026, 2, 7, tzinfo=UTC)})
    with pytest.raises(ValueError, match="cutoff"):
        load_fixture_dataset(earlier, tmp_path)
    late = cfg.skus[0].snapshot.model_copy(
        update={"available_at": datetime(2027, 1, 1, tzinfo=UTC)}
    )
    sku = cfg.skus[0].model_copy(update={"snapshot": late})
    with pytest.raises(ValueError, match="snapshot"):
        load_fixture_dataset(cfg.model_copy(update={"skus": (sku,) + cfg.skus[1:]}), tmp_path)
