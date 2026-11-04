from datetime import date
from decimal import Decimal

import pytest

from tests import run_replenishment_verification as runner


def backend_inspection():
    return (
        {
            "Name": "/" + runner.NAME,
            "Id": "container-id",
            "State": {"Running": True, "Status": "running"},
            "Image": runner.IMAGE,
            "Config": {"Labels": runner.LABELS.copy()},
            "HostConfig": {
                "NetworkMode": runner.NETWORK,
                "PortBindings": {"5432/tcp": [{"HostIp": "127.0.0.1", "HostPort": "18547"}]},
            },
            "Mounts": [
                {
                    "Type": "volume",
                    "Name": runner.VOLUME,
                    "Destination": "/var/lib/postgresql/data",
                    "RW": True,
                }
            ],
            "NetworkSettings": {"Networks": {runner.NETWORK: {"NetworkID": "network-id"}}},
        },
        {"Name": runner.VOLUME, "Labels": runner.LABELS.copy()},
        {
            "Name": runner.NETWORK,
            "Id": "network-id",
            "Labels": runner.LABELS.copy(),
            "Containers": {"container-id": {"Name": runner.NAME}},
        },
    )


def test_backend_guard_rejects_wrong_port_mount_label_or_extra_network():
    container, volume, network = backend_inspection()
    runner.validate_backend_inspection(container, volume, network, running=True)
    container["HostConfig"]["PortBindings"]["5432/tcp"][0]["HostPort"] = "18546"
    with pytest.raises(runner.GuardError):
        runner.validate_backend_inspection(container, volume, network, running=True)


def test_backend_refuses_inherited_analytics_url_before_resource_calls(monkeypatch):
    monkeypatch.setenv("ANALYTICS_DATABASE_URL", "do-not-log-this")
    with pytest.raises(runner.GuardError, match="ENVIRONMENT_INVALID"):
        runner.check_environment()


def test_plan_is_read_only_and_contains_only_public_resource_details(capsys, monkeypatch):
    monkeypatch.setattr(runner, "EXPECTED_ROOT", runner.ROOT)
    assert runner.main(["plan"]) == 0
    output = capsys.readouterr().out
    assert "sw-m7-replenishment-test" in output
    assert "18547" in output
    assert "PASSWORD" not in output
    assert "DATABASE_URL" not in output


def test_database_guard_checks_both_owners_and_competing_sessions():
    assert (
        runner.validate_database_identity(
            "sw_m7_replenishment_test",
            ("sw_m7_replenishment_test", "sw_m7_replenishment_test", "sw_m7_replenishment_test"),
            0,
        )
        is None
    )
    with pytest.raises(runner.GuardError):
        runner.validate_database_identity(
            "sw_m7_replenishment_migration_test",
            ("sw_m7_replenishment_migration_test", "someone", "someone"),
            0,
        )
    with pytest.raises(runner.GuardError):
        runner.validate_database_identity(
            "sw_m7_replenishment_test",
            ("sw_m7_replenishment_test", "sw_m7_replenishment_test", "sw_m7_replenishment_test"),
            1,
        )


def test_backend_check_refuses_wrong_identity_before_connecting(monkeypatch):
    container, volume, network = backend_inspection()
    container["Image"] = "sha256:wrong"
    monkeypatch.setattr(runner, "docker_inspect", lambda *args: (container, volume, network))
    called = []
    monkeypatch.setattr(runner, "check_databases", lambda *args: called.append(True))
    with pytest.raises(runner.GuardError, match="RESOURCE_INVALID"):
        runner.check_backend()
    assert called == []


def test_start_refuses_partial_existing_resources_before_mutating(monkeypatch):
    monkeypatch.setattr(runner, "resource_presence", lambda: (True, False, False))
    called = []
    monkeypatch.setattr(runner, "docker_mutate", lambda *args, **kwargs: called.append(args))
    with pytest.raises(runner.GuardError, match="RESOURCE_COLLISION"):
        runner.start_backend()
    assert called == []


def test_guard_is_active_under_optimized_python():
    import subprocess
    import sys

    script = (
        "from tests import run_replenishment_verification as r; "
        "from tests.test_replenishment_verification import backend_inspection; "
        'c,v,n=backend_inspection(); c["Image"]="wrong"; '
        "r.validate_backend_inspection(c,v,n,running=True)"
    )
    process = subprocess.run([sys.executable, "-O", "-c", script], capture_output=True, text=True)
    assert process.returncode != 0
    assert "RESOURCE_INVALID" in process.stderr


def test_pinned_file_check_rejects_missing_or_changed_bytes(tmp_path):
    import hashlib

    first = tmp_path / "first.json"
    first.write_bytes(b"known")
    expected = {"first.json": hashlib.sha256(b"known").hexdigest()}
    assert runner.verify_pinned_files(tmp_path, expected) == expected
    first.write_bytes(b"changed")
    with pytest.raises(runner.GuardError, match="SOURCE_CHANGED"):
        runner.verify_pinned_files(tmp_path, expected)
    first.unlink()
    with pytest.raises(runner.GuardError, match="SOURCE_CHANGED"):
        runner.verify_pinned_files(tmp_path, expected)


