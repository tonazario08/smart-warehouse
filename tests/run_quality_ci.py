"""Guarded GitHub-hosted CI backend orchestration."""

import json
import os
import re
import secrets
import socket
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import quote
from urllib.request import urlopen

from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

from tests import run_replenishment_verification as guarded

USER = guarded.USER
DATABASES = guarded.DATABASES
WINDOWS_NODES = tuple(
    "tests/test_replenishment_verification.py::" + name
    for name in (
        "test_runner_lock_rejects_simultaneous_owner",
        "test_runner_lock_rejects_dangling_symlink_path",
        "test_e2e_bind_guard_accepts_only_exact_desktop_path",
    )
)


class CIError(Exception):
    pass


def validate_urls(main, migration):
    try:
        urls = [make_url(main), make_url(migration)]
        for url, database in zip(urls, DATABASES, strict=True):
            if (
                (url.drivername, url.host, url.port, url.username, url.database)
                != ("postgresql+psycopg", "127.0.0.1", 18547, USER, database)
                or not url.password
                or url.query
            ):
                raise CIError("DATABASE_INVALID")
        if urls[0].password != urls[1].password:
            raise CIError("DATABASE_INVALID")
    except (ArgumentError, ValueError, TypeError):
        raise CIError("DATABASE_INVALID") from None


def validate_database_state(owners, competing):
    if owners != sorted((name, USER) for name in DATABASES) or competing != 0:
        raise CIError("DATABASE_INVALID")


def validate_windows_report(tests, skipped, failures, errors):
    if (tests, skipped, failures, errors) != (3, 0, 0, 0):
        raise CIError("WINDOWS_COVERAGE_INVALID")


def validate_collected_nodes(output):
    actual = [line.strip() for line in output.splitlines() if line.startswith("tests/")]
    if len(actual) != 3 or set(actual) != set(WINDOWS_NODES):
        raise CIError("WINDOWS_COVERAGE_INVALID")


def check_context():
    import app

    if (
        sys.platform != "linux"
        or os.environ.get("GITHUB_ACTIONS") != "true"
        or os.environ.get("RUNNER_OS") != "Linux"
        or any(
            os.environ.get(k) is not None
            for k in (
                "DOCKER_HOST",
                "DOCKER_CONTEXT",
                "DOCKER_TLS_VERIFY",
                "DOCKER_CERT_PATH",
                "DOCKER_CONFIG",
                "ANALYTICS_DATABASE_URL",
            )
        )
        or (guarded.ROOT / ".env").exists()
        or Path.cwd().resolve() != guarded.ROOT
    ):
        raise CIError("ENVIRONMENT_INVALID")
    try:
        workspace = Path(os.environ.get("GITHUB_WORKSPACE", ""))
        if (
            not workspace.is_absolute()
            or workspace.resolve(strict=True) != guarded.ROOT
            or not Path(app.__file__).resolve(strict=True).is_relative_to(guarded.ROOT / "app")
        ):
            raise CIError("ENVIRONMENT_INVALID")
    except (OSError, TypeError, ValueError):
        raise CIError("ENVIRONMENT_INVALID") from None


def database_guard(env, *, initialize=False):
    import psycopg

    main, migration = env["TEST_DATABASE_URL"], env["TEST_MIGRATION_DATABASE_URL"]
    validate_urls(main, migration)
    url = make_url(main)
    with psycopg.connect(
        host=url.host,
        port=url.port,
        dbname=url.database,
        user=url.username,
        password=url.password,
        application_name=env["M7_PG_MARKER"],
        autocommit=True,
    ) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "select current_database(), current_user, pg_get_userbyid(datdba) "
                "from pg_database where datname=current_database()"
            )
            if cursor.fetchone() != (DATABASES[0], USER, USER):
                raise CIError("DATABASE_INVALID")
            cursor.execute("select pg_stat_clear_snapshot()")
            cursor.execute(
                "select count(*) from pg_stat_activity where datname = any(%s) "
                "and pid <> pg_backend_pid() and backend_type='client backend' "
                "and application_name <> %s",
                (list(DATABASES), env["M7_PG_MARKER"]),
            )
            competing = cursor.fetchone()[0]
            owner_sql = (
                "select datname, pg_get_userbyid(datdba) from pg_database "
                "where datname=any(%s) order by datname"
            )
            cursor.execute(owner_sql, (list(DATABASES),))
            owners = cursor.fetchall()
            if initialize and owners == [(DATABASES[0], USER)] and competing == 0:
                cursor.execute(
                    'CREATE DATABASE "sw_m7_replenishment_migration_test" '
                    'OWNER "sw_m7_replenishment_test"'
                )
                cursor.execute(owner_sql, (list(DATABASES),))
                owners = cursor.fetchall()
            validate_database_state(owners, competing)


