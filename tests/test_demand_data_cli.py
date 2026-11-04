import json
import os
import subprocess
import sys

import pytest

from tests.demand_data_helpers import admission_values, event_values, instant, write_source


def fixture_files(tmp_path, rows=None):
    input_root = tmp_path / "inputs"
    input_root.mkdir()
    parsed = write_source(input_root, [event_values()] if rows is None else rows)
    path = input_root / "admission.json"
    path.write_text(parsed.model_dump_json(), encoding="utf-8")
    return path, input_root, tmp_path / "bundles"


def run_cli(*args, env=None):
    return subprocess.run(
        [sys.executable, "-m", "app.analytics.cli", *map(str, args)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        check=False,
        env=env,
    )


@pytest.mark.parametrize("command", ["validate", "build"])
@pytest.mark.parametrize(
    "selector",
    [
        {},
        {"nested": []},
        [[{}]],
        [],
        None,
        0,
        True,
        ["demand-data/1"],
        "demand-data/unknown",
    ],
)
def test_invalid_schema_selector_is_input_error_not_io_failure(tmp_path, command, selector):
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    admission = inputs / "PRIVATE_ADMISSION.json"
    sentinel = "PRIVATE_SCHEMA_VALUE_SENTINEL"
    admission.write_text(
        json.dumps({"schema_version": selector, "private": sentinel}), encoding="utf-8"
    )
    output = tmp_path / "bundles"
    args = [command, "--admission", admission, "--input-root", inputs]
    if command == "build":
        args.extend(("--output-root", output))
    result = run_cli(*args)
    assert result.returncode == 2
    assert result.stdout == ""
    error = json.loads(result.stderr)
    assert set(error) == {"code", "message", "report"}
    assert error["code"] == "ADMISSION_INVALID" and error["report"] is None
    assert sentinel not in result.stderr and str(tmp_path) not in result.stderr
    assert "PRIVATE_ADMISSION" not in result.stderr and "Traceback" not in result.stderr
    assert not output.exists()


def test_reported_cli_build_reuse_keeps_old_commands(tmp_path):
    from tests.demand_data_helpers import reported_rows, write_reported

    inputs = tmp_path / "inputs"
    inputs.mkdir()
    write_reported(inputs, reported_rows())
    admission = inputs / "admission.json"
    checked = run_cli("validate", "--admission", admission, "--input-root", inputs)
    assert (
        checked.returncode == 0
        and json.loads(checked.stdout)["report"]["measurement_counts"]["eligible"] == 1096
    )
    output = tmp_path / "bundles"
    args = ("build", "--admission", admission, "--input-root", inputs, "--output-root", output)
    first = run_cli(*args)
    assert first.returncode == 0 and first.stderr == ""
    result = json.loads(first.stdout)
    assert result["data_version"].startswith("ddv2-") and result["reused"] is False
    assert (
        result["message"] == "Đã công bố bộ dữ liệu doanh số báo cáo để đánh giá hồi cứu; "
        "không xác nhận nhu cầu thực hoặc xuất kho."
    )
    before = {p.name: p.read_bytes() for p in (output / result["data_version"]).iterdir()}
    second = run_cli(*args)
    assert second.returncode == 0 and json.loads(second.stdout) == {**result, "reused": True}
    assert {p.name: p.read_bytes() for p in (output / result["data_version"]).iterdir()} == before
    assert str(tmp_path) not in first.stdout + first.stderr + second.stdout + second.stderr


def test_prepare_mevgal_cli_is_offline_strict_and_private(tmp_path):
    from app.analytics.export import canonical_json
    from tests.demand_data_helpers import rights_values

    raw_root = tmp_path / "raw"
    raw_root.mkdir()
    raw = raw_root / "PRIVATE_SOURCE.zip"
    raw.write_bytes(b"not the public release")
    config = tmp_path / "PRIVATE_CONFIG.json"
    config.write_bytes(
        canonical_json(
            {
                "schema_version": "mevgal-preparation/1",
                "dataset_class": "fixture",
                "rights": rights_values(),
                "acquired_at": instant(19),
                "qualified_at": instant(20),
                "cutoff": instant(23),
            }
        )
    )
    output = tmp_path / "prepared"
    args = ("prepare-mevgal", "--archive", raw, "--config", config, "--destination-root", output)
    result = run_cli(*args)
    assert result.returncode == 2 and json.loads(result.stderr)["code"] == "INPUT_HASH_MISMATCH"
    assert result.stdout == "" and not output.exists()
    for extra in ("--admission", "--input-root", "--output-root"):
        failed = run_cli(*args, extra, "PRIVATE_SENTINEL")
        assert failed.returncode == 2 and json.loads(failed.stderr)["code"] == "ADMISSION_INVALID"
        assert "PRIVATE" not in failed.stdout + failed.stderr
    assert "PRIVATE" not in result.stdout + result.stderr and "Traceback" not in result.stderr


def test_validate_then_build_and_reuse(tmp_path):
    path, inputs, output = fixture_files(tmp_path)
    checked = run_cli("validate", "--admission", path, "--input-root", inputs)
    assert checked.returncode == 0
    assert json.loads(checked.stdout)["report"]["accepted_rows"] == 1
    assert checked.stderr == ""
    assert not output.exists()
    first = run_cli("build", "--admission", path, "--input-root", inputs, "--output-root", output)
    assert first.returncode == 0
    value = json.loads(first.stdout)
    assert set(value) == {"data_version", "reused", "dataset_class", "message"}
    assert value["dataset_class"] == "fixture" and value["reused"] is False
    before = {
        candidate.name: candidate.read_bytes()
        for candidate in (output / value["data_version"]).iterdir()
    }
    second = run_cli("build", "--admission", path, "--input-root", inputs, "--output-root", output)
    assert second.returncode == 0
    assert json.loads(second.stdout) == {**value, "reused": True}
    assert {
        candidate.name: candidate.read_bytes()
        for candidate in (output / value["data_version"]).iterdir()
    } == before


@pytest.mark.parametrize(
    "rows,code",
    [
        ([event_values(available_at=None)], "AVAILABILITY_TIME_REQUIRED"),
        ([event_values(available_at=instant(24))], "AFTER_CUTOFF"),
        ([event_values(quantity=True)], "INPUT_SCHEMA"),
    ],
)
def test_invalid_input_or_time_has_no_manifest(tmp_path, rows, code):
    path, inputs, output = fixture_files(tmp_path, rows)
    result = run_cli("build", "--admission", path, "--input-root", inputs, "--output-root", output)
    assert result.returncode == 2
    assert json.loads(result.stderr)["code"] == code
    assert result.stdout == ""
    assert not output.exists()


def test_import_has_no_settings_db_or_file_effect():
    script = """
import sys, builtins, sqlalchemy
class RefuseSettings:
    def find_spec(self, fullname, *args):
        if fullname in {"app.main", "app.core.config", "app.db.session"}:
            raise AssertionError("application/settings import is forbidden")
sys.meta_path.insert(0, RefuseSettings())
def refuse(*args, **kwargs):
    raise AssertionError("unexpected effect")
sqlalchemy.create_engine = refuse
builtins.open = refuse
import app.analytics.cli
print("SAFE")
"""
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, timeout=15, check=False
    )
    assert (result.returncode, result.stdout.strip(), result.stderr) == (0, "SAFE", "")


