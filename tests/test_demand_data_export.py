import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from app.analytics import export
from app.analytics.export import canonical_json, publish_bundle, verify_bundle
from app.analytics.schemas import PipelineError
from app.analytics.semantics import prepare_dataset
from tests.demand_data_helpers import admission, batch, event, instant, software, write_source


def prepared():
    return prepare_dataset(admission(), batch(event()), software())


def recorded_prepared():
    from app.analytics.schemas import Admission, DailyRecord
    from tests.demand_data_helpers import recorded_admission_values, vend_values

    return prepare_dataset(
        Admission(**recorded_admission_values()), batch(DailyRecord(**vend_values())), software()
    )


def reported_prepared():
    from tests.demand_data_helpers import reported_inputs

    return prepare_dataset(*reported_inputs(), software())


def test_reported_bundle_reconciles_records_grid_and_protocol(tmp_path):
    result = publish_bundle(reported_prepared(), tmp_path / "bundles")
    assert result.data_version.startswith("ddv2-")
    before = {p.name: p.read_bytes() for p in result.path.iterdir()}
    assert set(before) == {"manifest.json", "records.jsonl", "observations.jsonl", "quality.json"}
    manifest = json.loads(before["manifest.json"])
    assert manifest["schema_version"] == "demand-data-bundle/2"
    assert manifest["admission"]["rules_version"] == "demand-rules/3"
    assert "files" not in manifest["admission"]["source"]
    assert manifest["counts"]["observations"] == manifest["counts"]["usable_targets"] == 1096
    assert manifest["counts"]["eligible_sum"] == 2192
    assert (
        manifest["counts"]["partition_counts"]["train"]["horizons"]["7"][
            "complete_history_and_target"
        ]
        == 332
    )
    assert "HISTORICAL_AS_OF_NOT_VERIFIED" in manifest["limitations"]
    assert verify_bundle(result.path) == result.data_version
    assert publish_bundle(reported_prepared(), tmp_path / "bundles").reused is True
    assert {p.name: p.read_bytes() for p in result.path.iterdir()} == before


@pytest.mark.parametrize(
    "damage",
    [
        "status",
        "target",
        "raw_zero",
        "missing_day",
        "scope",
        "protocol",
        "horizon_count",
        "knowledge",
        "limitations",
        "limit",
        "source_checksum",
        "lineage",
    ],
)
def test_resealed_reported_bundle_refuses_semantic_forgery(tmp_path, damage):
    import hashlib

    result = publish_bundle(reported_prepared(), tmp_path / "bundles")
    original = {p.name: p.read_bytes() for p in result.path.iterdir()}
    files = dict(original)
    manifest = json.loads(files["manifest.json"])
    observations = [json.loads(v) for v in files["observations.jsonl"].splitlines()]
    records = [json.loads(v) for v in files["records.jsonl"].splitlines()]
    quality = json.loads(files["quality.json"])
    if damage == "status":
        observations[0]["measurement_status"] = "absent_report"
    elif damage == "target":
        observations[0]["target_quantity"] = 3
    elif damage == "raw_zero":
        records[0]["reported_quantity"] = 0
    elif damage == "missing_day":
        observations.pop()
    elif damage == "scope":
        observations[0]["reporting_entity_scope"] = "warehouse"
    elif damage == "protocol":
        manifest["admission"]["protocol"]["history_days"] = 27
    elif damage == "horizon_count":
        quality["partition_counts"]["train"]["horizons"]["7"]["complete_history_and_target"] += 1
        manifest["counts"]["partition_counts"] = quality["partition_counts"]
    elif damage == "knowledge":
        manifest["admission"]["mappings"][0]["available_at"] = "2026-10-24T08:00:00.000000Z"
    elif damage == "limitations":
        manifest["limitations"].remove("CONDITIONAL_NONNEGATIVE_TARGET")
    elif damage == "limit":
        manifest["limits"]["input_rows"] += 1
    elif damage == "source_checksum":
        manifest["source_checksum"] = "e" * 64
    else:
        manifest["admission"]["source_evidence"]["normalized_input_sha256"] = "e" * 64
    files["observations.jsonl"] = b"".join(canonical_json(v) for v in observations)
    files["records.jsonl"] = b"".join(canonical_json(v) for v in records)
    files["quality.json"] = canonical_json(quality)
    if damage == "raw_zero":
        digest = hashlib.sha256(files["records.jsonl"]).hexdigest()
        manifest["admission"]["source_evidence"]["normalized_input_sha256"] = digest
        manifest["source_checksum"] = hashlib.sha256(
            canonical_json([{"format": "jsonl", "sha256": digest}])
        ).hexdigest()
    files["manifest.json"] = canonical_json(manifest)
    target = resealed_copy(result, files)
    with pytest.raises(PipelineError, match="OUTPUT_CONFLICT"):
        verify_bundle(target)
    assert {p.name: p.read_bytes() for p in result.path.iterdir()} == original