def test_destructive_sql_guard_fails_before_statement_on_foreign_session():
    class Cursor:
        def execute(self, sql, params=None):
            pass

        def fetchone(self):
            return (
                "sw_m7_replenishment_test",
                "sw_m7_replenishment_test",
                "sw_m7_replenishment_test",
                1,
            )

        def close(self):
            pass

    class Raw:
        def cursor(self):
            return Cursor()

    class Dialect:
        name = "postgresql"

    class Connection:
        dialect = Dialect()
        connection = type("Pool", (), {"driver_connection": Raw()})()

    with pytest.raises(runner.GuardError, match="DATABASE_INVALID"):
        runner.guard_destructive_sql(Connection(), "TRUNCATE TABLE products", "owned-marker")


def test_destructive_sql_guard_does_not_touch_sqlite():
    class Connection:
        dialect = type("Dialect", (), {"name": "sqlite"})()

    runner.guard_destructive_sql(Connection(), "DROP TABLE products", "owned-marker")


def test_environment_rejects_docker_endpoint_overrides(monkeypatch):
    monkeypatch.setenv("DOCKER_HOST", "tcp://unapproved.example:2375")
    with pytest.raises(runner.GuardError, match="ENVIRONMENT_INVALID"):
        runner.check_environment()


def test_stopped_or_partial_stack_is_reported_not_ready(monkeypatch):
    monkeypatch.setattr(runner, "resource_presence", lambda: (False, False, False))
    assert runner.check_resource_state() == "ABSENT"
    monkeypatch.setattr(runner, "resource_presence", lambda: (True, False, False))
    with pytest.raises(runner.GuardError, match="RESOURCE_COLLISION"):
        runner.check_resource_state()


def test_pytest_plugin_refuses_missing_or_inherited_malformed_marker(monkeypatch):
    monkeypatch.delenv("M7_PG_MARKER", raising=False)
    with pytest.raises(runner.GuardError, match="MARKER_INVALID"):
        runner.install_sql_guard()
    monkeypatch.setenv("M7_PG_MARKER", "guessed-marker")
    with pytest.raises(runner.GuardError, match="MARKER_INVALID"):
        runner.install_sql_guard()


def test_backend_environment_overrides_inherited_marker_and_database_urls(monkeypatch):
    monkeypatch.setenv("M7_PG_MARKER", "untrusted")
    monkeypatch.setenv("DATABASE_URL", "untrusted")
    monkeypatch.setenv("PGAPPNAME", "untrusted")
    env = runner.backend_child_environment("password")
    assert env["M7_PG_MARKER"] != "untrusted"
    assert env["PGAPPNAME"] == env["M7_PG_MARKER"]
    assert "DATABASE_URL" not in env
    assert env["PYTEST_PLUGINS"] == "tests.run_replenishment_verification"


def test_same_owned_connection_passes_guard_and_checks_both_databases():
    class Cursor:
        def __init__(self):
            self.calls = []

        def execute(self, sql, params=None):
            self.calls.append((sql, params))

        def fetchone(self):
            if "current_setting" not in self.calls[-1][0]:
                return (runner.USER, runner.USER, runner.USER, 0)
            return ("m7-" + "a" * 32,)

        def fetchall(self):
            return sorted((name, runner.USER) for name in runner.DATABASES)

        def close(self):
            pass

    cursor = Cursor()
    raw = type("Raw", (), {"cursor": lambda self: cursor})()
    conn = type(
        "Connection",
        (),
        {
            "dialect": type("Dialect", (), {"name": "postgresql"})(),
            "connection": type("Pool", (), {"driver_connection": raw})(),
        },
    )()
    marker = "m7-" + "a" * 32
    runner.guard_destructive_sql(conn, "DROP TABLE products", marker)
    assert cursor.calls[0][0] == "select pg_stat_clear_snapshot()"
    assert cursor.calls[1][1] == (list(runner.DATABASES), marker)
    assert len(cursor.calls) == 4


def test_docker_context_rejects_remote_daemon(monkeypatch):
    outputs = iter(["desktop-linux", '[{"Endpoints":{"docker":{"Host":"tcp://remote"}}}]'])
    monkeypatch.setattr(runner, "docker_command", lambda *args: next(outputs))
    with pytest.raises(runner.GuardError, match="DOCKER_CONTEXT_INVALID"):
        runner.check_docker_context()


def test_check_on_absent_stack_is_read_only_and_reports_absent(monkeypatch, capsys):
    monkeypatch.setattr(runner, "EXPECTED_ROOT", runner.ROOT)
    monkeypatch.setattr(runner, "check_docker_context", lambda: None)
    monkeypatch.setattr(runner, "check_disk", lambda: None)
    monkeypatch.setattr(runner, "check_resource_state", lambda: "ABSENT")
    monkeypatch.setattr(runner, "port_is_free", lambda: None)
    monkeypatch.setattr(runner, "docker_command", lambda *args: runner.IMAGE)
    called = []
    monkeypatch.setattr(runner, "docker_mutate", lambda *args, **kwargs: called.append(args))
    assert runner.main(["check", "--target", "backend"]) == 0
    assert "ABSENT" in capsys.readouterr().out
    assert called == []