def run_backend():
    check_context()
    main = os.environ.get("TEST_DATABASE_URL", "")
    migration = os.environ.get("TEST_MIGRATION_DATABASE_URL", "")
    validate_urls(main, migration)
    if os.environ.get("DATABASE_URL") != main:
        raise CIError("DATABASE_INVALID")
    password = make_url(main).password
    env = guarded.backend_child_environment(password)
    database_guard(env, initialize=True)
    collected = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", *WINDOWS_NODES],
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    validate_collected_nodes(collected.stdout)
    database_guard(env)
    migration_code = (
        "import os; from tests.run_replenishment_verification import install_sql_guard; "
        "from alembic.config import Config; from alembic import command; "
        "install_sql_guard(); c=Config('alembic.ini'); "
        "c.set_main_option('sqlalchemy.url',os.environ['TEST_DATABASE_URL'].replace('%','%%')); "
        "command.upgrade(c,'head')"
    )
    subprocess.run([sys.executable, "-c", migration_code], env=env, check=True)
    database_guard(env)
    args = [sys.executable, "-m", "pytest", "-q"]
    args.extend("--deselect=" + node for node in WINDOWS_NODES)
    subprocess.run(args, env=env, check=True)
    database_guard(env)


def run_windows():
    if os.name != "nt":
        raise CIError("WINDOWS_REQUIRED")
    with tempfile.TemporaryDirectory() as folder:
        report = Path(folder) / "results.xml"
        subprocess.run(
            [sys.executable, "-m", "pytest", "-q", *WINDOWS_NODES, "--junitxml=" + str(report)],
            check=True,
        )
        root = ET.parse(report).getroot()
        cases = list(root.iter("testcase"))
        validate_windows_report(
            len(cases),
            sum(c.find("skipped") is not None for c in cases),
            sum(c.find("failure") is not None for c in cases),
            sum(c.find("error") is not None for c in cases),
        )


CI_PROJECT = "sw-quality-replenishment-ci"
CI_NETWORK = CI_PROJECT + "-net"
CI_VOLUME = CI_PROJECT + "-data"
CI_LABELS = {"task": "verify-m7-merge-ci", "role": "browser-test"}


def browser_plan():
    return (
        [("valid", "valid", "all")]
        + [
            (policy, "valid", "replenishment")
            for policy in ("unavailable", "failed", "stale", "corrupt", "unsupported")
        ]
        + [
            ("valid", forecast, "forecasting")
            for forecast in ("unavailable", "failed-valid", "corrupt", "unsupported", "ratio")
        ]
    )


def browser_environment(fixture):
    from app.auth.schemas import RegisterRequest

    env = os.environ.copy()
    env.update(
        {
            "CI_DB_PASSWORD": secrets.token_urlsafe(32),
            "CI_JWT_SECRET": secrets.token_urlsafe(48),
            "E2E_BASE_URL": "http://127.0.0.1:58082",
            "E2E_REPLENISHMENT_PROFILE": "synthetic-only",
            "E2E_REPLENISHMENT_RUN_ID": fixture["fixture_run_id"],
            "E2E_REPLENISHMENT_RESEARCH_RUN_ID": "",
        }
    )
    sensitive = [env["CI_DB_PASSWORD"], env["CI_JWT_SECRET"]]
    for role in ("ADMIN", "WAREHOUSE", "CLIENT"):
        email = f"quality-{role.lower()}@example.com"
        password = secrets.token_urlsafe(32)
        RegisterRequest.model_validate({"email": email, "password": password})
        env[f"CI_{role}_EMAIL"] = env[f"E2E_{role}_EMAIL"] = email
        env[f"CI_{role}_PASSWORD"] = env[f"E2E_{role}_PASSWORD"] = password
        sensitive.extend((email, password, quote(password, safe="")))
    env["CI_DATABASE_URL"] = (
        "postgresql+psycopg://sw_m7_replenishment_e2e:"
        + quote(env["CI_DB_PASSWORD"], safe="")
        + "@db:5432/sw_m7_replenishment_e2e"
    )
    sensitive.extend((env["CI_DATABASE_URL"], quote(env["CI_DATABASE_URL"], safe="")))
    return env, sensitive


