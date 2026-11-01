import subprocess
import sys

import pytest

from app.forecasting.cli import _approved_bundle, _file


def test_cli_rejects_missing_explicit_inputs_without_fallback():
    result = subprocess.run(
        [sys.executable, "-m", "app.forecasting.cli", "tune"],
        text=True,
        capture_output=True,
        timeout=30,
    )
    assert result.returncode == 2
    assert "DATABASE_URL" not in result.stdout + result.stderr


def test_bundle_root_requires_absolute_strict_containment_and_existing_paths(tmp_path, monkeypatch):
    root = tmp_path / "approved"
    root.mkdir()
    child = root / "bundle"
    child.mkdir()
    monkeypatch.setenv("FORECAST_APPROVED_BUNDLE_ROOT", str(root))
    assert _approved_bundle(str(child)) == child.resolve()
    for unsafe in (str(root), str(tmp_path), str(root / ".." / "outside"), "relative"):
        with pytest.raises((ValueError, OSError)):
            _approved_bundle(unsafe)
    monkeypatch.delenv("FORECAST_APPROVED_BUNDLE_ROOT")
    with pytest.raises(ValueError):
        _approved_bundle(str(child))
    monkeypatch.setenv("FORECAST_APPROVED_BUNDLE_ROOT", "relative")
    with pytest.raises(ValueError):
        _approved_bundle(str(child))


def test_bundle_root_rejects_symlink(tmp_path, monkeypatch):
    root = tmp_path / "approved"
    root.mkdir()
    target = root / "target"
    target.mkdir()
    link = root / "link"
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("creating symlinks is unavailable")
    monkeypatch.setenv("FORECAST_APPROVED_BUNDLE_ROOT", str(root))
    with pytest.raises(ValueError):
        _approved_bundle(str(link))


def test_safe_failed_receipt_is_published_in_its_scope(tmp_path):
    import json

    from app.forecasting.artifacts import publish_failure, write_failure_receipt
    from tests.forecasting_helpers import config

    receipt = write_failure_receipt(config(), tmp_path / "output", "FIT_FAILED")
    data = json.loads(receipt.read_text(encoding="utf-8"))
    assert data["state"] == "failed" and data["dataset_class"] == "fixture"
    assert set(data) == {
        "state",
        "error_code",
        "mode",
        "dataset_class",
        "reporting_scope",
        "config_sha256",
        "created_at",
        "attempt_id",
    }
    published = publish_failure(receipt, tmp_path / "catalog")
    assert published.parent.name == "failures" and published.parent.parent.name == "research"


def test_owned_relative_config_is_supported_without_allowing_traversal(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "input.json").write_text("{}", encoding="utf-8")
    assert _file("input.json") == b"{}"
    with pytest.raises(ValueError):
        _file("../outside.json")