def test_log_redaction_removes_raw_encoded_urls_and_bearer_tokens():
    secrets = ["pa ss", "pa%20ss", "postgresql://user:pa%20ss@localhost/db"]
    text = " ".join(secrets) + " Bearer abc.def.ghi"
    result = runner.redact(text, secrets)
    assert all(value not in result for value in secrets)
    assert "abc.def.ghi" not in result


def test_generated_child_environment_actually_loads_guard_plugin():
    import subprocess
    import sys

    env = runner.backend_child_environment("nonsecret-test-password")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "tests/test_replenishment_verification.py",
            "-k",
            "destructive_sql_guard_does_not_touch_sqlite",
        ],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert "1 passed" in result.stdout


def test_backend_does_not_launch_any_child_when_database_guard_fails(monkeypatch):
    monkeypatch.setattr(
        runner,
        "check_backend",
        lambda: (_ for _ in ()).throw(runner.GuardError("DATABASE_INVALID")),
    )
    called = []
    monkeypatch.setattr(runner, "run_child", lambda *args, **kwargs: called.append(args))
    with pytest.raises(runner.GuardError, match="DATABASE_INVALID"):
        runner.run_backend()
    assert called == []


def test_runner_lock_rejects_simultaneous_owner(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "verification_directory", lambda: tmp_path)
    with runner.execution_lock():
        with pytest.raises(runner.GuardError, match="RUNNER_BUSY"):
            with runner.execution_lock():
                pass
    with runner.execution_lock():
        pass


def test_child_log_is_redacted_before_write(tmp_path, monkeypatch, capsys):
    import sys

    monkeypatch.setattr(runner, "verification_directory", lambda: tmp_path)
    secret = "private-synthetic-password"
    env = runner.backend_child_environment(secret)
    runner.run_child(
        [sys.executable, "-c", 'import os;print(os.environ["TEST_DATABASE_URL"])'],
        env,
        "probe",
        [secret, env["TEST_DATABASE_URL"]],
        timeout=20,
    )
    log = next(tmp_path.glob("probe-*.log")).read_text(encoding="utf8")
    assert secret not in log and env["TEST_DATABASE_URL"] not in log
    assert "[REDACTED]" in log and "exit=0" in log
    assert secret not in capsys.readouterr().out


def test_sql_guard_refuses_wrong_owner_on_other_database():
    class Cursor:
        def execute(self, sql, params=None):
            self.sql = sql

        def fetchone(self):
            if "current_setting" in self.sql:
                return ("m7-" + "a" * 32,)
            return (runner.USER, runner.USER, runner.USER, 0)

        def fetchall(self):
            return [(runner.DATABASES[0], runner.USER), (runner.DATABASES[1], "other")]

        def close(self):
            pass

    raw = type("Raw", (), {"cursor": lambda self: Cursor()})()
    conn = type(
        "Connection",
        (),
        {
            "dialect": type("Dialect", (), {"name": "postgresql"})(),
            "connection": type("Pool", (), {"driver_connection": raw})(),
        },
    )()
    with pytest.raises(runner.GuardError, match="DATABASE_INVALID"):
        runner.guard_destructive_sql(conn, "TRUNCATE TABLE products", "m7-" + "a" * 32)


def test_partial_stage_must_have_exact_owned_and_unattached_resources(monkeypatch):
    monkeypatch.setattr(runner, "resource_presence", lambda: (False, False, True))
    monkeypatch.setattr(
        runner,
        "docker_command",
        lambda *args: '[{"Name":"' + runner.NETWORK + '","Labels":{},"Containers":{}}]',
    )
    with pytest.raises(runner.GuardError, match="RESOURCE_INVALID"):
        runner.validate_creation_stage((False, False, True))


def test_guard_rejects_wrong_network_identity_even_if_name_matches():
    container, volume, network = backend_inspection()
    network["Id"] = "another-network-id"
    with pytest.raises(runner.GuardError, match="RESOURCE_INVALID"):
        runner.validate_backend_inspection(container, volume, network, running=True)


def test_timed_out_child_is_reported_and_not_followed_by_success(tmp_path, monkeypatch):
    import sys

    monkeypatch.setattr(runner, "verification_directory", lambda: tmp_path)
    with pytest.raises(runner.GuardError, match="CHILD_FAILED"):
        runner.run_child(
            [sys.executable, "-c", "import time;time.sleep(10)"],
            runner.backend_child_environment("synthetic"),
            "timeout",
            [],
            timeout=0.2,
        )
    assert "exit=124" in next(tmp_path.glob("timeout-*.log")).read_text(encoding="utf8")


def test_backend_rechecks_database_before_each_child_and_after(monkeypatch):
    events = []
    monkeypatch.setattr(runner, "check_backend", lambda: events.append("guard") or "password")
    monkeypatch.setattr(
        runner, "run_child", lambda command, env, label, secrets, **kw: events.append(label)
    )
    runner.run_backend()
    assert events == ["guard", "backend-migrate", "guard", "backend-pytest", "guard"]