def browser_command(command, env, sensitive, *, cwd=None, input_text=None, timeout=1800):
    result = subprocess.run(
        command,
        cwd=cwd or guarded.ROOT,
        env=env,
        input=input_text,
        capture_output=True,
        text=True,
        errors="replace",
        timeout=timeout,
    )
    output = guarded.e2e_redact(result.stdout, sensitive)
    if result.returncode:
        print(output + guarded.e2e_redact(result.stderr, sensitive), file=sys.stderr)
        raise CIError("BROWSER_CHILD_FAILED")
    return output


def browser_compose(envfile):
    return [
        "docker",
        "compose",
        "-p",
        CI_PROJECT,
        "--env-file",
        str(envfile),
        "-f",
        "docker-compose.quality-e2e.yml",
    ]


def browser_coverage(output, policy, forecast, suite):
    counts = guarded.e2e_test_counts(output)
    if suite == "all":
        expected, title = (35, 11), "admin sees unavailable research in synthetic CI"
    elif suite == "replenishment":
        expected, title = (2, 12), "real API shows " + policy + " state"
    else:
        expected = (2, 8)
        title = (
            "finite WAPE is rendered as a percentage"
            if forecast == "ratio"
            else "real server reports " + forecast + " fixture state"
        )
    if (counts["passed"], counts["skipped"], counts["failed"]) != (*expected, 0):
        raise CIError("BROWSER_COVERAGE_INVALID")
    clean = re.sub(r"\x1b\[[0-9;]*m", "", output)
    if not re.search(r"(?m)^\s*✓[^\n]*" + re.escape(title), clean):
        raise CIError("BROWSER_COVERAGE_INVALID")
    return counts


def browser_context(env, sensitive):
    name = browser_command(["docker", "context", "show"], env, sensitive).strip()
    context = json.loads(browser_command(["docker", "context", "inspect", name], env, sensitive))
    if (
        len(context) != 1
        or context[0]["Endpoints"]["docker"]["Host"] != "unix:///var/run/docker.sock"
    ):
        raise CIError("DOCKER_CONTEXT_INVALID")


def browser_compose_guard(base, env, sensitive):
    config = json.loads(browser_command([*base, "config", "--format", "json"], env, sensitive))
    services = config["services"]
    if set(services) != {"db", "migrate", "bootstrap", "api", "web"}:
        raise CIError("COMPOSE_INVALID")
    for name, item in services.items():
        if item.get("env_file") or any(
            item.get("labels", {}).get(k) != v for k, v in CI_LABELS.items()
        ):
            raise CIError("COMPOSE_INVALID")
        if name != "web" and item.get("ports"):
            raise CIError("COMPOSE_INVALID")
    ports = services["web"].get("ports", [])
    if len(ports) != 1 or (
        ports[0].get("target"),
        str(ports[0].get("published")),
        ports[0].get("host_ip"),
        ports[0].get("protocol"),
    ) != (8080, "58082", "127.0.0.1", "tcp"):
        raise CIError("COMPOSE_INVALID")
    for name in ("migrate", "bootstrap", "api", "web"):
        build = services[name].get("build", {})
        expected = guarded.ROOT / "client" if name == "web" else guarded.ROOT
        if (
            Path(build.get("context", "")).resolve() != expected
            or build.get("dockerfile") != "Dockerfile"
        ):
            raise CIError("COMPOSE_INVALID")
    if services["db"].get("image") != "postgres:16-alpine":
        raise CIError("COMPOSE_INVALID")
    if (
        config["networks"]["internal"]["name"] != CI_NETWORK
        or config["volumes"]["database"]["name"] != CI_VOLUME
    ):
        raise CIError("COMPOSE_INVALID")
    for item in services["api"]["volumes"]:
        expected = {
            "/forecast-catalog": env["CI_FORECAST_CATALOG"],
            "/replenishment-catalog": env["CI_POLICY_CATALOG"],
        }
        if (
            item.get("type") != "bind"
            or item.get("read_only") is not True
            or item.get("target") not in expected
            or Path(item["source"]).resolve() != Path(expected[item["target"]]).resolve()
        ):
            raise CIError("COMPOSE_INVALID")
    if len(services["api"]["volumes"]) != 2:
        raise CIError("COMPOSE_INVALID")