@pytest.mark.parametrize("checkpoint", [0, 1, 2, 3, 4])
def test_reported_publication_preserves_atomic_lock_and_path_guards(
    tmp_path, monkeypatch, checkpoint
):
    write, rename, calls = export._write_file, export._rename_stage, 0

    def injected_write(*args):
        nonlocal calls
        current = calls
        calls += 1
        if current == checkpoint:
            raise OSError("private fixture")
        return write(*args)

    def injected_rename(*args):
        if checkpoint == 4:
            raise OSError("private fixture")
        return rename(*args)

    monkeypatch.setattr(export, "_write_file", injected_write)
    monkeypatch.setattr(export, "_rename_stage", injected_rename)
    root = tmp_path / "bundles"
    with pytest.raises(PipelineError, match="IO_UNAVAILABLE"):
        publish_bundle(reported_prepared(), root)
    assert list(root.iterdir()) == []


def test_existing_gross_bundle_verifies_without_new_mode(tmp_path):
    import hashlib

    from tests.demand_data_helpers import old_gross_bundle_bytes

    root = tmp_path / "ddv1-e7b01526ec7b540d6e8c6c335836eafe7fda8bdb85ebb900d789f619ad619fce"
    root.mkdir()
    files = old_gross_bundle_bytes()
    assert {name: hashlib.sha256(body).hexdigest() for name, body in files.items()} == {
        "manifest.json": "9ef9426a5989c1f33d11ce21ccc80dd7b4679ca090619c733451a2f02edf8d13",
        "observations.jsonl": "fa2b79105ded4c60c1346008b6edccf72b5668f283c1ca355677365882ef3efd",
        "quality.json": "e9db6a53ce5c4c34e65b763ab2732c2fbfab248b49e2d1854e4567033ffe0c83",
        "records.jsonl": "4684c0b398beee72173c0bc5fd95cb16c13a850331a953dd2b005693080b89b9",
    }
    for name, body in files.items():
        (root / name).write_bytes(body)
    assert verify_bundle(root) == root.name


def test_both_actual_legacy_bundle_bytes_still_verify(tmp_path):
    import hashlib

    from tests.demand_data_helpers import old_vend_bundle_bytes

    files = old_vend_bundle_bytes()
    assert {name: hashlib.sha256(body).hexdigest() for name, body in files.items()} == {
        "manifest.json": "e8c3d43a047fcaf724ff67aae83ccca4040bdc74a794f987e960175037e16585",
        "observations.jsonl": "13de910303595d1218bc93def8e34cda092d9b8ca2d3ceb7eaff2369e8077d87",
        "quality.json": "c4497d1debca00f5442d5adec6fb36eacd23cb9bb60f7f788396170ebc7f13d9",
        "records.jsonl": "403e619703622ceb8f940ac24837b5599136829c33fdaee1485ebedeaeead8d6",
    }
    root = tmp_path / "ddv1-57717432215abdb96e44336492958281ea5ce76ffb8e4c08c6704d774b8d2a23"
    root.mkdir()
    for name, body in files.items():
        (root / name).write_bytes(body)
    assert verify_bundle(root) == root.name


def test_recorded_vend_bundle_is_deterministic_descriptive_only(tmp_path):
    result = publish_bundle(recorded_prepared(), tmp_path / "bundles")
    before = {p.name: p.read_bytes() for p in result.path.iterdir()}
    manifest = json.loads(before["manifest.json"])
    assert manifest["admission"]["rules_version"] == "demand-rules/2"
    assert manifest["counts"]["usable_targets"] == 0
    assert {
        "RECORDED_VENDS_ONLY",
        "NO_FULFILLMENT_CLAIM",
        "NOT_FORECAST_READY",
        "NO_COMPLETE_TARGETS",
    } <= set(manifest["limitations"])
    assert set(before) == {"manifest.json", "records.jsonl", "observations.jsonl", "quality.json"}
    assert verify_bundle(result.path) == result.data_version
    assert publish_bundle(recorded_prepared(), tmp_path / "bundles").reused is True
    assert {p.name: p.read_bytes() for p in result.path.iterdir()} == before