def test_plan_reports_current_source_hashes(capsys, monkeypatch):
    import json

    monkeypatch.setattr(runner, "EXPECTED_ROOT", runner.ROOT)
    assert runner.main(["plan"]) == 0
    value = json.loads(capsys.readouterr().out)
    assert len(value["source_sha256"]["app/replenishment/simulation.py"]) == 64


def test_research_config_freezes_approved_assumptions():
    config = runner.research_config()
    assert (config.mode, config.dataset_class) == ("research", "research")
    assert (config.calibration_start, config.calibration_end) == (
        date(2022, 1, 1),
        date(2022, 7, 1),
    )
    assert (config.evaluation_start, config.evaluation_end) == (date(2022, 7, 1), date(2023, 1, 1))
    assert config.lead_times == (1, 7) and config.minimum_samples == 30
    assert config.service_probabilities == (Decimal(".80"), Decimal(".90"), Decimal(".95"))
    assert (
        config.initial_on_hand,
        config.initial_pipeline,
        config.reservations,
        config.backlog,
    ) == (10000, (), 0, 0)
    assert (config.costs.ordering_cost, config.costs.holding_cost) == (
        Decimal("100000"),
        Decimal("20000"),
    )
    assert config.warmup_days == 7
    assert config.temporal_availability_convention == "retrospective_final_vintage"


def test_research_authorization_is_pinned_research_not_fixture():
    authorization = runner.research_authorization()
    assert authorization.mode == authorization.dataset_class == "research"
    assert authorization.allow_fixture is False and authorization.expected_fixture_binding is None
    assert (
        authorization.bundle_path.name
        == "ddv2-62da0915fdcde6d212f7a5a5c903123a20baed119560be0be17d902eec84b3e7"
    )
    assert len(authorization.bundle_hashes) == 4
    assert (
        authorization.forecast_run_id
        == "frv1-398a6c1c260e5277a15b647d3f383ef2bc5458978386dd05ccf88eee527c7b82"
    )


def test_frozen_file_never_overwrites_different_bytes(tmp_path):
    path = tmp_path / "config.json"
    runner.freeze_bytes(path, b"first")
    runner.freeze_bytes(path, b"first")
    with pytest.raises(runner.GuardError, match="CONFIG_CONFLICT"):
        runner.freeze_bytes(path, b"second")
    assert path.read_bytes() == b"first"


def test_research_repeat_compares_all_scientific_bytes_but_not_receipt(tmp_path):
    first, second = tmp_path / "first", tmp_path / "second"
    first.mkdir()
    second.mkdir()
    for name in runner.SCIENTIFIC_FILES:
        (first / name).write_bytes(b"identical")
        (second / name).write_bytes(b"identical")
    (first / "receipt.json").write_bytes(b"time1")
    (second / "receipt.json").write_bytes(b"time2")
    runner.compare_scientific(first, second)
    (second / "summaries.json").write_bytes(b"changed")
    with pytest.raises(runner.GuardError, match="REPEAT_MISMATCH"):
        runner.compare_scientific(first, second)


def test_research_child_environment_does_not_inherit_database_or_fixture_optin(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "untrusted")
    monkeypatch.setenv("TEST_DATABASE_URL", "untrusted")
    monkeypatch.setenv("FORECAST_APPROVED_BUNDLE_ROOT", "untrusted")
    monkeypatch.setenv("OMP_NUM_THREADS", "99")
    environment = runner.research_environment(runner.M6_ROOT)
    assert environment["PYTHONPATH"] == str(runner.M6_ROOT)
    assert environment["OMP_NUM_THREADS"] == "1"
    assert "DATABASE_URL" not in environment and "TEST_DATABASE_URL" not in environment
    assert "FORECAST_APPROVED_BUNDLE_ROOT" not in environment


def test_research_rechecks_sources_after_failed_computation(monkeypatch):
    calls = []
    monkeypatch.setattr(runner, "source_code_snapshot", lambda: {"checked": "hash"})
    monkeypatch.setattr(runner, "verify_research_sources", lambda: calls.append("checked"))

    def fail():
        raise runner.GuardError("CHILD_FAILED")

    monkeypatch.setattr(runner, "_run_research", fail)
    with pytest.raises(runner.GuardError, match="CHILD_FAILED"):
        runner.run_research()
    assert calls == ["checked", "checked"]


def test_study_eligibility_requires_approved_common_calendar_and_calibration_counts():
    from datetime import date, timedelta
    from types import SimpleNamespace

    algorithms = ("persistence", "seasonal_naive", "xgboost")
    cal = [
        (SimpleNamespace(algorithm=a, horizon=h, origin=date(2022, 1, 1) + timedelta(days=i)),)
        for a in algorithms
        for h, n in ((1, 94), (7, 76))
        for i in range(n)
    ]
    evaluation = [
        (SimpleNamespace(algorithm=a, horizon=h, origin=date(2022, 6, 30) + timedelta(days=i)),)
        for a in algorithms
        for h in (1, 7)
        for i in range(178)
    ]
    runner.check_study_eligibility(cal, evaluation)
    with pytest.raises(runner.GuardError, match="ELIGIBILITY_CHANGED"):
        runner.check_study_eligibility(cal, evaluation[:-1])
    with pytest.raises(runner.GuardError, match="ELIGIBILITY_CHANGED"):
        runner.check_study_eligibility(cal[:-1], evaluation)