def test_secret_sentinel_never_in_stdout_stderr(tmp_path):
    sentinel = "PRIVATE_ARGUMENT_PASSWORD_SENTINEL"
    for args in (
        ("unknown", sentinel),
        ("build", "--admission", sentinel, "--unapproved", sentinel),
    ):
        result = run_cli(*args)
        assert result.returncode == 2
        assert set(json.loads(result.stderr)) == {"code", "message", "report"}
        assert sentinel not in result.stderr + result.stdout
        assert "Traceback" not in result.stderr
    path, inputs, output = fixture_files(tmp_path, [event_values(note=sentinel)])
    result = run_cli("build", "--admission", path, "--input-root", inputs, "--output-root", output)
    assert result.returncode == 2
    assert sentinel not in result.stderr + result.stdout
    assert str(tmp_path) not in result.stderr + result.stdout


def test_failed_snapshot_does_not_publish_or_use_implicit_database(tmp_path):
    values = admission_values()
    from app.analytics.schemas import OPERATIONAL_KINDS, Admission

    values["source"].update(
        kind="operational_b2b",
        files=(),
        channel="managed_b2b_fulfillment",
        kind_map=OPERATIONAL_KINDS,
        availability_policy_ref="recording-policy",
        database_identity={
            "host": "127.0.0.1",
            "port": 18546,
            "database": "sw_m5_demand_test",
            "username": "sw_m5_demand_test",
        },
    )
    path = tmp_path / "admission.json"
    path.write_text(Admission(**values).model_dump_json(), encoding="utf-8")
    env = dict(os.environ)
    env.pop("ANALYTICS_DATABASE_URL", None)
    env["DATABASE_URL"] = "PRIVATE_UNUSED_DATABASE_SENTINEL"
    output = tmp_path / "bundles"
    result = run_cli("build", "--admission", path, "--output-root", output, env=env)
    assert result.returncode == 4
    assert json.loads(result.stderr)["code"] == "DATABASE_UNAVAILABLE"
    assert "PRIVATE_UNUSED" not in result.stderr
    assert not output.exists()