@pytest.mark.parametrize(
    "damage",
    [
        "rules",
        "gross_zero_targets",
        "warnings",
        "limitations",
        "complete_record",
        "complete_observation",
        "forecast_target",
        "no_positive",
    ],
)
def test_resealed_target_rules_or_forecast_claim_refused(tmp_path, damage):
    import hashlib

    result = publish_bundle(recorded_prepared(), tmp_path / "bundles")
    value = json.loads((result.path / "manifest.json").read_bytes())
    records = [
        json.loads(line) for line in (result.path / "records.jsonl").read_bytes().splitlines()
    ]
    observations = [
        json.loads(line) for line in (result.path / "observations.jsonl").read_bytes().splitlines()
    ]
    quality = json.loads((result.path / "quality.json").read_bytes())
    if damage == "rules":
        value["admission"]["rules_version"] = "demand-rules/1"
    elif damage == "gross_zero_targets":
        value["admission"].update(target="gross_fulfilled_units", rules_version="demand-rules/1")
    elif damage == "warnings":
        quality["warnings"] = []
    elif damage == "limitations":
        value["limitations"].remove("NOT_FORECAST_READY")
    elif damage == "complete_record":
        records[0]["coverage"] = "complete"
    elif damage == "complete_observation":
        observations[0]["coverage"] = "complete"
        value["counts"]["coverage"] = {"complete": 1, "partial": 0, "unknown": 2}
    elif damage == "forecast_target":
        observations[0]["target_quantity"] = 3
        value["counts"]["usable_targets"] = 1
    else:
        records[0].update(quantity=None, coverage="unknown")
        observations[0].update(observed_quantity=None, coverage="unknown")
        value["counts"]["coverage"] = {"complete": 0, "partial": 0, "unknown": 3}
    for name, body in {
        "records.jsonl": b"".join(canonical_json(row) for row in records),
        "observations.jsonl": b"".join(canonical_json(row) for row in observations),
        "quality.json": canonical_json(quality),
    }.items():
        (result.path / name).write_bytes(body)
        value["artifacts"][name] = hashlib.sha256(body).hexdigest()
    identity = {key: item for key, item in value.items() if key != "data_version"}
    value["data_version"] = "ddv1-" + hashlib.sha256(canonical_json(identity)).hexdigest()
    (result.path / "manifest.json").write_bytes(canonical_json(value))
    target = result.path.with_name(value["data_version"])
    result.path.rename(target)
    with pytest.raises(PipelineError, match="OUTPUT_CONFLICT"):
        verify_bundle(target)


def test_same_input_same_bytes_version_and_reuse(tmp_path):
    value = prepared()
    first = publish_bundle(value, tmp_path / "bundles")
    before = {path.name: path.read_bytes() for path in first.path.iterdir()}
    assert set(before) == {"manifest.json", "records.jsonl", "observations.jsonl", "quality.json"}
    assert first.reused is False
    second = publish_bundle(prepared(), tmp_path / "bundles")
    assert (second.data_version, second.reused) == (first.data_version, True)
    assert {path.name: path.read_bytes() for path in second.path.iterdir()} == before
    assert verify_bundle(first.path) == first.data_version
    manifest = json.loads(before["manifest.json"])
    assert manifest["admission"]["dataset_class"] == "fixture"
    assert b"input-root" not in before["manifest.json"]
    assert canonical_json({"z": instant(), "a": "tiếng Việt"}) == (
        '{"a":"tiếng Việt","z":"2026-10-19T08:00:00.000000Z"}\n'.encode()
    )


def resealed_copy(result, files):
    import hashlib

    manifest = json.loads(files["manifest.json"])
    for name in ("records.jsonl", "observations.jsonl", "quality.json"):
        manifest["artifacts"][name] = hashlib.sha256(files[name]).hexdigest()
    identity = {key: value for key, value in manifest.items() if key != "data_version"}
    prefix = "ddv2-" if manifest["schema_version"] == "demand-data-bundle/2" else "ddv1-"
    manifest["data_version"] = prefix + hashlib.sha256(canonical_json(identity)).hexdigest()
    files["manifest.json"] = canonical_json(manifest)
    target = result.path.with_name(manifest["data_version"])
    target.mkdir()
    for name, body in files.items():
        (target / name).write_bytes(body)
    return target