def test_runner_lock_rejects_dangling_symlink_path(tmp_path, monkeypatch):
    from pathlib import Path
    from types import SimpleNamespace

    monkeypatch.setattr(runner, "verification_directory", lambda: tmp_path)
    lock = tmp_path / "backend.lock"
    original_is_symlink = Path.is_symlink
    original_lstat = Path.lstat
    monkeypatch.setattr(
        Path, "is_symlink", lambda path: True if path == lock else original_is_symlink(path)
    )
    monkeypatch.setattr(
        Path,
        "lstat",
        lambda path: (
            SimpleNamespace(st_file_attributes=0) if path == lock else original_lstat(path)
        ),
    )
    with pytest.raises(runner.GuardError, match="OUTPUT_INVALID"):
        with runner.execution_lock():
            pass
    assert not lock.exists()


def test_research_orchestrates_private_verify_freeze_reconcile_repeat_and_publish(
    tmp_path, monkeypatch
):
    from types import SimpleNamespace

    from app.replenishment import artifacts, inputs

    monkeypatch.setattr(runner, "ROOT", tmp_path)
    monkeypatch.setattr(runner, "M6_ROOT", tmp_path / "m6")
    (tmp_path / "m6").mkdir()
    (tmp_path / "artifacts/replenishment").mkdir(parents=True)
    monkeypatch.setattr(artifacts, "_owned", lambda path, **kwargs: path)
    monkeypatch.setattr(artifacts, "verify_public_projection", lambda path: None)
    monkeypatch.setattr(inputs, "_checked", lambda path: path)
    monkeypatch.setattr(
        inputs, "load_inputs", lambda *args: SimpleNamespace(forecast=SimpleNamespace(rows=()))
    )
    monkeypatch.setattr(inputs, "select_windows", lambda *args: ())
    monkeypatch.setattr(inputs, "validate_forecast_coverage", lambda *args: None)
    monkeypatch.setattr(runner, "verify_research_sources", lambda: tmp_path / "private")
    monkeypatch.setattr(runner, "check_study_eligibility", lambda *args: None)
    stages = []
    run_id = "rrv1-" + "a" * 64

    def child(command, cwd, label):
        stages.append(label)
        if label == "m6-private-verify":
            assert cwd == runner.M6_ROOT
            return {"run_id": runner.FORECAST_ID, "status": "verified"}
        root = tmp_path / "artifacts/replenishment/research"
        assert (root / "config.json").is_file() and (root / "authorization.json").is_file()
        if label in ("research-run", "research-repeat"):
            output = root / ("runs" if label == "research-run" else "repeat-runs") / run_id
            output.mkdir(parents=True)
            for name in runner.SCIENTIFIC_FILES:
                (output / name).write_bytes(b"synthetic-identical")
            return {"run_id": run_id, "reused": False}
        if label == "research-reconcile":
            return {"status": "reconciled", "cases": 36, "days": 6408}
        return {
            "run_id": run_id,
            "status": "verified" if label == "research-verify" else "published",
        }

    monkeypatch.setattr(runner, "research_child", child)
    result = runner._run_research()
    assert result["run_id"] == run_id
    assert stages == [
        "m6-private-verify",
        "research-run",
        "research-verify",
        "research-reconcile",
        "research-repeat",
        "research-publish",
    ]


def test_research_hashing_is_bounded_and_rejects_tampering(tmp_path):
    import hashlib

    (tmp_path / "small").write_bytes(b"original")
    expected = {"small": hashlib.sha256(b"original").hexdigest()}
    runner.verify_bounded_hashes(tmp_path, expected, limit=8)
    with pytest.raises(runner.GuardError, match="SOURCE_CHANGED"):
        runner.verify_bounded_hashes(tmp_path, expected, limit=7)
    (tmp_path / "small").write_bytes(b"modified")
    with pytest.raises(runner.GuardError, match="SOURCE_CHANGED"):
        runner.verify_bounded_hashes(tmp_path, expected, limit=8)


def test_research_child_records_sanitized_result_and_uses_given_cwd(tmp_path, monkeypatch):
    import sys

    monkeypatch.setattr(runner, "verification_directory", lambda: tmp_path)
    script = (
        'import json,os,sys; print(json.dumps({"cwd":os.getcwd()})); '
        'print("Bearer abc.def.ghi", file=sys.stderr)'
    )
    result = runner.research_child([sys.executable, "-c", script], tmp_path, "research-probe")
    assert result["cwd"] == str(tmp_path)
    content = next(tmp_path.glob("research-probe-*.log")).read_text(encoding="utf8")
    assert "abc.def.ghi" not in content and "Bearer [REDACTED]" in content


def test_backend_urls_use_exact_approved_database_names():
    from sqlalchemy.engine import make_url

    env = runner.backend_child_environment("synthetic-password")
    assert make_url(env["TEST_DATABASE_URL"]).database == "sw_m7_replenishment_test"
    assert (
        make_url(env["TEST_MIGRATION_DATABASE_URL"]).database
        == "sw_m7_replenishment_migration_test"
    )