def browser_absent(env, sensitive):
    for kind in ("container", "network", "volume"):
        flags = ["-aq"] if kind == "container" else ["-q"]
        output = browser_command(
            [
                "docker",
                kind,
                "ls",
                *flags,
                "--filter",
                "label=com.docker.compose.project=" + CI_PROJECT,
            ],
            env,
            sensitive,
        )
        if output.strip():
            raise CIError("RESOURCE_COLLISION")
    for kind, name in (("network", CI_NETWORK), ("volume", CI_VOLUME)):
        output = browser_command(["docker", kind, "ls", "--format", "{{.Name}}"], env, sensitive)
        if name in output.splitlines():
            raise CIError("RESOURCE_COLLISION")
    names = browser_command(
        ["docker", "container", "ls", "-a", "--format", "{{.Names}}"], env, sensitive
    )
    if set(names.splitlines()) & {
        f"{CI_PROJECT}-{name}-1" for name in ("db", "api", "web", "migrate", "bootstrap")
    }:
        raise CIError("RESOURCE_COLLISION")
    with socket.socket() as port:
        port.bind(("127.0.0.1", 58082))


def browser_guard(env, sensitive):
    ids = browser_command(
        ["docker", "ps", "-aq", "--filter", "label=com.docker.compose.project=" + CI_PROJECT],
        env,
        sensitive,
    ).split()
    if len(ids) != 5:
        raise CIError("RESOURCE_INVALID")
    containers = json.loads(browser_command(["docker", "inspect", *ids], env, sensitive))
    services = {}
    for item in containers:
        labels = item["Config"]["Labels"] or {}
        service = labels.get("com.docker.compose.service")
        if any(labels.get(k) != v for k, v in CI_LABELS.items()) or service in services:
            raise CIError("RESOURCE_INVALID")
        services[service] = item
    if set(services) != {"db", "migrate", "bootstrap", "api", "web"}:
        raise CIError("RESOURCE_INVALID")
    for name, item in services.items():
        expected_image = "postgres:16-alpine" if name == "db" else f"{CI_PROJECT}-{name}"
        if item["Config"]["Image"] != expected_image:
            raise CIError("RESOURCE_INVALID")
    for name in ("db", "api", "web"):
        if not services[name]["State"]["Running"]:
            raise CIError("RESOURCE_INVALID")
    for name in ("db", "api"):
        if services[name]["State"].get("Health", {}).get("Status") != "healthy":
            raise CIError("RESOURCE_INVALID")
    for name in ("migrate", "bootstrap"):
        if services[name]["State"]["ExitCode"] != 0 or services[name]["State"]["Running"]:
            raise CIError("RESOURCE_INVALID")
    for name in ("db", "migrate", "bootstrap", "api"):
        if services[name]["HostConfig"]["PortBindings"]:
            raise CIError("RESOURCE_INVALID")
    ports = services["web"]["HostConfig"]["PortBindings"]
    if ports != {"8080/tcp": [{"HostIp": "127.0.0.1", "HostPort": "58082"}]}:
        raise CIError("RESOURCE_INVALID")
    for name in ("db", "api", "web"):
        if set(services[name]["NetworkSettings"]["Networks"]) != {CI_NETWORK}:
            raise CIError("RESOURCE_INVALID")
    mounts = services["api"]["Mounts"]
    expected = {
        "/forecast-catalog": env["CI_FORECAST_CATALOG"],
        "/replenishment-catalog": env["CI_POLICY_CATALOG"],
    }
    if len(mounts) != 2 or any(
        m["Type"] != "bind"
        or m["RW"]
        or m["Destination"] not in expected
        or Path(m["Source"]).resolve() != Path(expected[m["Destination"]]).resolve()
        for m in mounts
    ):
        raise CIError("RESOURCE_INVALID")
    if not any(
        m.get("Name") == CI_VOLUME and m["Destination"] == "/var/lib/postgresql/data"
        for m in services["db"]["Mounts"]
    ):
        raise CIError("RESOURCE_INVALID")
    for kind, name in (("network", CI_NETWORK), ("volume", CI_VOLUME)):
        data = json.loads(browser_command(["docker", kind, "inspect", name], env, sensitive))[0]
        if data["Name"] != name or any(
            (data.get("Labels") or {}).get(k) != v for k, v in CI_LABELS.items()
        ):
            raise CIError("RESOURCE_INVALID")
        if kind == "network" and set((data.get("Containers") or {}).keys()) != {
            services[name]["Id"] for name in ("db", "api", "web")
        }:
            raise CIError("RESOURCE_INVALID")
    identity = browser_command(
        [
            "docker",
            "exec",
            services["db"]["Id"],
            "psql",
            "-U",
            "sw_m7_replenishment_e2e",
            "-d",
            "sw_m7_replenishment_e2e",
            "-Atc",
            "select current_database(),current_user,pg_get_userbyid(datdba) "
            "from pg_database where datname=current_database()",
        ],
        env,
        sensitive,
    ).strip()
    if identity != "sw_m7_replenishment_e2e|sw_m7_replenishment_e2e|sw_m7_replenishment_e2e":
        raise CIError("DATABASE_INVALID")
    return {name: item["Id"] for name, item in services.items()}