@pytest.mark.parametrize("damage", ["unknown_positive", "partial_null"])
def test_resealed_recorded_observation_coverage_must_match_quantity(tmp_path, damage):
    result = publish_bundle(recorded_prepared(), tmp_path / "bundles")
    original = {path.name: path.read_bytes() for path in result.path.iterdir()}
    files = dict(original)
    rows = [json.loads(line) for line in files["observations.jsonl"].splitlines()]
    manifest = json.loads(files["manifest.json"])
    if damage == "unknown_positive":
        rows[0]["coverage"] = "unknown"
        manifest["counts"]["coverage"] = {"complete": 0, "partial": 0, "unknown": 3}
    else:
        assert rows[1]["observed_quantity"] is None
        rows[1]["coverage"] = "partial"
        manifest["counts"]["coverage"] = {"complete": 0, "partial": 2, "unknown": 1}
    files["manifest.json"] = canonical_json(manifest)
    files["observations.jsonl"] = b"".join(canonical_json(row) for row in rows)
    target = resealed_copy(result, files)
    with pytest.raises(PipelineError, match="OUTPUT_CONFLICT"):
        verify_bundle(target)
    assert {path.name: path.read_bytes() for path in result.path.iterdir()} == original
    assert verify_bundle(result.path) == result.data_version


@pytest.mark.parametrize("proof", ["gross_mapping", "recorded_mapping", "coverage", "availability"])
def test_resealed_future_admission_proofs_refused_for_both_targets(tmp_path, proof):
    from datetime import date

    from tests.demand_data_helpers import day_proof

    value = recorded_prepared() if proof == "recorded_mapping" else prepared()
    if proof == "availability":
        value = prepare_dataset(
            admission(availability=(day_proof(date(2026, 10, 19)),)), batch(event()), software()
        )
    result = publish_bundle(value, tmp_path / "bundles")
    original = {path.name: path.read_bytes() for path in result.path.iterdir()}
    files = dict(original)
    manifest = json.loads(files["manifest.json"])
    field = "mappings" if proof.endswith("mapping") else proof
    manifest["admission"][field][0]["available_at"] = "2026-10-25T08:00:00.000000Z"
    files["manifest.json"] = canonical_json(manifest)
    target = resealed_copy(result, files)
    with pytest.raises(PipelineError, match="OUTPUT_CONFLICT"):
        verify_bundle(target)
    assert {path.name: path.read_bytes() for path in result.path.iterdir()} == original
    assert verify_bundle(result.path) == result.data_version


def test_manifest_safe_summary_is_explicit_versioned_and_verified(tmp_path):
    first = publish_bundle(prepared(), tmp_path / "bundles")
    path = first.path / "manifest.json"
    value = json.loads(path.read_bytes())
    assert value["counts"] == {
        "input_rows": 1,
        "accepted_rows": 1,
        "duplicate_rows": 0,
        "excluded_rows": 0,
        "rejected_rows": 0,
        "normalized_records": 1,
        "observations": 3,
        "usable_targets": 3,
        "coverage": {"complete": 3, "partial": 0, "unknown": 0},
        "lifecycle": {"active": 3, "inactive": 0, "unknown": 0},
        "availability": {"unknown": 3, "stockout_observed": 0, "covered_positive": 0},
        "censoring_risk": {"unknown": 3, "potential": 0, "not_indicated": 0},
    }
    assert value["limits"] == {
        "input_bytes": 67108864,
        "input_files": 32,
        "input_rows": 100000,
        "series_days": 1000000,
    }
    assert value["limitations"] == [
        "AVAILABILITY_UNKNOWN",
        "CENSORING_UNKNOWN",
        "NOT_LATENT_DEMAND",
        "NOT_RESEARCH_DATA",
    ]
    identity = {key: item for key, item in value.items() if key != "data_version"}
    import hashlib

    assert first.data_version == "ddv1-" + hashlib.sha256(canonical_json(identity)).hexdigest()
    value["counts"]["usable_targets"] = 2
    # Even a self-consistent new version hash cannot authorize inaccurate counts.
    identity = {key: item for key, item in value.items() if key != "data_version"}
    value["data_version"] = "ddv1-" + hashlib.sha256(canonical_json(identity)).hexdigest()
    path.write_bytes(canonical_json(value))
    changed = first.path.with_name(value["data_version"])
    first.path.rename(changed)
    with pytest.raises(PipelineError, match="OUTPUT_CONFLICT"):
        verify_bundle(changed)