def test_synthetic_forecast_binding_can_select_owned_m7_entities():
    from tests.replenishment_helpers import fixture_binding

    binding = fixture_binding("ddv1-" + "a" * 64, product_id=2, warehouse_id=2)
    assert (binding.product_id, binding.warehouse_id, binding.unit) == (2, 2, "unit")
    assert (binding.product_key, binding.warehouse_key) == ("product-1", "warehouse-1")


def test_e2e_seed_rejects_unowned_database_before_connecting(monkeypatch):
    import sqlalchemy

    from tests.prepare_replenishment_e2e import seed_owned_database

    monkeypatch.setenv("M7_E2E_SEED_RELEASE", "1")
    monkeypatch.setenv("APP_ENV", "integration")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://wrong:synthetic@db:5432/wrong")
    calls = []
    monkeypatch.setattr(sqlalchemy, "create_engine", lambda *args: calls.append(args))
    with pytest.raises(ValueError, match="DATABASE_INVALID"):
        seed_owned_database()
    assert calls == []


def test_fixture_inventory_rejects_unknown_or_changed_files(tmp_path):
    from tests.prepare_replenishment_e2e import fixture_inventory, require_inventory

    (tmp_path / "sample").write_bytes(b"fixture")
    expected = fixture_inventory(tmp_path)
    require_inventory(tmp_path, expected)
    (tmp_path / "sample").write_bytes(b"changed")
    with pytest.raises(ValueError, match="FIXTURE_CHANGED"):
        require_inventory(tmp_path, expected)
    (tmp_path / "sample").write_bytes(b"fixture")
    (tmp_path / "unexpected").write_bytes(b"other")
    with pytest.raises(ValueError, match="FIXTURE_CHANGED"):
        require_inventory(tmp_path, expected)


def test_existing_fixture_without_final_receipt_fails_closed(tmp_path, monkeypatch):
    from tests import prepare_replenishment_e2e as fixture

    monkeypatch.setattr(fixture, "OUTPUT", tmp_path)
    with pytest.raises(ValueError, match="FIXTURE_INCOMPLETE"):
        fixture.verify_existing()


def test_e2e_settings_use_exact_owner_database_and_explicit_role_credentials():
    from sqlalchemy.engine import make_url

    env, sensitive = runner.e2e_settings("valid", "valid")
    db = make_url(env["M7_DATABASE_URL"])
    assert (db.host, db.database, db.username) == (
        "db",
        "sw_m7_replenishment_e2e",
        "sw_m7_replenishment_e2e",
    )
    assert env["E2E_BASE_URL"] == "http://127.0.0.1:58082"
    assert env["E2E_FORECAST_SCENARIO"] == "valid"
    assert env["E2E_REPLENISHMENT_SCENARIO"] == "valid"
    for role in ("ADMIN", "WAREHOUSE", "CLIENT"):
        assert env["E2E_" + role + "_EMAIL"] == env["M7_" + role + "_EMAIL"]
        assert env["E2E_" + role + "_PASSWORD"] == env["M7_" + role + "_PASSWORD"]
        assert env["M7_" + role + "_PASSWORD"] in sensitive


def test_e2e_bind_guard_accepts_only_exact_desktop_path(tmp_path):
    path = tmp_path / "catalog"
    path.mkdir()
    assert runner.e2e_bind_matches(str(path), path)
    assert not runner.e2e_bind_matches(str(path) + "-other", path)
    assert not runner.e2e_bind_matches(str(path / ".." / "catalog"), path)
    assert not runner.e2e_bind_matches("/host_mnt/unknown", path)


def test_e2e_scenario_mapping_covers_legacy_variants():
    mapping = runner.forecast_scenario_matrix()
    assert set(mapping) == {
        "valid",
        "ratio",
        "unavailable",
        "failed-valid",
        "corrupt",
        "unsupported",
    }
    assert mapping["valid"] == "forecast-research"
    assert mapping["ratio"] == "forecast-ratio"
    assert mapping["failed-valid"] == "forecast-failed"


def test_e2e_absent_guard_rejects_any_project_collision_before_port(monkeypatch):
    monkeypatch.setattr(
        runner,
        "e2e_resource_inventory",
        lambda: {
            "containers": ["sw-m7-replenishment-e2e-api-1"],
            "project_containers": [],
            "volumes": [],
            "project_volumes": [],
            "networks": [],
            "project_networks": [],
        },
    )
    called = []
    monkeypatch.setattr(runner, "e2e_port_free", lambda: called.append(True))
    with pytest.raises(runner.GuardError, match="RESOURCE_COLLISION"):
        runner.e2e_require_absent()
    assert called == []


def test_e2e_staged_copy_detects_source_change(tmp_path):
    source, destination = tmp_path / "source", tmp_path / "staged"
    source.mkdir()
    (source / "module.py").write_bytes(b"original")
    manifest = runner.e2e_copy_tree(source, destination, python_only=True)
    runner.e2e_verify_tree(source, destination, manifest, python_only=True)
    (source / "module.py").write_bytes(b"changed")
    with pytest.raises(runner.GuardError, match="SOURCE_CHANGED"):
        runner.e2e_verify_tree(source, destination, manifest, python_only=True)


