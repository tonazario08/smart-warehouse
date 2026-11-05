from datetime import UTC, datetime

import pytest

from app.cold_start.benchmark import evaluate_cold_start
from app.cold_start.catalog import publish_report, read_report
from app.cold_start.dataset import load_fixture_dataset
from tests.cold_start_helpers import fixture_config


def make_report(root):
    source = root / "source"
    source.mkdir()
    return evaluate_cold_start(load_fixture_dataset(fixture_config(source), source)).model_copy(
        update={"created_at": datetime.now(UTC)}
    )


def test_content_addressed_projection_is_safe_and_detects_tamper(tmp_path):
    report = make_report(tmp_path)
    root = tmp_path / "catalog"
    run_id = publish_report(report, root)
    assert run_id == publish_report(report, root)
    projection = read_report(root, run_id)
    assert projection.fixture_label == "Dữ liệu kiểm thử"
    encoded = projection.model_dump_json()
    assert "supplier" not in encoded and "snapshot" not in encoded and "observations" not in encoded
    assert str(tmp_path) not in encoded and "product-0" not in encoded
    path = root / run_id
    path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(ValueError):
        read_report(root, run_id)


def test_rejects_unsafe_id_unexpected_files_and_symlinks(tmp_path):
    report = make_report(tmp_path)
    root = tmp_path / "catalog"
    run_id = publish_report(report, root)
    with pytest.raises(ValueError):
        read_report(root, "../escape")
    (root / run_id).unlink()
    (root / run_id).mkdir()
    with pytest.raises(ValueError):
        read_report(root, run_id)


def test_projection_rejects_forged_source_version_and_stray_root_file(tmp_path):
    from app.cold_start.catalog import PublicReport, entries

    report = make_report(tmp_path)
    root = tmp_path / "catalog"
    run_id = publish_report(report, root)
    valid = read_report(root, run_id)
    with pytest.raises(ValueError):
        PublicReport.model_validate({**valid.model_dump(), "data_versions": ("untrusted-secret",)})
    (root / "unexpected").write_text("x")
    with pytest.raises(ValueError):
        entries(root)
    with pytest.raises(ValueError):
        publish_report(report, root)


def test_cli_fixture_opt_in_and_real_offline_evaluation(tmp_path, capsys):
    from app.cold_start.cli import main

    source = tmp_path / "source"
    source.mkdir()
    cfg = fixture_config(source)
    path = tmp_path / "fixture.json"
    path.write_text(cfg.model_dump_json(), encoding="utf-8")
    root = tmp_path / "catalog"
    args = [
        "evaluate",
        "--config",
        str(path),
        "--input-root",
        str(source),
        "--output-root",
        str(root),
    ]
    with pytest.raises(SystemExit):
        main(args)
    capsys.readouterr()
    assert main(args + ["--allow-fixture"]) == 0
    run_id = capsys.readouterr().out.strip()
    assert read_report(root, run_id).fixture_label == "Dữ liệu kiểm thử"


def test_atomic_publication_excludes_stage_and_never_clobbers(tmp_path, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor

    from app.cold_start import catalog

    report = make_report(tmp_path)
    root = tmp_path / "catalog"
    root.mkdir()
    original = catalog.os.link
    seen = []

    def link(source, dest):
        seen.append(catalog.entries(root))
        return original(source, dest)

    monkeypatch.setattr(catalog.os, "link", link)
    with ThreadPoolExecutor(max_workers=4) as pool:
        ids = list(pool.map(lambda _: publish_report(report, root), range(4)))
    assert len(set(ids)) == 1 and seen
    assert all(all(not key.startswith(".stage-") for key, _ in snapshot) for snapshot in seen)
    path = root / ids[0]
    assert path.is_file()
    before = path.read_bytes()
    assert publish_report(report, root) == ids[0]
    assert path.read_bytes() == before


def test_projection_labels_scope_and_both_horizons(tmp_path):
    report = make_report(tmp_path)
    root = tmp_path / "catalog"
    value = read_report(root, publish_report(report, root))
    assert value.target == "gross_fulfilled_units"
    assert value.unit == report.unit
    assert value.scope == "single-warehouse-fixture"
    assert {p.horizon for p in value.samples} == {1, 7}


def test_cli_sanitizes_failure_receipt_io_error(tmp_path, monkeypatch, capsys):
    from app.cold_start import cli

    source = tmp_path / "source"
    source.mkdir()
    cfg = fixture_config(source)
    path = tmp_path / "fixture.json"
    path.write_text(cfg.model_dump_json(), encoding="utf-8")

    def unavailable(_):
        raise cli.ColdStartUnavailable()

    def fail(*args):
        raise OSError("private output detail")

    monkeypatch.setattr(cli, "evaluate_cold_start", unavailable)
    monkeypatch.setattr(cli, "publish_failure", fail)
    code = cli.main(
        [
            "evaluate",
            "--config",
            str(path),
            "--input-root",
            str(source),
            "--output-root",
            str(tmp_path / "catalog"),
            "--allow-fixture",
        ]
    )
    assert code == 1
    assert "private output detail" not in capsys.readouterr().out


def test_concurrent_distinct_publications_enforce_capacity_and_preserve_replay(tmp_path):
    import hashlib
    from concurrent.futures import ThreadPoolExecutor
    from datetime import timedelta
    from threading import Barrier

    from app.analytics.export import canonical_json
    from app.cold_start.catalog import PublicFailure, entries, publish_failure

    root = tmp_path / "catalog"
    root.mkdir()
    now = datetime.now(UTC)
    original = {}
    for i in range(127):
        value = PublicFailure(
            created_at=now - timedelta(seconds=i + 1), reason_code="EVALUATION_FAILED"
        )
        body = canonical_json(value)
        key = "csf1-" + hashlib.sha256(body).hexdigest()
        (root / key).write_bytes(body)
        original[key] = body
    barrier = Barrier(2)

    def publish(i):
        barrier.wait()
        try:
            return publish_failure(root, "EVALUATION_FAILED", now + timedelta(seconds=i))
        except ValueError:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        ids = list(pool.map(publish, range(2)))
    assert sum(key is not None for key in ids) == 1
    assert len(entries(root)) == 128
    assert all((root / key).read_bytes() == body for key, body in original.items())
    assert publish_failure(root, "EVALUATION_FAILED", now - timedelta(seconds=1)) in original


def test_foreign_writer_lock_is_not_removed_and_readers_do_not_block(tmp_path):
    from app.cold_start.catalog import entries, publish_failure

    root = tmp_path / "catalog"
    root.mkdir()
    lock = root / ".writer.lock"
    lock.write_bytes(b"")
    assert entries(root) == []
    with pytest.raises(ValueError):
        publish_failure(root, "EVALUATION_FAILED", datetime.now(UTC))
    assert lock.exists()