def test_foreign_lock_is_output_exit3_and_never_removed(tmp_path):
    path, inputs, output = fixture_files(tmp_path)
    output.mkdir()
    lock = output / ".publish.lock"
    lock.write_bytes(b"foreign")
    result = run_cli("build", "--admission", path, "--input-root", inputs, "--output-root", output)
    assert result.returncode == 3
    assert json.loads(result.stderr)["code"] == "OUTPUT_BUSY"
    assert lock.read_bytes() == b"foreign"


def test_missing_file_is_safe_io_exit5(tmp_path):
    result = run_cli(
        "validate", "--admission", tmp_path / "PRIVATE_MISSING_INPUT", "--input-root", tmp_path
    )
    assert result.returncode == 5
    assert json.loads(result.stderr)["code"] == "IO_UNAVAILABLE"
    assert "PRIVATE_MISSING_INPUT" not in result.stderr


def test_unmapped_admission_evidence_keeps_safe_mapping_failure_code(tmp_path):
    path, inputs, output = fixture_files(tmp_path)
    value = json.loads(path.read_bytes())
    value["coverage"].append({**value["coverage"][0], "source_product": "not-mapped"})
    path.write_text(json.dumps(value), encoding="utf-8")
    result = run_cli("build", "--admission", path, "--input-root", inputs, "--output-root", output)
    assert result.returncode == 2
    assert json.loads(result.stderr)["code"] == "UNKNOWN_MAPPING"
    assert not output.exists()


def test_future_outside_window_row_is_not_in_cli_bundle(tmp_path):
    path, inputs, output = fixture_files(
        tmp_path,
        [
            event_values(
                event_id="future-leak",
                occurred_at=instant(24),
                available_at=instant(25),
            )
        ],
    )
    result = run_cli("build", "--admission", path, "--input-root", inputs, "--output-root", output)
    assert result.returncode == 0
    bundle = output / json.loads(result.stdout)["data_version"]
    assert (bundle / "records.jsonl").read_bytes() == b""
    assert json.loads((bundle / "quality.json").read_bytes())["exclusions"] == {"OUTSIDE_WINDOW": 1}


@pytest.mark.parametrize("after_write", [False, True])
def test_interrupted_write_has_no_success_or_orphan_owned_lock(tmp_path, after_write):
    path, inputs, output = fixture_files(tmp_path)
    script = """
import sys
from app.analytics import cli, export
original=export._write_file
def interrupted(*args):
    if sys.argv[1] == "after":
        original(*args)
    raise KeyboardInterrupt
export._write_file = interrupted
raise SystemExit(cli.main(sys.argv[2:]))
"""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            script,
            "after" if after_write else "before",
            "build",
            "--admission",
            str(path),
            "--input-root",
            str(inputs),
            "--output-root",
            str(output),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        check=False,
    )
    assert result.returncode == 130
    assert json.loads(result.stderr)["code"] == "INTERRUPTED"
    assert result.stdout == ""
    assert list(output.iterdir()) == []