def test_e2e_diagnostics_redact_known_credentials_and_bearer(tmp_path):
    (tmp_path / "error-context.md").write_text("sample-secret Bearer abc.def.ghi", encoding="utf8")
    runner.e2e_scrub_diagnostics(tmp_path, ["sample-secret"])
    text = (tmp_path / "error-context.md").read_text(encoding="utf8")
    assert "sample-secret" not in text and "abc.def.ghi" not in text
    assert "[REDACTED]" in text


def test_e2e_compose_guard_rejects_database_or_api_host_ports():
    services = {name: {} for name in ("db", "migrate", "bootstrap", "api", "web")}
    services["api"]["ports"] = [{"published": "8000"}]
    with pytest.raises(runner.GuardError, match="COMPOSE_INVALID"):
        runner.e2e_validate_compose({"services": services}, {})


def test_e2e_keeps_redacted_log_even_if_diagnostic_audit_fails(tmp_path, monkeypatch):
    import sys

    monkeypatch.setattr(runner, "verification_directory", lambda: tmp_path)
    monkeypatch.setattr(
        runner,
        "e2e_scrub_diagnostics",
        lambda *args: (_ for _ in ()).throw(runner.GuardError("DIAGNOSTIC_UNSUPPORTED")),
    )
    env, _ = runner.e2e_settings("valid", "valid")
    with pytest.raises(runner.GuardError, match="DIAGNOSTIC_UNSUPPORTED"):
        runner.e2e_command(
            "audit-probe",
            [sys.executable, "-c", 'print("sensitive-marker")'],
            env,
            ["sensitive-marker"],
            diagnostics=tmp_path,
        )
    log = next(tmp_path.glob("e2e-audit-probe-*.log")).read_text(encoding="utf8")
    assert "sensitive-marker" not in log and "[REDACTED]" in log


def test_e2e_stage_guard_rejects_changed_manifest(tmp_path, monkeypatch):
    stage = tmp_path / "stage"
    source = tmp_path / "source"
    dist = tmp_path / "dist"
    source.mkdir()
    dist.mkdir()
    (source / "module.py").write_bytes(b"original")
    (dist / "index.html").write_bytes(b"html")
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    monkeypatch.setattr(runner, "E2E_STAGE", stage)
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "module.py").write_bytes(b"original")
    (tmp_path / "client").mkdir()
    (tmp_path / "client" / "dist").mkdir()
    (tmp_path / "client" / "dist" / "index.html").write_bytes(b"html")
    monkeypatch.setattr(runner, "e2e_source_snapshot", lambda: {"source": "hash"})
    runner.e2e_create_stage()
    runner.e2e_verify_stage()
    (stage / "app" / "module.py").write_bytes(b"tampered")
    with pytest.raises(runner.GuardError, match="SOURCE_CHANGED"):
        runner.e2e_verify_stage()


def test_e2e_live_guard_rejects_foreign_resource_labels():
    network = {"Name": runner.E2E_NETWORK, "Labels": {"task": "other"}, "Containers": {}}
    volume = {"Name": runner.E2E_VOLUME, "Labels": {"task": "other"}}
    with pytest.raises(runner.GuardError, match="RESOURCE_INVALID"):
        runner.e2e_validate_live([], network, volume, {})


def test_e2e_recovery_rejects_foreign_catalog_before_using_credentials(monkeypatch):
    api = {
        "Config": {"Labels": {"com.docker.compose.service": "api"}},
        "Mounts": [
            {"Destination": "/forecast-catalog", "Source": "unknown"},
            {"Destination": "/replenishment-catalog", "Source": "unknown"},
        ],
    }
    monkeypatch.setattr(runner, "e2e_inspect", lambda: ([api], {}, {}))
    monkeypatch.setattr(runner, "e2e_bind_matches", lambda *args: False)
    with pytest.raises(runner.GuardError, match="RESOURCE_INVALID"):
        runner.e2e_recover_environment()


def test_e2e_seed_receipt_rejects_wrong_binding_or_nonpositive_legacy_id():
    receipt = {
        "binding": [2, 2, "unit"],
        "legacy_request_id": 7,
        "protected_tables": {
            name: {"count": 0, "sha256": "a" * 64}
            for name in ("stocks", "outbounds", "transactions")
        },
    }
    runner.e2e_validate_seed_receipt(receipt)
    receipt["binding"] = [1, 1, "each"]
    with pytest.raises(runner.GuardError, match="SEED_INVALID"):
        runner.e2e_validate_seed_receipt(receipt)


