import pytest

from tests import prepare_replenishment_e2e as fixture
from tests import run_quality_ci as ci


def test_synthetic_fixture_profile_requires_explicit_ci_and_no_research(monkeypatch):
    calls = []
    monkeypatch.setattr(ci, "check_context", lambda: calls.append(True))
    monkeypatch.delenv("QUALITY_CI_PROFILE", raising=False)
    with pytest.raises(ValueError):
        fixture.validate_profile("synthetic-only", None)
    monkeypatch.setenv("QUALITY_CI_PROFILE", "synthetic-only")
    fixture.validate_profile("synthetic-only", None)
    assert calls == [True]
    with pytest.raises(ValueError):
        fixture.validate_profile("synthetic-only", "invented-research")
    with pytest.raises(ValueError):
        fixture.validate_profile("invalid", None)


def test_browser_matrix_covers_each_catalog_once_and_seed_is_strict():
    plan = ci.browser_plan()
    assert plan[0] == ("valid", "valid", "all")
    assert {p for p, _, suite in plan if suite == "replenishment"} == {
        "unavailable",
        "failed",
        "stale",
        "corrupt",
        "unsupported",
    }
    assert {f for _, f, suite in plan if suite == "forecasting"} == {
        "unavailable",
        "failed-valid",
        "corrupt",
        "unsupported",
        "ratio",
    }
    snapshot = {"count": 0, "sha256": "0" * 64}
    seed = {
        "legacy_request_id": 4,
        "binding": [2, 2, "unit"],
        "protected_tables": {"stocks": snapshot, "outbounds": snapshot, "transactions": snapshot},
    }
    ci.validate_seed(seed)
    seed["legacy_request_id"] = True
    with pytest.raises(ci.CIError):
        ci.validate_seed(seed)


def test_browser_coverage_rejects_missing_conditional_node_or_wrong_counts():
    output = "  ✓ 1 real API shows stale state\n  12 skipped\n  2 passed (1s)\n"
    assert ci.browser_coverage(output, "stale", "valid", "replenishment")["passed"] == 2
    with pytest.raises(ci.CIError):
        ci.browser_coverage(output.replace("✓", "-"), "stale", "valid", "replenishment")
    with pytest.raises(ci.CIError):
        ci.browser_coverage(
            output.replace("12 skipped", "13 skipped"), "stale", "valid", "replenishment"
        )
    for policy, forecast, suite in ci.browser_plan():
        if suite == "all":
            title, summary = (
                "admin sees unavailable research in synthetic CI",
                "11 skipped\n35 passed",
            )
        elif suite == "replenishment":
            title, summary = "real API shows " + policy + " state", "12 skipped\n2 passed"
        else:
            title = (
                "finite WAPE is rendered as a percentage"
                if forecast == "ratio"
                else "real server reports " + forecast + " fixture state"
            )
            summary = "8 skipped\n2 passed"
        ci.browser_coverage(f"  ✓ 1 {title}\n{summary}\n", policy, forecast, suite)


def test_browser_context_rejects_nonlocal_docker(monkeypatch):
    responses = iter(["default", '[{"Endpoints":{"docker":{"Host":"tcp://remote"}}}]'])
    monkeypatch.setattr(ci, "browser_command", lambda *args, **kwargs: next(responses))
    with pytest.raises(ci.CIError, match="DOCKER_CONTEXT_INVALID"):
        ci.browser_context({}, [])


def test_ci_context_requires_actual_linux_exact_workspace_and_app(monkeypatch, tmp_path):
    import app

    monkeypatch.chdir(ci.guarded.ROOT)
    monkeypatch.setattr(ci.sys, "platform", "linux")
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("RUNNER_OS", "Linux")
    monkeypatch.setenv("GITHUB_WORKSPACE", str(ci.guarded.ROOT))
    for key in (
        "DOCKER_HOST",
        "DOCKER_CONTEXT",
        "DOCKER_TLS_VERIFY",
        "DOCKER_CERT_PATH",
        "DOCKER_CONFIG",
        "ANALYTICS_DATABASE_URL",
    ):
        monkeypatch.delenv(key, raising=False)
    ci.check_context()
    monkeypatch.setattr(ci.sys, "platform", "win32")
    with pytest.raises(ci.CIError):
        ci.check_context()
    monkeypatch.setattr(ci.sys, "platform", "linux")
    monkeypatch.setenv("GITHUB_WORKSPACE", str(tmp_path))
    with pytest.raises(ci.CIError):
        ci.check_context()
    monkeypatch.setenv("GITHUB_WORKSPACE", str(ci.guarded.ROOT))
    monkeypatch.setattr(app, "__file__", str(tmp_path / "app" / "__init__.py"))
    with pytest.raises(ci.CIError):
        ci.check_context()


@pytest.mark.parametrize(
    "key",
    ["DOCKER_HOST", "DOCKER_CONTEXT", "DOCKER_TLS_VERIFY", "DOCKER_CERT_PATH", "DOCKER_CONFIG"],
)
def test_ci_context_rejects_docker_overrides(monkeypatch, key):
    monkeypatch.chdir(ci.guarded.ROOT)
    monkeypatch.setattr(ci.sys, "platform", "linux")
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("RUNNER_OS", "Linux")
    monkeypatch.setenv("GITHUB_WORKSPACE", str(ci.guarded.ROOT))
    monkeypatch.setenv(key, "untrusted")
    with pytest.raises(ci.CIError):
        ci.check_context()


def test_url_contract_rejects_wrong_identity_or_target():
    main = "postgresql+psycopg://sw_m7_replenishment_test:example@127.0.0.1:18547/sw_m7_replenishment_test"
    migration = main.rsplit("/", 1)[0] + "/sw_m7_replenishment_migration_test"
    ci.validate_urls(main, migration)
    for bad in (main.replace("18547", "5432"), main.replace("127.0.0.1", "localhost"), migration):
        with pytest.raises(ci.CIError):
            ci.validate_urls(bad, migration)
    with pytest.raises(ci.CIError):
        ci.validate_urls("not-a-url", migration)


def test_database_owners_and_foreign_connections_fail_closed():
    expected = [(name, ci.USER) for name in sorted(ci.DATABASES)]
    ci.validate_database_state(expected, 0)
    with pytest.raises(ci.CIError):
        ci.validate_database_state(expected, 1)
    with pytest.raises(ci.CIError):
        ci.validate_database_state([(ci.DATABASES[0], "other")], 0)


def test_node_split_is_exact_and_windows_skips_fail():
    nodes = ci.WINDOWS_NODES
    assert len(nodes) == len(set(nodes)) == 3
    assert all(node.startswith("tests/test_replenishment_verification.py::") for node in nodes)
    ci.validate_windows_report(3, 0, 0, 0)
    for counts in ((3, 1, 0, 0), (2, 0, 0, 0), (3, 0, 1, 0), (3, 0, 0, 1)):
        with pytest.raises(ci.CIError):
            ci.validate_windows_report(*counts)
    ci.validate_collected_nodes("\n".join(nodes))
    with pytest.raises(ci.CIError):
        ci.validate_collected_nodes("\n".join(nodes[:2]))