def test_partial_interruption_is_130_and_unknown_bytes_are_not_deleted(tmp_path):
    path, inputs, output = fixture_files(tmp_path)
    script = """
import sys
from app.analytics import cli, export
def interrupted(path, content):
    path.write_bytes(b"partial-unknown-bytes")
    raise KeyboardInterrupt
export._write_file=interrupted
raise SystemExit(cli.main(sys.argv[1:]))
"""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            script,
            "build",
            "--admission",
            str(path),
            "--input-root",
            str(inputs),
            "--output-root",
            str(output),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        check=False,
    )
    assert result.returncode == 130
    assert result.stdout == ""
    assert json.loads(result.stderr)["code"] == "INTERRUPTED"
    entries = list(output.iterdir())
    assert len(entries) == 1 and entries[0].name.startswith(".staging-")
    assert (entries[0] / "records.jsonl").read_bytes() == b"partial-unknown-bytes"
    assert not list(output.glob("ddv1-*"))


@pytest.mark.parametrize(
    "key", ["host", "hostaddr", "port", "dbname", "user", "service", "options"]
)
def test_explicit_url_override_never_reaches_engine(tmp_path, key):
    from app.analytics.schemas import OPERATIONAL_KINDS, Admission

    values = admission_values()
    values["source"].update(
        kind="operational_b2b",
        files=(),
        channel="managed_b2b_fulfillment",
        kind_map=OPERATIONAL_KINDS,
        availability_policy_ref="recording-policy",
        database_identity={
            "host": "127.0.0.1",
            "port": 18546,
            "database": "sw_m5_demand_test",
            "username": "sw_m5_demand_test",
        },
    )
    path = tmp_path / "admission.json"
    path.write_text(Admission(**values).model_dump_json(), encoding="utf-8")
    env = dict(
        os.environ,
        ANALYTICS_DATABASE_URL=(
            "postgresql+psycopg://sw_m5_demand_test:PRIVATE_PASSWORD@127.0.0.1:18546/"
            "sw_m5_demand_test?" + key + "=PRIVATE_OVERRIDE"
        ),
    )
    script = """
import sys, sqlalchemy
def refuse(*args, **kwargs):
    raise AssertionError("engine must not be created")
sqlalchemy.create_engine=refuse
from app.analytics.cli import main
raise SystemExit(main(sys.argv[1:]))
"""
    result = subprocess.run(
        [sys.executable, "-c", script, "validate", "--admission", str(path)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
        check=False,
        env=env,
    )
    assert result.returncode == 4
    assert json.loads(result.stderr)["code"] == "DATABASE_IDENTITY"
    assert "PRIVATE_" not in result.stdout + result.stderr


def test_recorded_vends_build_reuse_and_private_output(tmp_path):
    from tests.demand_data_helpers import vend_values, write_vends

    inputs = tmp_path / "PRIVATE_INPUTS"
    inputs.mkdir()
    admitted = write_vends(inputs, [vend_values()])
    path = inputs / "admission.json"
    path.write_text(admitted.model_dump_json(), encoding="utf-8")
    output = tmp_path / "PRIVATE_BUNDLES"
    checked = run_cli("validate", "--admission", path, "--input-root", inputs)
    assert checked.returncode == 0 and checked.stderr == ""
    assert "NOT_FORECAST_READY" in json.loads(checked.stdout)["report"]["warnings"]
    command = ("build", "--admission", path, "--input-root", inputs, "--output-root", output)
    first = run_cli(*command)
    assert first.returncode == 0 and first.stderr == ""
    value = json.loads(first.stdout)
    assert set(value) == {"data_version", "reused", "dataset_class", "message"}
    assert "mô tả" in value["message"] and "không xác nhận" in value["message"]
    assert "PRIVATE_" not in first.stdout
    assert value["reused"] is False
    before = {p.name: p.read_bytes() for p in (output / value["data_version"]).iterdir()}
    second = run_cli(*command)
    assert second.returncode == 0 and second.stderr == ""
    assert json.loads(second.stdout) == {**value, "reused": True}
    assert {p.name: p.read_bytes() for p in (output / value["data_version"]).iterdir()} == before
    # The same partial data never gets an implicit gross fallback/exception.
    values = json.loads(path.read_bytes())
    values["target"] = "gross_fulfilled_units"
    path.write_text(json.dumps(values), encoding="utf-8")
    rejected = run_cli(*command)
    assert rejected.returncode == 2
    assert json.loads(rejected.stderr)["code"] == "NO_OBSERVED_TARGETS"
    assert len(list(output.iterdir())) == 1