def validate_seed(seed):
    if (
        set(seed) != {"legacy_request_id", "binding", "protected_tables"}
        or not isinstance(seed["legacy_request_id"], int)
        or isinstance(seed["legacy_request_id"], bool)
        or seed["legacy_request_id"] <= 0
        or seed["binding"] != [2, 2, "unit"]
        or set(seed["protected_tables"]) != {"stocks", "outbounds", "transactions"}
    ):
        raise CIError("SEED_INVALID")
    for value in seed["protected_tables"].values():
        if (
            not isinstance(value, dict)
            or set(value) != {"count", "sha256"}
            or type(value["count"]) is not int
            or value["count"] < 0
            or not isinstance(value["sha256"], str)
            or re.fullmatch(r"[0-9a-f]{64}", value["sha256"]) is None
        ):
            raise CIError("SEED_INVALID")


def browser_ready():
    for _ in range(30):
        try:
            with urlopen("http://127.0.0.1:58082/api/v1/health/ready", timeout=3) as response:
                if response.status == 200:
                    return
        except OSError:
            pass
        time.sleep(1)
    raise CIError("BROWSER_NOT_READY")


def browser_verify_api_read(identities, env, sensitive):
    run_id = env.get("E2E_REPLENISHMENT_RUN_ID", "")
    if re.fullmatch(r"rrv1-[0-9a-f]{64}", run_id) is None:
        raise CIError("FIXTURE_INVALID")
    script = "\n".join(
        (
            "import json,os,pathlib,sys",
            "if (os.geteuid(), os.getegid()) != (10001, 10001): raise SystemExit(2)",
            "p=pathlib.Path('/replenishment-catalog/operational')/sys.argv[1]/'public-manifest.json'",
            "with p.open('rb') as f:",
            "    if not f.read(1): raise SystemExit(2)",
            "print(json.dumps({'status':'readable'}))",
        )
    )
    output = browser_command(
        ["docker", "exec", identities["api"], "python", "-c", script, run_id],
        env,
        sensitive,
    )
    if json.loads(output) != {"status": "readable"}:
        raise CIError("FIXTURE_INVALID")