@pytest.mark.parametrize(
    "damage", ["future_record", "unknown_target", "future_observation", "boolean_counts"]
)
def test_schema_inconsistent_artifacts_refused_even_with_resealed_hashes(tmp_path, damage):
    import hashlib

    result = publish_bundle(prepared(), tmp_path / "bundles")
    manifest_path = result.path / "manifest.json"
    value = json.loads(manifest_path.read_bytes())
    if damage == "boolean_counts":
        value["counts"]["input_rows"] = True
    else:
        name = "records.jsonl" if damage == "future_record" else "observations.jsonl"
        path = result.path / name
        rows = [json.loads(line) for line in path.read_bytes().splitlines()]
        if damage == "future_record":
            rows[0].update(
                occurred_at="2026-10-24T08:00:00.000000Z",
                available_at="2026-10-25T08:00:00.000000Z",
            )
        elif damage == "unknown_target":
            rows[0]["coverage"] = "unknown"
            value["counts"]["coverage"] = {"complete": 2, "partial": 0, "unknown": 1}
            value["limitations"].append("INCOMPLETE_COVERAGE")
            value["limitations"].sort()
        else:
            rows[0]["available_at"] = "2026-10-25T08:00:00.000000Z"
        body = b"".join(canonical_json(row) for row in rows)
        path.write_bytes(body)
        value["artifacts"][name] = hashlib.sha256(body).hexdigest()
    identity = {key: item for key, item in value.items() if key != "data_version"}
    value["data_version"] = "ddv1-" + hashlib.sha256(canonical_json(identity)).hexdigest()
    manifest_path.write_bytes(canonical_json(value))
    target = result.path.with_name(value["data_version"])
    result.path.rename(target)
    with pytest.raises(PipelineError, match="OUTPUT_CONFLICT"):
        verify_bundle(target)


def test_source_snapshot_id_conflict(tmp_path):
    first = publish_bundle(prepared(), tmp_path / "bundles")
    before = {path.name: path.read_bytes() for path in first.path.iterdir()}
    changed = prepared().model_copy(update={"source_checksum": "d" * 64})
    with pytest.raises(PipelineError, match="SOURCE_SNAPSHOT_CONFLICT"):
        publish_bundle(changed, tmp_path / "bundles")
    assert {path.name: path.read_bytes() for path in first.path.iterdir()} == before


@pytest.mark.parametrize("damage", ["tamper", "missing", "extra", "class"])
def test_tampered_or_incomplete_version_not_overwritten(tmp_path, damage):
    first = publish_bundle(prepared(), tmp_path / "bundles")
    if damage == "tamper":
        (first.path / "records.jsonl").write_bytes(b"changed\n")
    elif damage == "missing":
        (first.path / "quality.json").unlink()
    elif damage == "extra":
        (first.path / "private.txt").write_bytes(b"do not remove")
    else:
        path = first.path / "manifest.json"
        manifest = json.loads(path.read_bytes())
        manifest["admission"]["dataset_class"] = "not-research"
        path.write_bytes(canonical_json(manifest))
    before = {path.name: path.read_bytes() for path in first.path.iterdir()}
    with pytest.raises(PipelineError, match="OUTPUT_CONFLICT"):
        publish_bundle(prepared(), tmp_path / "bundles")
    assert {path.name: path.read_bytes() for path in first.path.iterdir()} == before


def test_changed_timezone_rules_or_software_changes_version(tmp_path):
    first = publish_bundle(prepared(), tmp_path / "bundles")
    changed = prepare_dataset(admission(business_timezone="UTC"), batch(event()), software())
    second = publish_bundle(changed, tmp_path / "bundles")
    assert second.data_version != first.data_version
    value = prepared()
    value = value.model_copy(
        update={"software": software().model_copy(update={"implementation_sha256": "e" * 64})}
    )
    assert publish_bundle(value, tmp_path / "bundles").data_version not in {
        first.data_version,
        second.data_version,
    }