def test_e2e_start_refuses_resource_collision_before_build_or_mutation(monkeypatch):
    monkeypatch.setattr(runner, "check_docker_context", lambda: None)
    monkeypatch.setattr(runner, "check_disk", lambda: None)
    monkeypatch.setattr(runner, "e2e_check_images", lambda: None)
    monkeypatch.setattr(
        runner,
        "e2e_require_absent",
        lambda: (_ for _ in ()).throw(runner.GuardError("RESOURCE_COLLISION")),
    )
    calls = []
    monkeypatch.setattr(runner, "e2e_command", lambda *args, **kwargs: calls.append(args))
    with pytest.raises(runner.GuardError, match="RESOURCE_COLLISION"):
        runner.e2e_start()
    assert calls == []


def test_e2e_frontend_build_uses_same_origin_api(monkeypatch, tmp_path):
    (tmp_path / "client").mkdir()
    monkeypatch.setattr(runner, "ROOT", tmp_path)
    for name in ("E2E_STAGE", "E2E_EMPTY_ENV", "E2E_SEED_RECEIPT"):
        monkeypatch.setattr(runner, name, tmp_path / name)
    for name in ("check_docker_context", "check_disk", "e2e_check_images", "e2e_require_absent"):
        monkeypatch.setattr(runner, name, lambda: None)
    monkeypatch.setattr(runner, "e2e_load_or_prepare_fixture", lambda: {})
    monkeypatch.setattr(runner, "e2e_source_snapshot", lambda: {})
    monkeypatch.setattr(runner, "e2e_settings", lambda *_: ({"PATH": "test", "M7_SECRET": "x"}, []))

    def capture_build(label, command, env, sensitive, **kwargs):
        assert label == "frontend-build"
        assert command == ["npm.cmd", "run", "build"]
        assert env["VITE_API_BASE_URL"] == "/api/v1"
        assert "M7_SECRET" not in env
        raise runner.GuardError("BUILD_CAPTURED")

    monkeypatch.setattr(runner, "e2e_command", capture_build)
    with pytest.raises(runner.GuardError, match="BUILD_CAPTURED"):
        runner.e2e_start()


def test_e2e_suite_plan_covers_every_legacy_negative_catalog():
    plan = runner.e2e_suite_plan("all", "forecast-research")
    assert [(item["policy"], item["forecast"]) for item in plan] == [
        ("valid", "valid"),
        ("valid", "unavailable"),
        ("valid", "corrupt"),
        ("valid", "unsupported"),
    ]
    assert runner.e2e_suite_plan("all", "forecast-ratio")[0]["forecast"] == "ratio"
    assert runner.e2e_suite_plan("all", "forecast-failed")[0]["forecast"] == "failed-valid"
    with pytest.raises(runner.GuardError, match="SCENARIO_INVALID"):
        runner.e2e_suite_plan("all", "corrupt")


def test_e2e_fixture_reuses_verified_roots_and_refuses_partial_roots(tmp_path, monkeypatch):
    from tests import prepare_replenishment_e2e as fixture

    for name in ("OUTPUT", "FORECAST", "BUNDLES", "LEGACY_FORECAST"):
        path = tmp_path / name
        path.mkdir()
        monkeypatch.setattr(fixture, name, path)
    monkeypatch.setattr(fixture, "verify_existing", lambda: {"status": "verified"})
    calls = []
    monkeypatch.setattr(runner, "e2e_command", lambda *args, **kwargs: calls.append(args))
    assert runner.e2e_load_or_prepare_fixture() == {"status": "verified"}
    assert calls == []
    (tmp_path / "FORECAST").rmdir()
    with pytest.raises(runner.GuardError, match="FIXTURE_INCOMPLETE"):
        runner.e2e_load_or_prepare_fixture()


def test_e2e_switch_does_not_mutate_already_selected_catalog(monkeypatch):
    env, sensitive = runner.e2e_settings("valid", "valid")
    identities = {"db": "dbid", "migrate": "mid", "bootstrap": "bid", "api": "aid", "web": "wid"}
    monkeypatch.setattr(runner, "e2e_live_guard", lambda current: identities)
    monkeypatch.setattr(runner, "e2e_verify_stage", lambda: {})
    calls = []
    monkeypatch.setattr(runner, "e2e_command", lambda *args, **kwargs: calls.append(args))
    updated, got = runner.e2e_switch(env, sensitive, "valid", "valid")
    assert updated is env and got == identities and calls == []


def test_e2e_redacts_dynamic_email_as_well_as_known_secret():
    cleaned = runner.e2e_redact("dynamic-user@example.com known-secret", ["known-secret"])
    assert "dynamic-user@example.com" not in cleaned and "known-secret" not in cleaned


def test_playwright_summary_reports_explicit_pass_and_skip_counts():
    assert runner.e2e_test_counts("  5 skipped\n  13 passed (30s)\n") == {
        "passed": 13,
        "skipped": 5,
        "failed": 0,
    }
    with pytest.raises(runner.GuardError, match="TEST_OUTPUT_INVALID"):
        runner.e2e_test_counts("no usable test summary")


def test_e2e_check_dispatch_is_read_only(monkeypatch, capsys):
    monkeypatch.setattr(runner, "EXPECTED_ROOT", runner.ROOT)
    monkeypatch.setattr(runner, "e2e_check", lambda: {"state": "ABSENT"})
    assert runner.main(["check", "--target", "e2e"]) == 0
    assert "ABSENT" in capsys.readouterr().out