def run_browser():
    from tests import prepare_replenishment_e2e as fixture_module

    check_context()
    if os.environ.get("CI") != "true" or os.environ.get("QUALITY_CI_PROFILE") != "synthetic-only":
        raise CIError("ENVIRONMENT_INVALID")
    fixture_module.validate_profile("synthetic-only", None)
    fixture_module.checked_workspace("synthetic-only")
    if (guarded.ROOT / "artifacts").exists():
        raise CIError("OUTPUT_CONFLICT")
    env, sensitive = browser_environment({"fixture_run_id": ""})
    catalogs = fixture_module.OUTPUT / "catalogs"
    forecast = fixture_module.LEGACY_FORECAST
    env["CI_POLICY_CATALOG"] = str(catalogs / "valid")
    env["CI_FORECAST_CATALOG"] = str(forecast / "valid")
    env["E2E_REPLENISHMENT_SCENARIO"] = env["E2E_FORECAST_SCENARIO"] = "valid"
    browser_context(env, sensitive)
    browser_absent(env, sensitive)
    with tempfile.TemporaryDirectory() as directory:
        envfile = Path(directory) / "empty.env"
        envfile.touch(exist_ok=False)
        base = browser_compose(envfile)
        browser_compose_guard(base, env, sensitive)
        browser_command([*base, "build"], env, sensitive)
        fixture = fixture_module.prepare(None, profile="synthetic-only")
        if fixture != fixture_module.verify_existing(profile="synthetic-only"):
            raise CIError("FIXTURE_INVALID")
        env["E2E_REPLENISHMENT_RUN_ID"] = fixture["fixture_run_id"]
        browser_absent(env, sensitive)
        browser_compose_guard(base, env, sensitive)
        browser_command([*base, "up", "-d", "--no-build", "--wait"], env, sensitive)
        identities = browser_guard(env, sensitive)
        browser_ready()
        browser_verify_api_read(identities, env, sensitive)
        source = (guarded.ROOT / "tests/prepare_replenishment_e2e.py").read_text(encoding="utf8")
        seed_output = browser_command(
            [
                "docker",
                "exec",
                "-i",
                "-e",
                "M7_E2E_SEED_RELEASE=1",
                identities["api"],
                "python",
                "-",
                "--seed-db",
            ],
            env,
            sensitive,
            input_text=source,
        )
        seed = json.loads(seed_output)
        validate_seed(seed)
        env["E2E_M4_LEGACY_REQUEST_ID"] = str(seed["legacy_request_id"])
        for policy, forecasting, suite in browser_plan():
            if fixture != fixture_module.verify_existing(profile="synthetic-only"):
                raise CIError("FIXTURE_INVALID")
            before = browser_guard(env, sensitive)
            if (policy, forecasting) != (
                env["E2E_REPLENISHMENT_SCENARIO"],
                env["E2E_FORECAST_SCENARIO"],
            ):
                env["CI_POLICY_CATALOG"] = str(catalogs / policy)
                env["CI_FORECAST_CATALOG"] = str(forecast / forecasting)
                env["E2E_REPLENISHMENT_SCENARIO"] = policy
                env["E2E_FORECAST_SCENARIO"] = forecasting
                browser_compose_guard(base, env, sensitive)
                browser_command(
                    [*base, "up", "-d", "--no-deps", "--force-recreate", "--wait", "api"],
                    env,
                    sensitive,
                )
                browser_command(["docker", "restart", before["web"]], env, sensitive)
                after = browser_guard(env, sensitive)
                if (
                    any(
                        after[name] != before[name]
                        for name in ("db", "migrate", "bootstrap", "web")
                    )
                    or after["api"] == before["api"]
                ):
                    raise CIError("RESOURCE_INVALID")
                browser_ready()
            args = ["npm", "exec", "--", "playwright", "test"]
            if suite != "all":
                args.append("e2e/" + suite + ".spec.ts")
            args.extend(["--reporter=list", "--retries=0"])
            output = browser_command(
                args, env, sensitive, cwd=guarded.ROOT / "client", timeout=2400
            )
            counts = browser_coverage(output, policy, forecasting, suite)
            print(output)
            print(json.dumps({"policy": policy, "forecast": forecasting, "suite": suite, **counts}))
            browser_guard(env, sensitive)
        fixture_module.verify_existing(profile="synthetic-only")


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in ("backend", "windows", "e2e"):
        raise CIError("ARGUMENT_INVALID")
    {"backend": run_backend, "windows": run_windows, "e2e": run_browser}[sys.argv[1]]()


if __name__ == "__main__":
    try:
        main()
    except (CIError, guarded.GuardError, subprocess.CalledProcessError):
        print("Quality CI guard or child failed", file=sys.stderr)
        sys.exit(1)