def test_input_output_overlap_and_reparse_refused(tmp_path):
    from app.analytics.ingestion import read_source
    from tests.demand_data_helpers import event_values

    input_root = tmp_path / "inputs"
    input_root.mkdir()
    parsed = write_source(input_root, [event_values()])
    value = prepare_dataset(parsed, read_source(parsed, input_root), software())
    for root in (input_root, input_root / "nested", tmp_path, Path.cwd(), Path.home()):
        with pytest.raises(PipelineError, match="OUTPUT_PATH_UNSAFE"):
            publish_bundle(value, root)
    if os.name == "nt":
        target, junction = tmp_path / "target", tmp_path / "junction"
        target.mkdir()
        marker = target / "keep.txt"
        marker.write_bytes(b"preserve")
        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(junction), str(target)],
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            pytest.fail("Windows junction creation NOT VERIFIED; do not skip this host gate.")
        try:
            with pytest.raises(PipelineError, match="OUTPUT_PATH_UNSAFE"):
                publish_bundle(prepared(), junction / "bundles")
            assert marker.read_bytes() == b"preserve"
        finally:
            junction.rmdir()


@pytest.mark.parametrize("checkpoint", [0, 1, 2, 3, 4])
def test_each_write_or_rename_failure_leaves_no_success(tmp_path, monkeypatch, checkpoint):
    write, rename, calls = export._write_file, export._rename_stage, 0

    def injected_write(*args):
        nonlocal calls
        current = calls
        calls += 1
        if current == checkpoint:
            raise OSError("private fixture failure")
        return write(*args)

    def injected_rename(*args):
        if checkpoint == 4:
            raise OSError("private fixture failure")
        return rename(*args)

    monkeypatch.setattr(export, "_write_file", injected_write)
    monkeypatch.setattr(export, "_rename_stage", injected_rename)
    root = tmp_path / "bundles"
    with pytest.raises(PipelineError, match="IO_UNAVAILABLE"):
        publish_bundle(prepared(), root)
    assert list(root.iterdir()) == []


def test_foreign_lock_is_preserved(tmp_path):
    root = tmp_path / "bundles"
    root.mkdir()
    lock = root / ".publish.lock"
    lock.write_bytes(b"foreign-token")
    with pytest.raises(PipelineError, match="OUTPUT_BUSY"):
        publish_bundle(prepared(), root)
    assert lock.read_bytes() == b"foreign-token"


def test_competing_processes_publish_once(tmp_path):
    script = """
import sys
from pathlib import Path
from app.analytics import export
from app.analytics.schemas import PipelineError
from app.analytics.semantics import prepare_dataset
from tests.demand_data_helpers import admission,batch,event,software
if sys.argv[2] == "hold":
    original = export._write_file
    def held(*args):
        if args[0].name == "records.jsonl":
            print("LOCKED", flush=True)
            sys.stdin.readline()
        return original(*args)
    export._write_file = held
try:
    value = prepare_dataset(admission(),batch(event()),software())
    result = export.publish_bundle(value,Path(sys.argv[1]))
    print("REUSED" if result.reused else "PUBLISHED", flush=True)
except PipelineError as error:
    print(error.code, flush=True)
"""
    root = tmp_path / "bundles"
    with subprocess.Popen(
        [sys.executable, "-c", script, str(root), "hold"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    ) as first:
        assert first.stdout.readline().strip() == "LOCKED"
        second = subprocess.run(
            [sys.executable, "-c", script, str(root), "run"],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        assert second.stdout.strip() == "OUTPUT_BUSY"
        output, errors = first.communicate("release\n", timeout=15)
        assert (first.returncode, output.strip(), errors) == (0, "PUBLISHED", "")
    third = subprocess.run(
        [sys.executable, "-c", script, str(root), "run"],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert third.stdout.strip() == "REUSED"
    assert len(list(root.iterdir())) == 1


def test_future_outside_window_data_never_enters_published_records(tmp_path):
    value = prepare_dataset(
        admission(),
        batch(event(event_id="future-leak", occurred_at=instant(24), available_at=instant(25))),
        software(),
    )
    result = publish_bundle(value, tmp_path / "bundles")
    assert (result.path / "records.jsonl").read_bytes() == b""
    quality = json.loads((result.path / "quality.json").read_bytes())
    assert quality["exclusions"] == {"OUTSIDE_WINDOW": 1}
    assert verify_bundle(result.path) == result.data_version
