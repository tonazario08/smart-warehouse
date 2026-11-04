"""Guarded backend and research verification for the M7 worktree."""

import argparse
import hashlib
import json
import ntpath
import os
import re
import secrets
import shutil
import socket
import subprocess
import sys
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_ROOT = Path("C:/Users/TQUOCTOAN/.codex/worktrees/m7-replenishment-policy/smart-warehouse")
NAME = "sw-m7-replenishment-test"
VOLUME = NAME + "-data"
NETWORK = NAME + "-net"
IMAGE = "sha256:cf78e76683b9ca8c5733cbbdce6c9262b45b6767934dd0a95e671f9a0fc20685"
USER = "sw_m7_replenishment_test"
DATABASES = ("sw_m7_replenishment_test", "sw_m7_replenishment_migration_test")
LABELS = {"task": "implement-replenishment-policy", "role": "backend-test"}


class GuardError(Exception):
    pass


def check_environment():
    import app

    if (
        os.environ.get("ANALYTICS_DATABASE_URL") is not None
        or (ROOT / ".env").exists()
        or any(
            key in os.environ
            for key in ("DOCKER_HOST", "DOCKER_CONTEXT", "DOCKER_TLS_VERIFY", "DOCKER_CERT_PATH")
        )
    ):
        raise GuardError("ENVIRONMENT_INVALID")
    if not Path(app.__file__).resolve().is_relative_to(ROOT / "app"):
        raise GuardError("APP_ROOT_INVALID")
    if Path.cwd().resolve() != ROOT or ROOT != EXPECTED_ROOT.resolve():
        raise GuardError("WORKTREE_INVALID")


def validate_backend_inspection(container, volume, network, *, running):
    try:
        mounts = container["Mounts"]
        attached = network["Containers"] or {}
        checks = (
            container["Name"] == "/" + NAME,
            container["State"]["Running"] is running,
            container["Image"] == IMAGE,
            container["Config"]["Labels"] == LABELS,
            volume["Labels"] == LABELS and volume["Name"] == VOLUME,
            network["Labels"] == LABELS and network["Name"] == NETWORK,
            container["HostConfig"]["PortBindings"]
            == {"5432/tcp": [{"HostIp": "127.0.0.1", "HostPort": "18547"}]},
            len(mounts) == 1,
            len(mounts) == 1 and mounts[0]["Type"] == "volume",
            len(mounts) == 1 and mounts[0]["Name"] == VOLUME,
            len(mounts) == 1 and mounts[0]["Destination"] == "/var/lib/postgresql/data",
            len(mounts) == 1 and mounts[0]["RW"] is True,
            list(container["NetworkSettings"]["Networks"]) == [NETWORK],
            container["NetworkSettings"]["Networks"][NETWORK]["NetworkID"] == network["Id"],
            container["State"]["Status"] == ("running" if running else "exited"),
            container["HostConfig"]["NetworkMode"] == NETWORK,
            (
                len(attached) == 1
                and container["Id"] in attached
                and attached[container["Id"]]["Name"] == NAME
            )
            if running
            else not attached,
        )
        if not all(checks):
            raise GuardError("RESOURCE_INVALID")
    except (KeyError, TypeError, StopIteration):
        raise GuardError("RESOURCE_INVALID") from None


def validate_database_identity(database, row, competing):
    if database not in DATABASES or row != (database, USER, USER) or competing != 0:
        raise GuardError("DATABASE_INVALID")


def docker_command(*args, env=None):
    try:
        result = subprocess.run(
            ["docker", *args], env=env, capture_output=True, text=True, timeout=30, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        raise GuardError("DOCKER_UNAVAILABLE") from None
    if result.returncode:
        raise GuardError("DOCKER_FAILURE")
    return result.stdout


def docker_mutate(*args, env=None):
    check_docker_context()
    docker_command(*args, env=env)


def check_docker_context():
    try:
        active = docker_command("context", "show").strip()
        context = json.loads(docker_command("context", "inspect", active))
        endpoint = context[0]["Endpoints"]["docker"]["Host"]
        if active != "desktop-linux" or endpoint != "npipe:////./pipe/dockerDesktopLinuxEngine":
            raise GuardError("DOCKER_CONTEXT_INVALID")
    except (ValueError, IndexError, TypeError, KeyError):
        raise GuardError("DOCKER_CONTEXT_INVALID") from None


def resource_presence():
    containers = docker_command("ps", "-a", "--format", "{{.Names}}").splitlines()
    volumes = docker_command("volume", "ls", "--format", "{{.Name}}").splitlines()
    networks = docker_command("network", "ls", "--format", "{{.Name}}").splitlines()
    return NAME in containers, VOLUME in volumes, NETWORK in networks


def check_resource_state():
    presence = resource_presence()
    if presence == (False, False, False):
        return "ABSENT"
    if presence != (True, True, True):
        raise GuardError("RESOURCE_COLLISION")
    container, volume, network = docker_inspect()
    running = container.get("State", {}).get("Running")
    if type(running) is not bool:
        raise GuardError("RESOURCE_INVALID")
    validate_backend_inspection(container, volume, network, running=running)
    credentials(container)
    if running:
        check_backend()
        return "RUNNING"
    return "STOPPED"


def docker_inspect():
    try:
        container = json.loads(docker_command("inspect", NAME))[0]
        volume = json.loads(docker_command("volume", "inspect", VOLUME))[0]
        network = json.loads(docker_command("network", "inspect", NETWORK))[0]
        return container, volume, network
    except (ValueError, IndexError, TypeError):
        raise GuardError("RESOURCE_INVALID") from None


def credentials(container):
    try:
        env = dict(item.split("=", 1) for item in container["Config"]["Env"] if "=" in item)
        if env["POSTGRES_USER"] != USER or not env["POSTGRES_PASSWORD"]:
            raise ValueError
        return env["POSTGRES_PASSWORD"]
    except (KeyError, TypeError, ValueError):
        raise GuardError("RESOURCE_INVALID") from None


def check_databases(password):
    import psycopg

    try:
        for database in DATABASES:
            with psycopg.connect(
                host="127.0.0.1",
                port=18547,
                user=USER,
                password=password,
                dbname=database,
                connect_timeout=5,
            ) as conn:
                row = conn.execute(
                    "select current_database(), current_user, pg_get_userbyid(datdba) "
                    "from pg_database where datname=current_database()"
                ).fetchone()
                sessions = conn.execute(
                    "select count(*) from pg_stat_activity where pid <> pg_backend_pid() "
                    "and backend_type='client backend'"
                ).fetchone()[0]
                validate_database_identity(database, row, sessions)
    except psycopg.Error:
        raise GuardError("DATABASE_UNAVAILABLE") from None


def check_backend():
    container, volume, network = docker_inspect()
    validate_backend_inspection(container, volume, network, running=True)
    password = credentials(container)
    check_databases(password)
    return password


def port_is_free():
    try:
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 18547))
    except OSError:
        raise GuardError("PORT_OCCUPIED") from None


def validate_creation_stage(expected):
    if resource_presence() != expected:
        raise GuardError("RESOURCE_COLLISION")
    try:
        if expected[2]:
            network = json.loads(docker_command("network", "inspect", NETWORK))[0]
            if network["Name"] != NETWORK or network["Labels"] != LABELS or network["Containers"]:
                raise GuardError("RESOURCE_INVALID")
        if expected[1]:
            volume = json.loads(docker_command("volume", "inspect", VOLUME))[0]
            if volume["Name"] != VOLUME or volume["Labels"] != LABELS:
                raise GuardError("RESOURCE_INVALID")
    except (ValueError, IndexError, TypeError, KeyError):
        raise GuardError("RESOURCE_INVALID") from None


def start_backend():
    presence = resource_presence()
    if presence == (True, True, True):
        container, volume, network = docker_inspect()
        if container["State"]["Running"]:
            check_backend()
            return
        validate_backend_inspection(container, volume, network, running=False)
        credentials(container)
        port_is_free()
        docker_mutate("start", NAME)
    elif presence == (False, False, False):
        port_is_free()
        image = docker_command("image", "inspect", IMAGE, "--format", "{{.Id}}").strip()
        if image != IMAGE:
            raise GuardError("IMAGE_INVALID")
        password = secrets.token_urlsafe(32)
        env = os.environ.copy()
        env["POSTGRES_PASSWORD"] = password
        validate_creation_stage((False, False, False))
        docker_mutate(
            "network",
            "create",
            "--label",
            "task=implement-replenishment-policy",
            "--label",
            "role=backend-test",
            NETWORK,
        )
        validate_creation_stage((False, False, True))
        docker_mutate(
            "volume",
            "create",
            "--label",
            "task=implement-replenishment-policy",
            "--label",
            "role=backend-test",
            VOLUME,
        )
        validate_creation_stage((False, True, True))
        port_is_free()
        docker_mutate(
            "run",
            "--pull=never",
            "-d",
            "--name",
            NAME,
            "--label",
            "task=implement-replenishment-policy",
            "--label",
            "role=backend-test",
            "--network",
            NETWORK,
            "-p",
            "127.0.0.1:18547:5432",
            "-v",
            f"{VOLUME}:/var/lib/postgresql/data",
            "-e",
            f"POSTGRES_USER={USER}",
            "-e",
            "POSTGRES_PASSWORD",
            "-e",
            f"POSTGRES_DB={USER}",
            IMAGE,
            env=env,
        )
        # No DB creation until the exact running container has passed the ownership guard.
        container, volume, network = docker_inspect()
        validate_backend_inspection(container, volume, network, running=True)
        initialize_new_databases(password)
    else:
        raise GuardError("RESOURCE_COLLISION")
    # Starting a stopped server may finish before PostgreSQL is accepting connections.
    deadline = time.monotonic() + 45
    while True:
        try:
            check_backend()
            break
        except GuardError as exc:
            if str(exc) != "DATABASE_UNAVAILABLE" or time.monotonic() >= deadline:
                raise
            time.sleep(1)


def initialize_new_databases(password):
    import psycopg
    from psycopg import sql

    deadline = time.monotonic() + 45
    while True:
        try:
            conn = psycopg.connect(
                host="127.0.0.1",
                port=18547,
                user=USER,
                password=password,
                dbname=DATABASES[0],
                connect_timeout=3,
                autocommit=True,
            )
            break
        except psycopg.OperationalError:
            if time.monotonic() >= deadline:
                raise GuardError("DATABASE_UNAVAILABLE") from None
            time.sleep(1)
    try:
        with conn:
            row = conn.execute(
                "select current_database(), current_user, pg_get_userbyid(datdba) "
                "from pg_database where datname=current_database()"
            ).fetchone()
            count = conn.execute(
                "select count(*) from pg_stat_activity where pid <> pg_backend_pid() "
                "and backend_type='client backend'"
            ).fetchone()[0]
            validate_database_identity(DATABASES[0], row, count)
            existing = conn.execute(
                "select 1 from pg_database where datname=%s", (DATABASES[1],)
            ).fetchone()
            if existing:
                raise GuardError("RESOURCE_COLLISION")
            check_docker_context()
            container, volume, network = docker_inspect()
            validate_backend_inspection(container, volume, network, running=True)
            if credentials(container) != password:
                raise GuardError("RESOURCE_INVALID")
            conn.execute(
                sql.SQL("CREATE DATABASE {} OWNER {}").format(
                    sql.Identifier(DATABASES[1]), sql.Identifier(USER)
                )
            )
    except psycopg.Error:
        raise GuardError("DATABASE_UNAVAILABLE") from None


def check_disk():
    if shutil.disk_usage(ROOT).free < 5 * 1024**3:
        raise GuardError("DISK_INSUFFICIENT")


def verify_pinned_files(root, expected):
    actual = {}
    try:
        for name, digest in expected.items():
            path = root / name
            if path.is_symlink() or not path.is_file():
                raise GuardError("SOURCE_CHANGED")
            actual[name] = hashlib.sha256(path.read_bytes()).hexdigest()
            if actual[name] != digest:
                raise GuardError("SOURCE_CHANGED")
    except OSError:
        raise GuardError("SOURCE_CHANGED") from None
    return actual


def guard_destructive_sql(connection, statement, marker):
    if connection.dialect.name != "postgresql":
        return
    if not re.search(r"(?:^|;)\s*(?:TRUNCATE|DROP|ALTER)\b", statement, re.IGNORECASE):
        return
    if not marker:
        raise GuardError("DATABASE_INVALID")
    cursor = connection.connection.driver_connection.cursor()
    try:
        cursor.execute("select pg_stat_clear_snapshot()")
        cursor.execute(
            "select current_database(), current_user, pg_get_userbyid(datdba), "
            "(select count(*) from pg_stat_activity where datname = any(%s) "
            "and pid <> pg_backend_pid() and backend_type = 'client backend' "
            "and application_name <> %s) "
            "from pg_database where datname=current_database()",
            (list(DATABASES), marker),
        )
        database, user, owner, competing = cursor.fetchone()
        validate_database_identity(database, (database, user, owner), competing)
        cursor.execute(
            "select datname, pg_get_userbyid(datdba) from pg_database "
            "where datname = any(%s) order by datname",
            (list(DATABASES),),
        )
        if cursor.fetchall() != sorted((name, USER) for name in DATABASES):
            raise GuardError("DATABASE_INVALID")
        cursor.execute("select current_setting('application_name')")
        if cursor.fetchone()[0] != marker:
            raise GuardError("DATABASE_INVALID")
    finally:
        cursor.close()


def backend_child_environment(password):
    allowed = (
        "SYSTEMROOT",
        "WINDIR",
        "SYSTEMDRIVE",
        "COMSPEC",
        "PATH",
        "PATHEXT",
        "TEMP",
        "TMP",
        "USERNAME",
        "USERPROFILE",
        "APPDATA",
        "LOCALAPPDATA",
        "PROGRAMDATA",
        "PROGRAMFILES",
    )
    env = {key: os.environ[key] for key in allowed if key in os.environ}
    marker = "m7-" + secrets.token_hex(16)
    env["M7_PG_MARKER"] = marker
    env["PGAPPNAME"] = marker
    env["PYTHONPATH"] = str(ROOT)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTEST_PLUGINS"] = "tests.run_replenishment_verification"
    for key in (
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS",
        "NUMEXPR_NUM_THREADS",
    ):
        env[key] = "1"
    for key, database in zip(
        ("TEST_DATABASE_URL", "TEST_MIGRATION_DATABASE_URL"), DATABASES, strict=True
    ):
        env[key] = (
            f"postgresql+psycopg://{quote(USER, safe='')}:"
            f"{quote(password, safe='')}@127.0.0.1:18547/{database}"
        )
    return env


def install_sql_guard():
    from sqlalchemy import event
    from sqlalchemy.engine import Engine

    marker = os.environ.get("M7_PG_MARKER", "")
    if not re.fullmatch(r"m7-[0-9a-f]{32}", marker) or os.environ.get("PGAPPNAME") != marker:
        raise GuardError("MARKER_INVALID")

    def before_cursor_execute(connection, cursor, statement, parameters, context, executemany):
        guard_destructive_sql(connection, statement, marker)

    event.listen(Engine, "before_cursor_execute", before_cursor_execute)


def pytest_configure(config):
    install_sql_guard()


def redact(output, sensitive):
    for value in sorted((x for x in sensitive if x), key=len, reverse=True):
        output = output.replace(value, "[REDACTED]")
    output = re.sub(r"(?i)bearer\s+[^\s]+", "Bearer [REDACTED]", output)
    return re.sub(r"\beyJ[A-Za-z0-9_-]*\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b", "[REDACTED]", output)


def verification_directory():
    from app.replenishment.inputs import _checked

    current = ROOT
    for component in ("artifacts", "replenishment", "verification"):
        current = current / component
        if not current.exists():
            _checked(current.parent)
            current.mkdir(exist_ok=False)
        if not _checked(current).is_dir():
            raise GuardError("OUTPUT_INVALID")
    return current


@contextmanager
def execution_lock():
    import msvcrt

    path = verification_directory() / "backend.lock"
    if path.exists() or path.is_symlink():
        info = path.lstat()
        if path.is_symlink() or getattr(info, "st_file_attributes", 0) & 0x400:
            raise GuardError("OUTPUT_INVALID")
    try:
        lock = path.open("a+b")
        if lock.seek(0, 2) == 0:
            lock.write(b"0")
            lock.flush()
        lock.seek(0)
        msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        if "lock" in locals():
            lock.close()
        raise GuardError("RUNNER_BUSY") from None
    try:
        yield
    finally:
        lock.seek(0)
        msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
        lock.close()


def run_child(command, env, label, sensitive, *, timeout=1200):
    root = verification_directory()
    path = root / (label + "-" + uuid.uuid4().hex + ".log")
    started = time.monotonic()
    try:
        with path.open("x", encoding="utf-8", newline="\n") as log:
            process = subprocess.Popen(
                command,
                cwd=ROOT,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                errors="replace",
            )
            try:
                output, _ = process.communicate(timeout=timeout)
                result = process.returncode
            except subprocess.TimeoutExpired as expired:
                killed = False
                try:
                    if os.name == "nt":
                        termination = subprocess.run(
                            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            timeout=15,
                            check=False,
                        )
                        killed = termination.returncode == 0
                    else:
                        process.kill()
                        killed = True
                    output, _ = process.communicate(timeout=15)
                except (OSError, subprocess.TimeoutExpired):
                    output = expired.output or ""
                    if isinstance(output, bytes):
                        output = output.decode("utf-8", errors="replace")
                    killed = False
                result = 124 if killed else 125
            safe = redact(output, sensitive)
            log.write(safe)
            log.write(f"\nexit={result}; elapsed={time.monotonic() - started:.2f}s\n")
    except OSError:
        raise GuardError("PROCESS_UNAVAILABLE") from None
    print(json.dumps({"step": label, "exit": result, "log": str(path)}), flush=True)
    if result:
        raise GuardError("CHILD_FAILED")


def run_backend():
    password = check_backend()
    env = backend_child_environment(password)
    sensitive = [
        password,
        quote(password, safe=""),
        env["TEST_DATABASE_URL"],
        env["TEST_MIGRATION_DATABASE_URL"],
        env["M7_PG_MARKER"],
    ]
    migration = (
        "import os; from tests.run_replenishment_verification import install_sql_guard; "
        "from alembic.config import Config; from alembic import command; "
        'install_sql_guard(); c=Config("alembic.ini"); '
        'c.set_main_option("sqlalchemy.url",os.environ["TEST_DATABASE_URL"].replace("%","%%")); '
        'command.upgrade(c,"head")'
    )
    run_child([sys.executable, "-c", migration], env, "backend-migrate", sensitive)
    check_backend()
    run_child([sys.executable, "-m", "pytest", "-q"], env, "backend-pytest", sensitive)
    check_backend()


M6_ROOT = ROOT.parent.parent / "m6-demand-forecasting" / "smart-warehouse"
M5_ROOT = ROOT.parent.parent / "m5-demand-data" / "smart-warehouse"
DATA_VERSION = "ddv2-62da0915fdcde6d212f7a5a5c903123a20baed119560be0be17d902eec84b3e7"
FORECAST_ID = "frv1-398a6c1c260e5277a15b647d3f383ef2bc5458978386dd05ccf88eee527c7b82"
SOURCE_HASH = "8898733f8924dc5ff947f3d3225b832021a61bf01dc84bca6a5bd271d95d63e1"
PUBLIC_HASH = "1e31a3ff9fa86a41e6ff96e51c29e70b6b472215f3b4d46284d02390251124f7"
BUNDLE_HASHES = {
    "manifest.json": "17b7dd594458912c8e1d02e0535646faa56ed0523bcc595948fa07d3a6b615d1",
    "observations.jsonl": "6a56332fd7e21719122c7978e4bcae0453f39dae6d08d66c3627e19ad6b3b386",
    "quality.json": "b2f5c76ec497b86f55daa7f68fd7e5ea748185bd7164e95e8ccb049a4ee59c0e",
    "records.jsonl": "05c04fb8140d394d5bd756bd21f3e2c6073656ac8c4ca492742a06ea22969c8c",
}
PRIVATE_HASHES = {
    "manifest.json": SOURCE_HASH,
    "metrics.json": "b921e7bf1b96e2b8da3fa479fea6cbc36f74a5c0d58a65b77eae3db34fb30b7d",
    "predictions.jsonl": "0ba4a45df5446104b1c5f4a918b3189e1a44b4450ff490e3b9a528216a1ad564",
    "receipt.json": "ddf4bb51eef66b8fdc6e03f9cb0a36cb88e7f0f6c4f913bd32bfaf79993973c2",
    "models/h1-l1.json": "56ad84df61c2a9b0fdbbd5799a2a050e60634b417a57dda6d774ceb73ead2d3c",
    "models/h7-l1.json": "ce54fe63b6927bef23d369d3fa05e13802736a88a4cbfb1ab404f6571f990e8e",
    "models/h7-l2.json": "537fa28fe4df065d35e771f0f149b3051832ace8df83a7131dd0b39109fdf015",
    "models/h7-l3.json": "9aa03c27df62b7c6ff079b123b37071990b5739bac38ca33231d780809d8dc33",
    "models/h7-l4.json": "c92db28f7d19a342151495145bb880e347abe3a8df5108635776744cf2d6e37a",
    "models/h7-l5.json": "a8fe19b8f8d499d715bf60e1f924ad89ec9ba2431ebf2bfe60db100257048ef6",
    "models/h7-l6.json": "9e394d1f4530134758032474f64e1c211143548bf70874d51c06d1e08704d316",
    "models/h7-l7.json": "c134e642ad2ed9cb41adbcf336a1b055b1d88dfc406a40c029fce5ffaef143d7",
}
PUBLIC_HASHES = {
    "public-manifest.json": PUBLIC_HASH,
    "metrics.json": PRIVATE_HASHES["metrics.json"],
    "predictions.jsonl": PRIVATE_HASHES["predictions.jsonl"],
}
SCIENTIFIC_FILES = (
    "manifest.json",
    "calibration.json",
    "summaries.json",
    "days.jsonl",
    "orders.jsonl",
)


def research_authorization():
    from app.replenishment.schemas import InputAuthorization

    bundle_root = M5_ROOT / "artifacts/demand-data/bundles/reported-sales-v1"
    forecast_root = M6_ROOT / "artifacts/forecasting/catalog/research"
    return InputAuthorization(
        schema_version="replenishment-input-authorization/1",
        mode="research",
        dataset_class="research",
        approved_bundle_root=bundle_root,
        bundle_path=bundle_root / DATA_VERSION,
        bundle_hashes=BUNDLE_HASHES,
        approved_forecast_root=forecast_root,
        forecast_dir=forecast_root / FORECAST_ID,
        public_manifest_sha256=PUBLIC_HASH,
        source_manifest_sha256=SOURCE_HASH,
        forecast_run_id=FORECAST_ID,
        allow_fixture=False,
        expected_fixture_binding=None,
    )


def research_config():
    from datetime import date
    from decimal import Decimal

    from app.replenishment.schemas import CostInputs, StudyConfig

    return StudyConfig(
        schema_version="replenishment-study/1",
        mode="research",
        dataset_class="research",
        target="reported_daily_unit_sales",
        reporting_scope="company_aggregate",
        unit="unit",
        data_version=DATA_VERSION,
        forecast_run_id=FORECAST_ID,
        source_manifest_sha256=SOURCE_HASH,
        public_manifest_sha256=PUBLIC_HASH,
        calibration_start=date(2022, 1, 1),
        calibration_end=date(2022, 7, 1),
        evaluation_start=date(2022, 7, 1),
        evaluation_end=date(2023, 1, 1),
        nominal_coverage=Decimal(".90"),
        service_probabilities=(Decimal(".80"), Decimal(".90"), Decimal(".95")),
        minimum_samples=30,
        lead_times=(1, 7),
        warmup_days=7,
        costs=CostInputs(
            ordering_cost=Decimal("100000"),
            holding_cost=Decimal("20000"),
            currency="VND",
            holding_period="year",
        ),
        initial_on_hand=10000,
        initial_pipeline=(),
        reservations=0,
        backlog=0,
        temporal_availability_convention="retrospective_final_vintage",
        disclosures=(
            "Final-vintage reported sales are a company-level proxy, not warehouse demand.",
            "The 2022 source and M6 metrics were previously inspected; "
            "this is not a blind holdout.",
            "Historical publication and operational availability are unproven.",
            "Inventory, pipeline, lead times and VND costs are hypothetical scenario assumptions.",
            "Overlapping windows and dependence preclude an iid or guaranteed service claim.",
        ),
    )


def freeze_bytes(path, expected):
    from app.replenishment.artifacts import _owned

    path = _owned(path, must_exist=False)
    try:
        if path.exists():
            if path.is_symlink() or path.read_bytes() != expected:
                raise GuardError("CONFIG_CONFLICT")
        else:
            with path.open("xb") as stream:
                stream.write(expected)
                stream.flush()
                os.fsync(stream.fileno())
    except OSError:
        raise GuardError("CONFIG_UNAVAILABLE") from None


def compare_scientific(first, second):
    from app.replenishment.artifacts import _owned, _read

    first, second = _owned(first), _owned(second)
    try:
        for name in SCIENTIFIC_FILES:
            if _read(first / name) != _read(second / name):
                raise GuardError("REPEAT_MISMATCH")
    except OSError:
        raise GuardError("REPEAT_MISMATCH") from None


def verify_bounded_hashes(root, expected, *, limit=64 * 1024 * 1024):
    from app.replenishment.inputs import _checked

    try:
        for name, digest in expected.items():
            path = _checked(root / name)
            total, checksum = 0, hashlib.sha256()
            with path.open("rb") as stream:
                while chunk := stream.read(1024 * 1024):
                    total += len(chunk)
                    if total > limit:
                        raise GuardError("SOURCE_CHANGED")
                    checksum.update(chunk)
            if checksum.hexdigest() != digest:
                raise GuardError("SOURCE_CHANGED")
    except OSError:
        raise GuardError("SOURCE_CHANGED") from None


def verify_research_sources():
    from app.forecasting.repository import verify_catalog_run
    from app.replenishment.inputs import _checked

    auth = research_authorization()
    private = M6_ROOT / "artifacts/forecasting/runs" / FORECAST_ID
    try:
        for root, hashes in (
            (auth.bundle_path, BUNDLE_HASHES),
            (private, PRIVATE_HASHES),
            (auth.forecast_dir, PUBLIC_HASHES),
        ):
            _checked(root)
            actual_names = {
                item.relative_to(root).as_posix() for item in root.rglob("*") if item.is_file()
            }
            if actual_names != set(hashes):
                raise GuardError("SOURCE_CHANGED")
            for name in hashes:
                _checked(root / name)
            verify_bounded_hashes(root, hashes)
        public = verify_catalog_run(auth.forecast_dir)
        if (
            public.manifest.run_id != FORECAST_ID
            or public.manifest.data_version != DATA_VERSION
            or public.manifest.source_manifest_sha256 != SOURCE_HASH
            or public.manifest.dataset_class != "research"
            or public.manifest.mode != "research"
            or public.manifest.artifacts
            != {
                "metrics.json": PRIVATE_HASHES["metrics.json"],
                "predictions.jsonl": PRIVATE_HASHES["predictions.jsonl"],
            }
        ):
            raise GuardError("SOURCE_CHANGED")
    except GuardError:
        raise
    except Exception:
        raise GuardError("SOURCE_CHANGED") from None
    return private


def source_code_snapshot():
    from app.replenishment.inputs import _checked

    result = {}
    try:
        for module in ("analytics", "forecasting", "replenishment"):
            for path in sorted((ROOT / "app" / module).glob("*.py")):
                result[path.relative_to(ROOT).as_posix()] = hashlib.sha256(
                    _checked(path).read_bytes()
                ).hexdigest()
        for path in (
            ROOT / "tests/run_replenishment_verification.py",
            ROOT / "tests/reconcile_replenishment_run.py",
        ):
            result[path.relative_to(ROOT).as_posix()] = hashlib.sha256(
                _checked(path).read_bytes()
            ).hexdigest()
    except (OSError, ValueError):
        raise GuardError("SOURCE_CHANGED") from None
    return result


def research_environment(cwd):
    allowed = (
        "SYSTEMROOT",
        "WINDIR",
        "SYSTEMDRIVE",
        "COMSPEC",
        "PATH",
        "PATHEXT",
        "TEMP",
        "TMP",
        "USERNAME",
        "USERPROFILE",
        "APPDATA",
        "LOCALAPPDATA",
        "PROGRAMDATA",
        "PROGRAMFILES",
    )
    env = {key: os.environ[key] for key in allowed if key in os.environ}
    env["PYTHONPATH"] = str(cwd)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    for key in (
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS",
        "NUMEXPR_NUM_THREADS",
    ):
        env[key] = "1"
    return env


def research_child(command, cwd, label):
    root = verification_directory()
    path = root / (label + "-" + uuid.uuid4().hex + ".log")
    started = time.monotonic()
    env = research_environment(cwd)
    try:
        with path.open("x", encoding="utf8", newline="\n") as log:
            proc = subprocess.Popen(
                command,
                cwd=cwd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                errors="replace",
            )
            try:
                output, error = proc.communicate(timeout=600)
                code = proc.returncode
            except subprocess.TimeoutExpired as exc:
                try:
                    termination = subprocess.run(
                        ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=15,
                        check=False,
                    )
                    output, error = proc.communicate(timeout=15)
                    code = 124 if termination.returncode == 0 else 125
                except (OSError, subprocess.TimeoutExpired):
                    output, error = exc.output or "", exc.stderr or ""
                    if isinstance(output, bytes):
                        output = output.decode("utf8", errors="replace")
                    if isinstance(error, bytes):
                        error = error.decode("utf8", errors="replace")
                    code = 125
            log.write(redact(json.dumps({"command": command, "cwd": str(cwd)}), []) + "\n")
            log.write(redact(output, []))
            log.write(redact(error, []))
            log.write(f"\nexit={code}; elapsed={time.monotonic() - started:.2f}s\n")
    except OSError:
        raise GuardError("PROCESS_UNAVAILABLE") from None
    print(json.dumps({"step": label, "exit": code, "log": str(path)}), flush=True)
    if code:
        raise GuardError("CHILD_FAILED")
    try:
        return json.loads(output)
    except (ValueError, TypeError):
        raise GuardError("CHILD_OUTPUT_INVALID") from None


def check_study_eligibility(calibration_windows, evaluation_windows):
    from datetime import date, timedelta

    algorithms = ("persistence", "seasonal_naive", "xgboost")
    pairs = {(algorithm, horizon) for algorithm in algorithms for horizon in (1, 7)}

    def group(windows):
        result = {pair: set() for pair in pairs}
        for window in windows:
            row = window[0]
            pair = (row.algorithm, row.horizon)
            if pair not in result or row.origin in result[pair]:
                raise GuardError("ELIGIBILITY_CHANGED")
            result[pair].add(row.origin)
        return result

    calibration, evaluation = group(calibration_windows), group(evaluation_windows)
    for horizon, expected in ((1, 94), (7, 76)):
        samples = [calibration[(algorithm, horizon)] for algorithm in algorithms]
        if any(len(sample) != expected for sample in samples) or any(
            sample != samples[0] for sample in samples[1:]
        ):
            raise GuardError("ELIGIBILITY_CHANGED")
    expected_origins = {date(2022, 6, 30) + timedelta(days=i) for i in range(178)}
    if set.intersection(*(evaluation[pair] for pair in pairs)) != expected_origins:
        raise GuardError("ELIGIBILITY_CHANGED")


def _run_research():
    from app.analytics.export import canonical_json
    from app.replenishment.artifacts import _owned, verify_public_projection
    from app.replenishment.inputs import _checked

    if (M6_ROOT / ".env").exists():
        raise GuardError("ENVIRONMENT_INVALID")
    private = verify_research_sources()
    # Force the original owning checkout and verify its import before invoking M6's CLI.
    verify_script = (
        "import pathlib,sys,app; p=pathlib.Path(app.__file__).resolve(); "
        "root=pathlib.Path.cwd().resolve(); "
        'sys.exit(2) if not p.is_relative_to(root / "app") else None; '
        "from app.forecasting.cli import main; "
        'sys.exit(main(["verify", "--run-dir", sys.argv[1]]))'
    )
    verified = research_child(
        [sys.executable, "-c", verify_script, str(private)], M6_ROOT, "m6-private-verify"
    )
    if verified.get("run_id") != FORECAST_ID or verified.get("status") != "verified":
        raise GuardError("SOURCE_CHANGED")

    auth, config = research_authorization(), research_config()
    root = _owned(ROOT / "artifacts/replenishment/research", must_exist=False)
    if root.exists():
        _checked(root)
        _owned(root / "config.json", must_exist=False)
        _owned(root / "authorization.json", must_exist=False)
        if not (root / "config.json").is_file() or not (root / "authorization.json").is_file():
            raise GuardError("CONFIG_CONFLICT")
    else:
        _checked(root.parent)
        root.mkdir(exist_ok=False)
    config_path, auth_path = root / "config.json", root / "authorization.json"
    config_bytes = canonical_json(config.model_dump(mode="json"))
    auth_bytes = canonical_json(auth.model_dump(mode="json"))
    if config_path.exists() and config_path.read_bytes() != config_bytes:
        raise GuardError("CONFIG_CONFLICT")
    if auth_path.exists() and auth_path.read_bytes() != auth_bytes:
        raise GuardError("CONFIG_CONFLICT")
    freeze_bytes(config_path, config_bytes)
    freeze_bytes(auth_path, auth_bytes)
    config_hash = hashlib.sha256(config_bytes).hexdigest()
    from app.replenishment.inputs import load_inputs, select_windows, validate_forecast_coverage

    study_inputs = load_inputs(auth.forecast_dir, auth.bundle_path, config, auth)
    validate_forecast_coverage(
        study_inputs.forecast.rows, config.evaluation_start, config.evaluation_end
    )
    check_study_eligibility(
        select_windows(
            study_inputs.forecast.rows, config.calibration_start, config.calibration_end
        ),
        select_windows(study_inputs.forecast.rows, config.evaluation_start, config.evaluation_end),
    )
    common = [
        "--forecast-dir",
        str(auth.forecast_dir),
        "--bundle",
        str(auth.bundle_path),
        "--config",
        str(config_path),
        "--authorization",
        str(auth_path),
    ]
    cli = [sys.executable, "-m", "app.replenishment.cli"]
    first_result = research_child(
        [*cli, "run", *common, "--output-root", str(root / "runs")], ROOT, "research-run"
    )
    run_id = first_result.get("run_id", "")
    if not re.fullmatch(r"rrv1-[0-9a-f]{64}", run_id):
        raise GuardError("CHILD_OUTPUT_INVALID")
    run = root / "runs" / run_id
    verification = research_child(
        [*cli, "verify", "--run-dir", str(run), "--authorization", str(auth_path)],
        ROOT,
        "research-verify",
    )
    if verification.get("run_id") != run_id or verification.get("status") != "verified":
        raise GuardError("CHILD_OUTPUT_INVALID")
    reconcile = [
        sys.executable,
        "-m",
        "tests.reconcile_replenishment_run",
        "--run-dir",
        str(run),
        *common,
    ]
    evidence = research_child(reconcile, ROOT, "research-reconcile")
    if evidence != {"status": "reconciled", "cases": 36, "days": 6408}:
        raise GuardError("RECONCILIATION_FAILED")
    repeat = research_child(
        [*cli, "run", *common, "--output-root", str(root / "repeat-runs")], ROOT, "research-repeat"
    )
    if repeat.get("run_id") != run_id:
        raise GuardError("REPEAT_MISMATCH")
    compare_scientific(run, root / "repeat-runs" / run_id)
    publication = research_child(
        [
            *cli,
            "publish",
            "--run-dir",
            str(run),
            "--authorization",
            str(auth_path),
            "--catalog-root",
            str(root / "catalog"),
        ],
        ROOT,
        "research-publish",
    )
    if publication.get("run_id") != run_id or publication.get("status") != "published":
        raise GuardError("CHILD_OUTPUT_INVALID")
    verify_public_projection(root / "catalog" / "research" / run_id)
    if config_path.read_bytes() != config_bytes or auth_path.read_bytes() != auth_bytes:
        raise GuardError("CONFIG_CONFLICT")
    return {
        "run_id": run_id,
        "config_sha256": config_hash,
        "private_run": str(run),
        "catalog": str(root / "catalog" / "research" / run_id),
        "cases": 36,
        "days": 6408,
    }


def run_research():
    source_before = source_code_snapshot()
    verify_research_sources()
    try:
        result = _run_research()
    finally:
        verify_research_sources()
        if source_code_snapshot() != source_before:
            raise GuardError("SOURCE_CHANGED")
    from app.analytics.export import canonical_json

    evidence = {
        **result,
        "source_sha256": source_before,
        "bundle_sha256": BUNDLE_HASHES,
        "private_forecast_sha256": PRIVATE_HASHES,
        "public_forecast_sha256": PUBLIC_HASHES,
        "calibration_windows_per_model": {"1": 94, "7": 76},
        "evaluation_common_days": 178,
        "warmup_days": 7,
        "scored_days": 171,
    }
    evidence_path = verification_directory() / ("research-evidence-" + uuid.uuid4().hex + ".json")
    with evidence_path.open("xb") as stream:
        stream.write(canonical_json(evidence))
    print(json.dumps({**result, "evidence": str(evidence_path)}))


E2E_PROJECT = "sw-m7-replenishment-e2e"
E2E_NETWORK = E2E_PROJECT + "-net"
E2E_VOLUME = E2E_PROJECT + "-data"
E2E_APP_IMAGE = "sha256:efaef359acf97e4beb5b50fccc42b3ab86615c61e815e148e3e408c6f3b78bca"
E2E_WEB_IMAGE = "sha256:5c0b47b7b23d7e65adcfbe11a44bb2988f46df44543e6d856bae87c73309af3d"
E2E_STAGE = ROOT / "artifacts/replenishment/e2e-stage-v1"
E2E_OUTPUT = ROOT / "artifacts/replenishment/e2e-fixture-v1"
E2E_LEGACY = ROOT / "artifacts/forecasting/e2e-catalog"
E2E_EMPTY_ENV = ROOT / "artifacts/replenishment/e2e-empty.env"
E2E_COMPOSE = ROOT / "docker-compose.replenishment-e2e.yml"
E2E_NAME = "sw_m7_replenishment_e2e"


def forecast_scenario_matrix():
    return {
        "valid": "forecast-research",
        "ratio": "forecast-ratio",
        "failed-valid": "forecast-failed",
        "unavailable": "forecast-research",
        "corrupt": "forecast-research",
        "unsupported": "forecast-research",
    }


def e2e_settings(replenishment, forecast):
    from sqlalchemy.engine import make_url

    from app.auth.schemas import RegisterRequest

    if replenishment not in {"valid", "unavailable", "failed", "stale", "corrupt", "unsupported"}:
        raise GuardError("SCENARIO_INVALID")
    if forecast not in forecast_scenario_matrix():
        raise GuardError("SCENARIO_INVALID")
    allowed = (
        "SYSTEMROOT",
        "WINDIR",
        "SYSTEMDRIVE",
        "COMSPEC",
        "PATH",
        "PATHEXT",
        "TEMP",
        "TMP",
        "USERNAME",
        "USERPROFILE",
        "APPDATA",
        "LOCALAPPDATA",
        "PROGRAMDATA",
        "PROGRAMFILES",
    )
    env = {key: os.environ[key] for key in allowed if key in os.environ}
    db_password, jwt = secrets.token_urlsafe(32), secrets.token_urlsafe(48)
    database_url = (
        f"postgresql+psycopg://{E2E_NAME}:{quote(db_password, safe='')}@db:5432/{E2E_NAME}"
    )
    env.update(
        {
            "M7_DB_NAME": E2E_NAME,
            "M7_DB_USER": E2E_NAME,
            "M7_DB_PASSWORD": db_password,
            "M7_DATABASE_URL": database_url,
            "M7_JWT_SECRET": jwt,
            "M7_STAGED_APP": str(E2E_STAGE / "app"),
            "M7_STAGED_DIST": str(E2E_STAGE / "dist"),
            "M7_FORECAST_CATALOG": str(E2E_LEGACY / forecast),
            "M7_REPLENISHMENT_CATALOG": str(E2E_OUTPUT / "catalogs" / replenishment),
            "E2E_BASE_URL": "http://127.0.0.1:58082",
            "E2E_FORECAST_SCENARIO": forecast,
            "E2E_REPLENISHMENT_SCENARIO": replenishment,
        }
    )
    sensitive = [
        db_password,
        quote(db_password, safe=""),
        jwt,
        database_url,
        quote(database_url, safe=""),
    ]
    for role in ("ADMIN", "WAREHOUSE", "CLIENT"):
        email, password = f"m7-{role.lower()}@example.com", secrets.token_urlsafe(24)
        checked = RegisterRequest.model_validate({"email": email, "password": password})
        if checked.email != email or checked.password != password:
            raise GuardError("CREDENTIAL_INVALID")
        env[f"M7_{role}_EMAIL"] = env[f"E2E_{role}_EMAIL"] = email
        env[f"M7_{role}_PASSWORD"] = env[f"E2E_{role}_PASSWORD"] = password
        sensitive.extend((email, password, quote(password, safe="")))
    parsed = make_url(database_url)
    if (parsed.host, parsed.database, parsed.username, parsed.password) != (
        "db",
        E2E_NAME,
        E2E_NAME,
        db_password,
    ):
        raise GuardError("CREDENTIAL_INVALID")
    return env, sensitive


def e2e_bind_matches(source, expected):
    from app.replenishment.inputs import _checked

    if not isinstance(source, str) or "\0" in source:
        return False
    value = source.replace("\\", "/")
    for prefix in ("/run/desktop/mnt/host/", "/host_mnt/"):
        if value.startswith(prefix):
            rest = value[len(prefix) :]
            if not re.fullmatch(r"[A-Za-z]/.+", rest):
                return False
            value = rest[0] + ":/" + rest[2:]
            break
    if not re.fullmatch(r"[A-Za-z]:/.+", value):
        return False
    if any(part in ("", ".", "..") or ":" in part for part in value[3:].split("/")):
        return False
    approved = str(_checked(expected)).replace("\\", "/")
    return ntpath.normcase(ntpath.normpath(value)) == ntpath.normcase(ntpath.normpath(approved))


def e2e_resource_inventory():
    def lines(*args):
        return docker_command(*args).splitlines()

    label = f"label=com.docker.compose.project={E2E_PROJECT}"
    return {
        "containers": lines("container", "ls", "-a", "--format", "{{.Names}}"),
        "project_containers": lines("container", "ls", "-a", "--filter", label, "--quiet"),
        "volumes": lines("volume", "ls", "--format", "{{.Name}}"),
        "project_volumes": lines("volume", "ls", "--filter", label, "--quiet"),
        "networks": lines("network", "ls", "--format", "{{.Name}}"),
        "project_networks": lines("network", "ls", "--filter", label, "--quiet"),
    }


def e2e_port_free():
    try:
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 58082))
    except OSError:
        raise GuardError("PORT_OCCUPIED") from None


def e2e_require_absent():
    inventory = e2e_resource_inventory()
    if (
        any(
            name.startswith(E2E_PROJECT + "-") or name.startswith(E2E_PROJECT + "_")
            for name in inventory["containers"]
        )
        or E2E_VOLUME in inventory["volumes"]
        or E2E_NETWORK in inventory["networks"]
        or inventory["project_containers"]
        or inventory["project_volumes"]
        or inventory["project_networks"]
    ):
        raise GuardError("RESOURCE_COLLISION")
    e2e_port_free()


def e2e_check_images():
    try:
        for image in (IMAGE, E2E_APP_IMAGE, E2E_WEB_IMAGE):
            item = json.loads(docker_command("image", "inspect", image))[0]
            if item["Id"] != image:
                raise GuardError("IMAGE_INVALID")
            if image == E2E_APP_IMAGE and (
                item["Config"]["User"],
                item["Config"]["WorkingDir"],
            ) != ("10001:10001", "/app"):
                raise GuardError("IMAGE_INVALID")
            if image == E2E_WEB_IMAGE and item["Config"]["User"] != "101":
                raise GuardError("IMAGE_INVALID")
    except (KeyError, TypeError, IndexError, ValueError):
        raise GuardError("IMAGE_INVALID") from None


def e2e_tree_manifest(root, *, python_only):
    from app.replenishment.inputs import _checked

    root = _checked(root)
    result = {}
    try:
        for path in sorted(root.rglob("*")):
            _checked(path)
            if path.is_file() and (not python_only or path.suffix == ".py"):
                if path.stat().st_size > 64 * 1024 * 1024:
                    raise GuardError("SOURCE_CHANGED")
                result[path.relative_to(root).as_posix()] = hashlib.sha256(
                    path.read_bytes()
                ).hexdigest()
        if not result or len(result) > 5000:
            raise GuardError("SOURCE_CHANGED")
    except (OSError, ValueError):
        raise GuardError("SOURCE_CHANGED") from None
    return result


def e2e_copy_tree(source, destination, *, python_only):
    from app.replenishment.artifacts import _checked

    source = _checked(source)
    destination = _checked(destination, must_exist=False)
    if destination.exists() or destination.is_symlink():
        raise GuardError("OUTPUT_CONFLICT")
    manifest = e2e_tree_manifest(source, python_only=python_only)
    destination.mkdir(parents=True, exist_ok=False)
    for relative in manifest:
        src, target = source / relative, destination / relative
        _checked(src)
        target.parent.mkdir(parents=True, exist_ok=True)
        with src.open("rb") as inp, target.open("xb") as out:
            shutil.copyfileobj(inp, out)
    e2e_verify_tree(source, destination, manifest, python_only=python_only)
    return manifest


def e2e_verify_tree(source, destination, manifest, *, python_only):
    if (
        e2e_tree_manifest(source, python_only=python_only) != manifest
        or e2e_tree_manifest(destination, python_only=False) != manifest
    ):
        raise GuardError("SOURCE_CHANGED")


def e2e_redact(text, sensitive):
    text = redact(text, sensitive)
    return re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "[REDACTED_EMAIL]", text)


def e2e_scrub_diagnostics(root, sensitive):
    from app.replenishment.inputs import _checked

    if not root.exists():
        return
    _checked(root)
    for path in root.rglob("*"):
        _checked(path)
        if path.is_dir():
            continue
        if path.suffix.lower() == ".png" and path.name in {
            "desktop-list.png",
            "desktop-detail.png",
            "mobile-list.png",
            "mobile-detail.png",
        }:
            continue
        if (
            path.suffix.lower() not in {".md", ".txt", ".json"}
            or path.stat().st_size > 8 * 1024 * 1024
        ):
            raise GuardError("DIAGNOSTIC_UNSUPPORTED")
        body = path.read_text(encoding="utf8")
        cleaned = e2e_redact(body, sensitive)
        if cleaned != body:
            path.write_text(cleaned, encoding="utf8", newline="\n")


def e2e_command(
    label, command, env, sensitive, *, cwd=ROOT, timeout=1800, input_text=None, diagnostics=None
):
    log_path = verification_directory() / ("e2e-" + label + "-" + uuid.uuid4().hex + ".log")
    started = time.monotonic()
    try:
        with log_path.open("x", encoding="utf8", newline="\n") as log:
            process = subprocess.Popen(
                command,
                cwd=cwd,
                env=env,
                stdin=subprocess.PIPE if input_text is not None else None,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                errors="replace",
            )
            try:
                output, error = process.communicate(input=input_text, timeout=timeout)
                code = process.returncode
            except subprocess.TimeoutExpired as expired:
                try:
                    terminated = subprocess.run(
                        ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=15,
                        check=False,
                    )
                    output, error = process.communicate(timeout=15)
                    code = 124 if terminated.returncode == 0 else 125
                except (OSError, subprocess.TimeoutExpired):
                    output, error = expired.output or "", expired.stderr or ""
                    if isinstance(output, bytes):
                        output = output.decode("utf8", errors="replace")
                    if isinstance(error, bytes):
                        error = error.decode("utf8", errors="replace")
                    code = 125
            audit_failed = False
            if diagnostics is not None:
                try:
                    e2e_scrub_diagnostics(diagnostics, sensitive)
                except Exception:
                    audit_failed = True
            log.write(
                e2e_redact(json.dumps({"command": command, "cwd": str(cwd)}), sensitive) + "\n"
            )
            log.write(e2e_redact(output, sensitive))
            log.write(e2e_redact(error, sensitive))
            log.write(f"\nexit={code}; elapsed={time.monotonic() - started:.2f}s\n")
    except OSError:
        raise GuardError("PROCESS_UNAVAILABLE") from None
    print(json.dumps({"step": label, "exit": code, "log": str(log_path)}), flush=True)
    if audit_failed:
        raise GuardError("DIAGNOSTIC_UNSUPPORTED")
    if code:
        raise GuardError("CHILD_FAILED")
    return output


def e2e_validate_compose(config, env):
    try:
        services = config["services"]
        if set(services) != {"db", "migrate", "bootstrap", "api", "web"}:
            raise GuardError("COMPOSE_INVALID")
        if any(services[name].get("ports") for name in ("db", "migrate", "bootstrap", "api")):
            raise GuardError("COMPOSE_INVALID")
        ports = services["web"]["ports"]
        if (
            len(ports) != 1
            or str(ports[0]["published"]) != "58082"
            or ports[0]["host_ip"] != "127.0.0.1"
            or ports[0]["target"] != 8080
        ):
            raise GuardError("COMPOSE_INVALID")
        images = {
            "db": IMAGE,
            "migrate": E2E_APP_IMAGE,
            "bootstrap": E2E_APP_IMAGE,
            "api": E2E_APP_IMAGE,
            "web": E2E_WEB_IMAGE,
        }
        for name, image in images.items():
            item = services[name]
            labels = item.get("labels") or {}
            if (
                item.get("image") != image
                or item.get("pull_policy") != "never"
                or item.get("build")
                or item.get("env_file")
                or labels.get("task") != "implement-replenishment-policy"
                or labels.get("role") != "isolated-e2e"
            ):
                raise GuardError("COMPOSE_INVALID")
        if config["networks"]["internal"]["name"] != E2E_NETWORK:
            raise GuardError("COMPOSE_INVALID")
        if config["volumes"]["database"]["name"] != E2E_VOLUME:
            raise GuardError("COMPOSE_INVALID")
        expected_mounts = {
            "migrate": {"/app/app": env["M7_STAGED_APP"]},
            "bootstrap": {"/app/app": env["M7_STAGED_APP"]},
            "api": {
                "/app/app": env["M7_STAGED_APP"],
                "/forecast-catalog": env["M7_FORECAST_CATALOG"],
                "/replenishment-catalog": env["M7_REPLENISHMENT_CATALOG"],
            },
            "web": {"/usr/share/nginx/html": env["M7_STAGED_DIST"]},
        }
        for name, mounts in expected_mounts.items():
            actual = services[name]["volumes"]
            if len(actual) != len(mounts):
                raise GuardError("COMPOSE_INVALID")
            for mount in actual:
                if (
                    mount["type"] != "bind"
                    or mount.get("read_only") is not True
                    or mount["target"] not in mounts
                    or not e2e_bind_matches(mount["source"], mounts[mount["target"]])
                ):
                    raise GuardError("COMPOSE_INVALID")
        db_mount = services["db"]["volumes"]
        if (
            len(db_mount) != 1
            or db_mount[0]["type"] != "volume"
            or db_mount[0]["source"] != "database"
            or db_mount[0]["target"] != "/var/lib/postgresql/data"
        ):
            raise GuardError("COMPOSE_INVALID")
        if any(
            services[name]["environment"]["DATABASE_URL"] != env["M7_DATABASE_URL"]
            for name in ("migrate", "bootstrap", "api")
        ):
            raise GuardError("COMPOSE_INVALID")
        api = services["api"]["environment"]
        if (
            api["APP_ENV"] != "integration"
            or api["FORECAST_ALLOW_FIXTURE"] != "true"
            or api["REPLENISHMENT_ALLOW_FIXTURE"] != "true"
            or api["JWT_SECRET_KEY"] != env["M7_JWT_SECRET"]
            or api["SEED_CLIENT_EMAIL"] != env["M7_CLIENT_EMAIL"]
        ):
            raise GuardError("COMPOSE_INVALID")
        if any(
            services["bootstrap"]["environment"][f"SEED_{role}_{field}"]
            != env[f"M7_{role}_{field}"]
            for role in ("ADMIN", "WAREHOUSE", "CLIENT")
            for field in ("EMAIL", "PASSWORD")
        ):
            raise GuardError("COMPOSE_INVALID")
        if any(
            services["db"]["environment"]["POSTGRES_" + key] != env["M7_DB_" + name]
            for key, name in (("DB", "NAME"), ("USER", "USER"), ("PASSWORD", "PASSWORD"))
        ):
            raise GuardError("COMPOSE_INVALID")
    except (KeyError, TypeError, IndexError, ValueError):
        raise GuardError("COMPOSE_INVALID") from None


def e2e_compose_base():
    return [
        "docker",
        "compose",
        "--project-name",
        E2E_PROJECT,
        "--env-file",
        str(E2E_EMPTY_ENV),
        "-f",
        str(E2E_COMPOSE),
    ]


def e2e_compose_guard(env):
    from app.replenishment.inputs import _checked

    empty = _checked(E2E_EMPTY_ENV)
    if not empty.is_file() or empty.stat().st_size:
        raise GuardError("COMPOSE_INVALID")
    try:
        completed = subprocess.run(
            [*e2e_compose_base(), "config", "--format", "json"],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        if completed.returncode:
            raise GuardError("COMPOSE_INVALID")
        config = json.loads(completed.stdout)
    except (OSError, subprocess.TimeoutExpired, ValueError):
        raise GuardError("COMPOSE_INVALID") from None
    e2e_validate_compose(config, env)


def e2e_source_snapshot():
    from app.replenishment.inputs import _checked

    roots = (ROOT / "app", ROOT / "client/src", ROOT / "client/e2e", ROOT / "alembic")
    fixed = (
        "client/package.json",
        "client/package-lock.json",
        "client/playwright.config.ts",
        "alembic.ini",
        "docker-compose.replenishment-e2e.yml",
        "tests/prepare_replenishment_e2e.py",
        "tests/prepare_forecasting_e2e.py",
        "tests/replenishment_helpers.py",
        "tests/reconcile_replenishment_run.py",
        "tests/run_replenishment_verification.py",
    )
    files = []
    for folder in roots:
        _checked(folder)
        for path in sorted(folder.rglob("*")):
            if "__pycache__" in path.parts:
                continue
            _checked(path)
            if path.is_file():
                files.append(path)
    files.extend(ROOT / item for item in fixed)
    if len(files) > 5000:
        raise GuardError("SOURCE_CHANGED")
    result = {}
    for path in files:
        checked = _checked(path)
        if not checked.is_file() or checked.stat().st_size > 64 * 1024 * 1024:
            raise GuardError("SOURCE_CHANGED")
        result[path.relative_to(ROOT).as_posix()] = hashlib.sha256(checked.read_bytes()).hexdigest()
    return result


def e2e_create_stage():
    from app.analytics.export import canonical_json
    from app.replenishment.artifacts import _checked

    root = _checked(E2E_STAGE, must_exist=False)
    if root.exists() or root.is_symlink():
        raise GuardError("OUTPUT_CONFLICT")
    source = e2e_source_snapshot()
    root.mkdir(parents=True, exist_ok=False)
    with (root / "owner.txt").open("xb") as stream:
        stream.write(b"M7_E2E_STAGE_V1\n")
    app_hashes = e2e_copy_tree(ROOT / "app", root / "app", python_only=True)
    dist_hashes = e2e_copy_tree(ROOT / "client/dist", root / "dist", python_only=False)
    if "index.html" not in dist_hashes or source != e2e_source_snapshot():
        raise GuardError("SOURCE_CHANGED")
    manifest = {
        "schema_version": "m7-e2e-stage/1",
        "source": source,
        "app": app_hashes,
        "dist": dist_hashes,
    }
    with (root / "manifest.json").open("xb") as stream:
        stream.write(canonical_json(manifest))
    return manifest


def e2e_verify_stage():
    from app.analytics.export import canonical_json
    from app.replenishment.inputs import _checked

    root = _checked(E2E_STAGE)
    if {p.name for p in root.iterdir()} != {"app", "dist", "owner.txt", "manifest.json"}:
        raise GuardError("SOURCE_CHANGED")
    if _checked(root / "owner.txt").read_bytes() != b"M7_E2E_STAGE_V1\n":
        raise GuardError("SOURCE_CHANGED")
    raw = _checked(root / "manifest.json").read_bytes()
    try:
        manifest = json.loads(raw)
        if (
            canonical_json(manifest) != raw
            or set(manifest) != {"schema_version", "source", "app", "dist"}
            or manifest["schema_version"] != "m7-e2e-stage/1"
            or manifest["source"] != e2e_source_snapshot()
        ):
            raise GuardError("SOURCE_CHANGED")
        e2e_verify_tree(ROOT / "app", root / "app", manifest["app"], python_only=True)
        e2e_verify_tree(ROOT / "client/dist", root / "dist", manifest["dist"], python_only=False)
    except (KeyError, TypeError, ValueError):
        raise GuardError("SOURCE_CHANGED") from None
    return manifest


def e2e_validate_live(containers, network, volume, env):
    try:
        for resource, name in ((network, E2E_NETWORK), (volume, E2E_VOLUME)):
            labels = resource.get("Labels") or {}
            if (
                resource["Name"] != name
                or labels.get("com.docker.compose.project") != E2E_PROJECT
                or labels.get("task") != "implement-replenishment-policy"
                or labels.get("role") != "isolated-e2e"
            ):
                raise GuardError("RESOURCE_INVALID")
        services = {}
        for item in containers:
            labels = item["Config"]["Labels"] or {}
            service = labels.get("com.docker.compose.service")
            if (
                labels.get("com.docker.compose.project") != E2E_PROJECT
                or labels.get("task") != "implement-replenishment-policy"
                or labels.get("role") != "isolated-e2e"
                or service in services
            ):
                raise GuardError("RESOURCE_INVALID")
            services[service] = item
        if set(services) != {"db", "migrate", "bootstrap", "api", "web"}:
            raise GuardError("RESOURCE_INVALID")
        images = {
            "db": IMAGE,
            "migrate": E2E_APP_IMAGE,
            "bootstrap": E2E_APP_IMAGE,
            "api": E2E_APP_IMAGE,
            "web": E2E_WEB_IMAGE,
        }
        for name, item in services.items():
            if item["Image"] != images[name]:
                raise GuardError("RESOURCE_INVALID")
            ports = item["HostConfig"].get("PortBindings") or {}
            if name == "web":
                if ports != {"8080/tcp": [{"HostIp": "127.0.0.1", "HostPort": "58082"}]}:
                    raise GuardError("RESOURCE_INVALID")
            elif ports:
                raise GuardError("RESOURCE_INVALID")
            running = item["State"]["Running"]
            if name in ("db", "api", "web"):
                if not running or set(item["NetworkSettings"]["Networks"]) != {E2E_NETWORK}:
                    raise GuardError("RESOURCE_INVALID")
                if (
                    name in ("db", "api")
                    and item["State"].get("Health", {}).get("Status") != "healthy"
                ):
                    raise GuardError("RESOURCE_INVALID")
            elif running or item["State"]["ExitCode"] != 0:
                raise GuardError("RESOURCE_INVALID")
        expected_ids = {item["Id"] for item in services.values() if item["State"]["Running"]}
        if set((network.get("Containers") or {}).keys()) != expected_ids:
            raise GuardError("RESOURCE_INVALID")
        db_mounts = services["db"]["Mounts"]
        if (
            len(db_mounts) != 1
            or db_mounts[0]["Type"] != "volume"
            or db_mounts[0]["Name"] != E2E_VOLUME
            or not db_mounts[0]["RW"]
            or db_mounts[0]["Destination"] != "/var/lib/postgresql/data"
        ):
            raise GuardError("RESOURCE_INVALID")
        expected_mounts = {
            "migrate": {"/app/app": env["M7_STAGED_APP"]},
            "bootstrap": {"/app/app": env["M7_STAGED_APP"]},
            "api": {
                "/app/app": env["M7_STAGED_APP"],
                "/forecast-catalog": env["M7_FORECAST_CATALOG"],
                "/replenishment-catalog": env["M7_REPLENISHMENT_CATALOG"],
            },
            "web": {"/usr/share/nginx/html": env["M7_STAGED_DIST"]},
        }
        for name, wanted in expected_mounts.items():
            mounts = services[name]["Mounts"]
            if len(mounts) != len(wanted):
                raise GuardError("RESOURCE_INVALID")
            for mount in mounts:
                target = mount["Destination"]
                if (
                    mount["Type"] != "bind"
                    or mount["RW"]
                    or target not in wanted
                    or not e2e_bind_matches(mount["Source"], wanted[target])
                ):
                    raise GuardError("RESOURCE_INVALID")

        def variables(item):
            return dict(value.split("=", 1) for value in item["Config"]["Env"] if "=" in value)

        api, db, bootstrap = (variables(services[name]) for name in ("api", "db", "bootstrap"))
        if (
            api.get("DATABASE_URL") != env["M7_DATABASE_URL"]
            or api.get("APP_ENV") != "integration"
            or api.get("JWT_SECRET_KEY") != env["M7_JWT_SECRET"]
            or api.get("FORECAST_ALLOW_FIXTURE") != "true"
            or api.get("REPLENISHMENT_ALLOW_FIXTURE") != "true"
            or api.get("SEED_CLIENT_EMAIL") != env["M7_CLIENT_EMAIL"]
        ):
            raise GuardError("RESOURCE_INVALID")
        if any(
            db.get("POSTGRES_" + key) != env["M7_DB_" + field]
            for key, field in (("DB", "NAME"), ("USER", "USER"), ("PASSWORD", "PASSWORD"))
        ):
            raise GuardError("RESOURCE_INVALID")
        if any(
            bootstrap.get(f"SEED_{role}_{field}") != env[f"M7_{role}_{field}"]
            for role in ("ADMIN", "WAREHOUSE", "CLIENT")
            for field in ("EMAIL", "PASSWORD")
        ):
            raise GuardError("RESOURCE_INVALID")
        return services
    except (KeyError, TypeError, IndexError, ValueError):
        raise GuardError("RESOURCE_INVALID") from None


def e2e_inspect():
    label = f"label=com.docker.compose.project={E2E_PROJECT}"
    ids = docker_command("container", "ls", "-a", "--filter", label, "--quiet").splitlines()
    if len(ids) != 5:
        raise GuardError("RESOURCE_INVALID")
    try:
        containers = [json.loads(docker_command("inspect", item))[0] for item in ids]
        network = json.loads(docker_command("network", "inspect", E2E_NETWORK))[0]
        volume = json.loads(docker_command("volume", "inspect", E2E_VOLUME))[0]
        return containers, network, volume
    except (ValueError, IndexError, TypeError):
        raise GuardError("RESOURCE_INVALID") from None


def e2e_live_guard(env):
    check_docker_context()
    containers, network, volume = e2e_inspect()
    services = e2e_validate_live(containers, network, volume, env)
    sql = (
        "select current_database(), current_user, pg_get_userbyid(datdba) "
        "from pg_database where datname=current_database()"
    )
    identity = docker_command(
        "exec", services["db"]["Id"], "psql", "-U", E2E_NAME, "-d", E2E_NAME, "-Atc", sql
    ).strip()
    if identity != f"{E2E_NAME}|{E2E_NAME}|{E2E_NAME}":
        raise GuardError("DATABASE_INVALID")
    return {name: item["Id"] for name, item in services.items()}


def e2e_recover_environment():
    from sqlalchemy.engine import make_url

    from app.auth.schemas import RegisterRequest

    containers, network, volume = e2e_inspect()
    try:
        by_service = {}
        for item in containers:
            labels = item["Config"]["Labels"] or {}
            service = labels.get("com.docker.compose.service")
            if (
                labels.get("com.docker.compose.project") != E2E_PROJECT
                or labels.get("task") != "implement-replenishment-policy"
                or labels.get("role") != "isolated-e2e"
                or service in by_service
            ):
                raise GuardError("RESOURCE_INVALID")
            by_service[service] = item
        if set(by_service) != {"db", "migrate", "bootstrap", "api", "web"}:
            raise GuardError("RESOURCE_INVALID")
        mounts = {m["Destination"]: m["Source"] for m in by_service["api"]["Mounts"]}
        if len(mounts) != 3:
            raise GuardError("RESOURCE_INVALID")
        forecast = [
            name
            for name in forecast_scenario_matrix()
            if e2e_bind_matches(mounts.get("/forecast-catalog"), E2E_LEGACY / name)
        ]
        policy = [
            name
            for name in ("valid", "unavailable", "failed", "stale", "corrupt", "unsupported")
            if e2e_bind_matches(
                mounts.get("/replenishment-catalog"), E2E_OUTPUT / "catalogs" / name
            )
        ]
        if len(forecast) != 1 or len(policy) != 1:
            raise GuardError("RESOURCE_INVALID")

        def variables(item):
            return dict(value.split("=", 1) for value in item["Config"]["Env"] if "=" in value)

        api, db, bootstrap = (variables(by_service[name]) for name in ("api", "db", "bootstrap"))
        allowed = (
            "SYSTEMROOT",
            "WINDIR",
            "SYSTEMDRIVE",
            "COMSPEC",
            "PATH",
            "PATHEXT",
            "TEMP",
            "TMP",
            "USERNAME",
            "USERPROFILE",
            "APPDATA",
            "LOCALAPPDATA",
            "PROGRAMDATA",
            "PROGRAMFILES",
        )
        env = {key: os.environ[key] for key in allowed if key in os.environ}
        env.update(
            {
                "M7_DB_NAME": E2E_NAME,
                "M7_DB_USER": E2E_NAME,
                "M7_DB_PASSWORD": db["POSTGRES_PASSWORD"],
                "M7_DATABASE_URL": api["DATABASE_URL"],
                "M7_JWT_SECRET": api["JWT_SECRET_KEY"],
                "M7_STAGED_APP": str(E2E_STAGE / "app"),
                "M7_STAGED_DIST": str(E2E_STAGE / "dist"),
                "M7_FORECAST_CATALOG": str(E2E_LEGACY / forecast[0]),
                "M7_REPLENISHMENT_CATALOG": str(E2E_OUTPUT / "catalogs" / policy[0]),
                "E2E_BASE_URL": "http://127.0.0.1:58082",
                "E2E_FORECAST_SCENARIO": forecast[0],
                "E2E_REPLENISHMENT_SCENARIO": policy[0],
            }
        )
        url = make_url(env["M7_DATABASE_URL"])
        if (url.drivername, url.host, url.database, url.username, url.password) != (
            "postgresql+psycopg",
            "db",
            E2E_NAME,
            E2E_NAME,
            env["M7_DB_PASSWORD"],
        ):
            raise GuardError("RESOURCE_INVALID")
        sensitive = [
            env["M7_DB_PASSWORD"],
            quote(env["M7_DB_PASSWORD"], safe=""),
            env["M7_DATABASE_URL"],
            quote(env["M7_DATABASE_URL"], safe=""),
            env["M7_JWT_SECRET"],
        ]
        for role in ("ADMIN", "WAREHOUSE", "CLIENT"):
            email, password = bootstrap[f"SEED_{role}_EMAIL"], bootstrap[f"SEED_{role}_PASSWORD"]
            request = RegisterRequest.model_validate({"email": email, "password": password})
            if request.email != email or request.password != password:
                raise GuardError("RESOURCE_INVALID")
            env[f"M7_{role}_EMAIL"] = env[f"E2E_{role}_EMAIL"] = email
            env[f"M7_{role}_PASSWORD"] = env[f"E2E_{role}_PASSWORD"] = password
            sensitive.extend((email, password, quote(password, safe="")))
        services = e2e_validate_live(containers, network, volume, env)
        identities = e2e_live_guard(env)
        if identities != {name: item["Id"] for name, item in services.items()}:
            raise GuardError("RESOURCE_INVALID")
        return env, sensitive, identities
    except (KeyError, TypeError, ValueError, IndexError):
        raise GuardError("RESOURCE_INVALID") from None


E2E_SEED_RECEIPT = ROOT / "artifacts/replenishment/verification/e2e-seed-receipt.json"


def e2e_validate_seed_receipt(receipt):
    try:
        if (
            set(receipt) != {"binding", "legacy_request_id", "protected_tables"}
            or receipt["binding"] != [2, 2, "unit"]
            or type(receipt["legacy_request_id"]) is not int
            or not 1 <= receipt["legacy_request_id"] <= 2147483647
            or set(receipt["protected_tables"]) != {"stocks", "outbounds", "transactions"}
        ):
            raise GuardError("SEED_INVALID")
        for data in receipt["protected_tables"].values():
            if (
                set(data) != {"count", "sha256"}
                or type(data["count"]) is not int
                or data["count"] < 0
                or not re.fullmatch(r"[0-9a-f]{64}", data["sha256"])
            ):
                raise GuardError("SEED_INVALID")
    except (KeyError, TypeError):
        raise GuardError("SEED_INVALID") from None


def e2e_read_seed_receipt():
    from app.analytics.export import canonical_json
    from app.replenishment.inputs import _checked

    try:
        raw = _checked(E2E_SEED_RECEIPT).read_bytes()
        if len(raw) > 4096:
            raise GuardError("SEED_INVALID")
        receipt = json.loads(raw)
        if canonical_json(receipt) != raw:
            raise GuardError("SEED_INVALID")
        e2e_validate_seed_receipt(receipt)
        return receipt
    except (OSError, ValueError, TypeError):
        raise GuardError("SEED_INVALID") from None


def e2e_database_snapshot(env, sensitive, ids, label):
    script = r"""
import hashlib, json, os
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
url = make_url(os.environ['DATABASE_URL'])
expected = 'sw_m7_replenishment_e2e'
if (url.drivername, url.host, url.database, url.username) != (
    'postgresql+psycopg', 'db', expected, expected
):
    raise SystemExit(2)
engine = create_engine(url)
try:
    with engine.connect() as connection:
        connection.execute(text('SET TRANSACTION READ ONLY'))
        identity = connection.execute(text(
            "select current_database(),current_user,pg_get_userbyid(datdba) "
            "from pg_database where datname=current_database()"
        )).one()
        if tuple(identity) != (expected, expected, expected):
            raise SystemExit(2)
        result = {}
        for table in ('stocks', 'outbounds', 'transactions'):
            rows = connection.execute(text(
                f'SELECT CAST(row_to_json(t) AS text) FROM {table} t ORDER BY id'
            )).scalars()
            digest, count = hashlib.sha256(), 0
            for row in rows:
                digest.update(row.encode('utf8') + b'\n')
                count += 1
            result[table] = {'count': count, 'sha256': digest.hexdigest()}
        print(json.dumps(result))
finally:
    engine.dispose()
"""
    output = e2e_command(
        label,
        ["docker", "exec", "-i", ids["api"], "python", "-"],
        env,
        sensitive,
        input_text=script,
        timeout=60,
    )
    try:
        result = json.loads(output)
        e2e_validate_seed_receipt(
            {"binding": [2, 2, "unit"], "legacy_request_id": 1, "protected_tables": result}
        )
        return result
    except (ValueError, TypeError):
        raise GuardError("SEED_INVALID") from None


def e2e_verify_seed(env, sensitive, ids, receipt):
    e2e_validate_seed_receipt(receipt)
    script = r"""
import json, os, sys
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
url = make_url(os.environ['DATABASE_URL'])
expected = 'sw_m7_replenishment_e2e'
if (url.drivername, url.host, url.database, url.username) != (
    'postgresql+psycopg', 'db', expected, expected
):
    raise SystemExit(2)
engine = create_engine(url)
try:
    with engine.connect() as connection:
        connection.execute(text('SET TRANSACTION READ ONLY'))
        identity = connection.execute(text(
            "select current_database(),current_user,pg_get_userbyid(datdba) "
            "from pg_database where datname=current_database()"
        )).one()
        if tuple(identity) != (expected, expected, expected):
            raise SystemExit(2)
        binding = connection.execute(text(
            "select p.sku,p.unit,w.code from products p cross join warehouses w "
            "where p.id=2 and w.id=2"
        )).one()
        if tuple(binding) != ('M7-E2E-SYNTHETIC', 'unit', 'M7-E2E-SYNTHETIC'):
            raise SystemExit(2)
        legacy = connection.execute(text(
            "select pr.id from purchase_requests pr join users u on u.id=pr.requested_by_id "
            "join products p on p.id=pr.product_id "
            "left join purchase_request_workflows wf on wf.purchase_request_id=pr.id "
            "where pr.id=:request_id and pr.request_number='M4-LEGACY-M7' "
            "and u.email=:email and u.role='client' and p.sku='M4-LEGACY-M7' "
            "and wf.purchase_request_id is null"
        ), {'request_id': int(sys.argv[1]), 'email': os.environ['SEED_CLIENT_EMAIL']}).all()
        if len(legacy) != 1:
            raise SystemExit(2)
        print(json.dumps({'status': 'verified', 'legacy_request_id': int(sys.argv[1])}))
finally:
    engine.dispose()
"""
    output = e2e_command(
        "seed-check",
        ["docker", "exec", "-i", ids["api"], "python", "-", str(receipt["legacy_request_id"])],
        env,
        sensitive,
        input_text=script,
        timeout=60,
    )
    try:
        if json.loads(output) != {
            "status": "verified",
            "legacy_request_id": receipt["legacy_request_id"],
        }:
            raise GuardError("SEED_INVALID")
    except (ValueError, TypeError):
        raise GuardError("SEED_INVALID") from None


def e2e_load_or_prepare_fixture():
    from app.replenishment.artifacts import verify_public_projection
    from app.replenishment.inputs import _checked
    from tests import prepare_replenishment_e2e as fixture

    roots = (fixture.OUTPUT, fixture.FORECAST, fixture.BUNDLES, fixture.LEGACY_FORECAST)
    states = tuple(path.exists() or path.is_symlink() for path in roots)
    if all(states):
        return fixture.verify_existing()
    if any(states):
        raise GuardError("FIXTURE_INCOMPLETE")
    research_root = _checked(fixture.RESEARCH_CATALOG)
    entries = tuple(research_root.iterdir())
    if len(entries) != 1 or not re.fullmatch(r"rrv1-[0-9a-f]{64}", entries[0].name):
        raise GuardError("RESEARCH_INPUT_INVALID")
    research = _checked(entries[0])
    public = verify_public_projection(research)
    if (public["mode"], public["dataset_class"], public["forecast_run_id"]) != (
        "research",
        "research",
        FORECAST_ID,
    ):
        raise GuardError("RESEARCH_INPUT_INVALID")
    env = research_environment(ROOT)
    env["M7_E2E_PREPARE_RELEASE"] = "1"
    output = e2e_command(
        "fixture-prepare",
        [
            sys.executable,
            "-m",
            "tests.prepare_replenishment_e2e",
            "--execute",
            "--research-run",
            str(research),
        ],
        env,
        [],
        timeout=1800,
    )
    try:
        created = json.loads(output)
        verified = fixture.verify_existing()
        if created != verified:
            raise GuardError("FIXTURE_INCOMPLETE")
        return verified
    except (TypeError, ValueError):
        raise GuardError("FIXTURE_INCOMPLETE") from None


def e2e_suite_plan(suite, scenario):
    policies = {"unavailable", "failed", "stale", "corrupt", "unsupported"}
    if suite not in {"all", "replenishment"}:
        raise GuardError("SCENARIO_INVALID")
    if scenario == "valid":
        return [{"policy": "valid", "forecast": "valid", "suite": suite}]
    if scenario in policies and suite == "replenishment":
        return [{"policy": scenario, "forecast": "valid", "suite": "replenishment"}]
    forecasts = {
        "forecast-research": ("valid", "unavailable", "corrupt", "unsupported"),
        "forecast-ratio": ("ratio",),
        "forecast-failed": ("failed-valid",),
    }
    if scenario in forecasts:
        return [
            {"policy": "valid", "forecast": name, "suite": "forecast"}
            for name in forecasts[scenario]
        ]
    raise GuardError("SCENARIO_INVALID")


def e2e_start():
    from app.analytics.export import canonical_json
    from app.replenishment.inputs import _checked
    from tests.prepare_replenishment_e2e import verify_existing

    check_docker_context()
    check_disk()
    e2e_check_images()
    e2e_require_absent()
    if any(
        path.exists() or path.is_symlink() for path in (E2E_STAGE, E2E_EMPTY_ENV, E2E_SEED_RECEIPT)
    ):
        raise GuardError("OUTPUT_CONFLICT")
    if any((ROOT / "client").glob(".env*")):
        raise GuardError("ENVIRONMENT_INVALID")
    fixture = e2e_load_or_prepare_fixture()
    source = e2e_source_snapshot()
    env, sensitive = e2e_settings("valid", "valid")
    build_env = {
        key: value
        for key, value in env.items()
        if not key.startswith("M7_") and not key.startswith("E2E_")
    }
    build_env["VITE_API_BASE_URL"] = "/api/v1"
    e2e_command("frontend-build", ["npm.cmd", "run", "build"], build_env, [], cwd=ROOT / "client")
    if e2e_source_snapshot() != source:
        raise GuardError("SOURCE_CHANGED")
    e2e_create_stage()
    with E2E_EMPTY_ENV.open("xb"):
        pass
    e2e_verify_stage()
    e2e_compose_guard(env)
    e2e_require_absent()
    e2e_command(
        "up",
        [*e2e_compose_base(), "up", "-d", "--no-build", "--pull", "never", "--wait"],
        env,
        sensitive,
    )
    identities = e2e_live_guard(env)
    e2e_verify_stage()
    import_check = (
        "import pathlib,app,sys; p=pathlib.Path(app.__file__).resolve(); "
        "print('M7_APP_IMPORT_OK' if p == pathlib.Path('/app/app/__init__.py') else 'INVALID'); "
        "sys.exit(0 if p == pathlib.Path('/app/app/__init__.py') else 2)"
    )
    imported = e2e_command(
        "app-import",
        ["docker", "exec", identities["api"], "python", "-c", import_check],
        env,
        sensitive,
        timeout=60,
    )
    if imported.strip() != "M7_APP_IMPORT_OK":
        raise GuardError("SOURCE_CHANGED")
    script = _checked(ROOT / "tests/prepare_replenishment_e2e.py").read_text(encoding="utf8")
    output = e2e_command(
        "fixture-seed",
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
        input_text=script,
        timeout=60,
    )
    try:
        seed = json.loads(output)
        e2e_validate_seed_receipt(seed)
    except (ValueError, TypeError):
        raise GuardError("SEED_INVALID") from None
    after = e2e_database_snapshot(env, sensitive, identities, "seed-protected-after")
    if after != seed["protected_tables"]:
        raise GuardError("SEED_INVALID")
    with E2E_SEED_RECEIPT.open("xb") as stream:
        stream.write(canonical_json(seed))
        stream.flush()
        os.fsync(stream.fileno())
    e2e_verify_seed(env, sensitive, identities, seed)
    if e2e_live_guard(env) != identities or e2e_verify_stage()["source"] != source:
        raise GuardError("RESOURCE_INVALID")
    if verify_existing() != fixture:
        raise GuardError("SOURCE_CHANGED")
    print(
        json.dumps(
            {
                "status": "ready",
                "fixture_run_id": fixture["fixture_run_id"],
                "research_run_id": fixture["research_run_id"],
                "legacy_request_id": seed["legacy_request_id"],
                "seed_receipt": str(E2E_SEED_RECEIPT),
                "resources": identities,
            }
        )
    )


def e2e_web_ready():
    from urllib.error import URLError
    from urllib.request import urlopen

    deadline = time.monotonic() + 45
    while True:
        try:
            with urlopen("http://127.0.0.1:58082/api/v1/health/ready", timeout=2) as response:
                if response.status == 200:
                    return
        except (OSError, URLError):
            pass
        if time.monotonic() >= deadline:
            raise GuardError("WEB_UNAVAILABLE")
        time.sleep(0.25)


def e2e_switch(env, sensitive, policy, forecast):
    from tests.prepare_replenishment_e2e import verify_existing

    if policy not in {"valid", "unavailable", "failed", "stale", "corrupt", "unsupported"}:
        raise GuardError("SCENARIO_INVALID")
    if forecast not in forecast_scenario_matrix():
        raise GuardError("SCENARIO_INVALID")
    e2e_verify_stage()
    before = e2e_live_guard(env)
    if env["E2E_REPLENISHMENT_SCENARIO"] == policy and env["E2E_FORECAST_SCENARIO"] == forecast:
        return env, before
    verify_existing()
    updated = env.copy()
    updated["E2E_REPLENISHMENT_SCENARIO"] = policy
    updated["E2E_FORECAST_SCENARIO"] = forecast
    updated["M7_REPLENISHMENT_CATALOG"] = str(E2E_OUTPUT / "catalogs" / policy)
    updated["M7_FORECAST_CATALOG"] = str(E2E_LEGACY / forecast)
    e2e_compose_guard(updated)
    if e2e_live_guard(env) != before:
        raise GuardError("RESOURCE_INVALID")
    e2e_command(
        "switch-api",
        [
            *e2e_compose_base(),
            "up",
            "-d",
            "--no-deps",
            "--force-recreate",
            "--no-build",
            "--pull",
            "never",
            "--wait",
            "api",
        ],
        updated,
        sensitive,
        timeout=600,
    )
    replaced = e2e_live_guard(updated)
    if (
        any(replaced[name] != before[name] for name in ("db", "migrate", "bootstrap", "web"))
        or replaced["api"] == before["api"]
    ):
        raise GuardError("RESOURCE_INVALID")
    e2e_command(
        "restart-web", ["docker", "restart", replaced["web"]], updated, sensitive, timeout=60
    )
    after = e2e_live_guard(updated)
    if after != replaced:
        raise GuardError("RESOURCE_INVALID")
    e2e_web_ready()
    e2e_verify_stage()
    verify_existing()
    print(
        json.dumps(
            {
                "status": "switched",
                "policy": policy,
                "forecast": forecast,
                "before": before,
                "after": after,
            }
        )
    )
    return updated, after


def e2e_test_counts(output):
    clean = re.sub(r"\x1b\[[0-9;]*m", "", output)
    counts = {
        name: int(count)
        for count, name in re.findall(r"(?m)^\s*(\d+)\s+(passed|skipped|failed)\b", clean)
    }
    if "passed" not in counts or counts.get("failed", 0):
        raise GuardError("TEST_OUTPUT_INVALID")
    return {
        "passed": counts["passed"],
        "skipped": counts.get("skipped", 0),
        "failed": counts.get("failed", 0),
    }


def e2e_screenshot_evidence(result_root):
    from app.analytics.export import canonical_json
    from app.replenishment.inputs import _checked

    root = _checked(result_root)
    names = ("desktop-list.png", "desktop-detail.png", "mobile-list.png", "mobile-detail.png")
    evidence = {}
    for name in names:
        matches = tuple(root.rglob(name))
        if len(matches) != 1:
            raise GuardError("SCREENSHOT_MISSING")
        path = _checked(matches[0])
        body = path.read_bytes()
        if not body.startswith(b"\x89PNG\r\n\x1a\n") or len(body) > 16 * 1024 * 1024:
            raise GuardError("SCREENSHOT_INVALID")
        evidence[name] = {"path": str(path), "sha256": hashlib.sha256(body).hexdigest()}
    destination = verification_directory() / ("e2e-screenshots-" + uuid.uuid4().hex + ".json")
    with destination.open("xb") as stream:
        stream.write(canonical_json(evidence))
    return destination


def e2e_check():
    from tests import prepare_replenishment_e2e as fixture

    check_docker_context()
    check_disk()
    e2e_check_images()
    if any((ROOT / "client").glob(".env*")):
        raise GuardError("ENVIRONMENT_INVALID")
    states = tuple(
        path.exists() or path.is_symlink()
        for path in (fixture.OUTPUT, fixture.FORECAST, fixture.BUNDLES, fixture.LEGACY_FORECAST)
    )
    if all(states):
        fixture_state = fixture.verify_existing()
    elif any(states):
        raise GuardError("FIXTURE_INCOMPLETE")
    else:
        fixture_state = {"status": "absent"}
    inventory = e2e_resource_inventory()
    if not (
        inventory["project_containers"]
        or inventory["project_volumes"]
        or inventory["project_networks"]
    ):
        e2e_require_absent()
        if any(
            path.exists() or path.is_symlink()
            for path in (E2E_STAGE, E2E_EMPTY_ENV, E2E_SEED_RECEIPT)
        ):
            raise GuardError("OUTPUT_CONFLICT")
        return {"state": "ABSENT", "fixture": fixture_state}
    e2e_verify_stage()
    env, sensitive, ids = e2e_recover_environment()
    receipt = e2e_read_seed_receipt()
    e2e_verify_seed(env, sensitive, ids, receipt)
    return {
        "state": "RUNNING",
        "fixture": fixture_state,
        "resources": ids,
        "policy": env["E2E_REPLENISHMENT_SCENARIO"],
        "forecast": env["E2E_FORECAST_SCENARIO"],
    }


def e2e_playwright(env, sensitive, identities, specs, label, *, read_only, screenshots):
    from tests.prepare_replenishment_e2e import verify_existing

    e2e_verify_stage()
    verify_existing()
    if e2e_live_guard(env) != identities:
        raise GuardError("RESOURCE_INVALID")
    receipt = e2e_read_seed_receipt()
    e2e_verify_seed(env, sensitive, identities, receipt)
    e2e_web_ready()
    before = (
        e2e_database_snapshot(env, sensitive, identities, label + "-before") if read_only else None
    )
    output_dir = verification_directory() / ("e2e-output-" + uuid.uuid4().hex)
    command = [
        "npm.cmd",
        "exec",
        "--",
        "playwright",
        "test",
        *specs,
        "--reporter=list",
        "--retries=0",
        "--output",
        str(output_dir),
    ]
    try:
        output = e2e_command(
            label,
            command,
            env,
            sensitive,
            cwd=ROOT / "client",
            timeout=1800,
            diagnostics=output_dir,
        )
        counts = e2e_test_counts(output)
        evidence = e2e_screenshot_evidence(output_dir) if screenshots else None
    finally:
        if e2e_live_guard(env) != identities:
            raise GuardError("RESOURCE_INVALID")
        if (
            read_only
            and e2e_database_snapshot(env, sensitive, identities, label + "-after") != before
        ):
            raise GuardError("BUSINESS_STATE_CHANGED")
        e2e_verify_stage()
        verify_existing()
    result = {
        "suite": label,
        "policy": env["E2E_REPLENISHMENT_SCENARIO"],
        "forecast": env["E2E_FORECAST_SCENARIO"],
        "counts": counts,
        "output": str(output_dir),
        "screenshots": str(evidence) if evidence else None,
    }
    print(json.dumps(result), flush=True)
    return result


def e2e_run(suite, scenario):
    from tests.prepare_replenishment_e2e import verify_existing

    plan = e2e_suite_plan(suite, scenario)
    check_docker_context()
    check_disk()
    e2e_check_images()
    e2e_verify_stage()
    fixture = verify_existing()
    env, sensitive, identities = e2e_recover_environment()
    receipt = e2e_read_seed_receipt()
    e2e_verify_seed(env, sensitive, identities, receipt)
    env["E2E_REPLENISHMENT_RUN_ID"] = fixture["fixture_run_id"]
    env["E2E_REPLENISHMENT_RESEARCH_RUN_ID"] = fixture["research_run_id"]
    env["E2E_M4_LEGACY_REQUEST_ID"] = str(receipt["legacy_request_id"])
    results = []
    for item in plan:
        env, identities = e2e_switch(env, sensitive, item["policy"], item["forecast"])
        if item["suite"] == "all":
            results.append(
                e2e_playwright(
                    env,
                    sensitive,
                    identities,
                    ["e2e/replenishment.spec.ts", "e2e/auth-client.spec.ts"],
                    "focused",
                    read_only=True,
                    screenshots=True,
                )
            )
            results.append(
                e2e_playwright(
                    env, sensitive, identities, [], "full", read_only=False, screenshots=True
                )
            )
        elif item["suite"] == "replenishment":
            results.append(
                e2e_playwright(
                    env,
                    sensitive,
                    identities,
                    ["e2e/replenishment.spec.ts"],
                    "replenishment-" + item["policy"],
                    read_only=True,
                    screenshots=item["policy"] == "valid",
                )
            )
        else:
            results.append(
                e2e_playwright(
                    env,
                    sensitive,
                    identities,
                    ["e2e/forecasting.spec.ts"],
                    "forecast-" + item["forecast"],
                    read_only=True,
                    screenshots=False,
                )
            )
    print(json.dumps({"status": "completed", "scenario": scenario, "results": results}))


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("plan", "check", "start", "backend", "research", "e2e"))
    parser.add_argument("--target", choices=("backend", "e2e"))
    parser.add_argument("--suite", choices=("all", "replenishment"))
    parser.add_argument(
        "--scenario",
        choices=(
            "valid",
            "unavailable",
            "failed",
            "stale",
            "corrupt",
            "unsupported",
            "forecast-research",
            "forecast-ratio",
            "forecast-failed",
        ),
    )
    args = parser.parse_args(argv)
    try:
        check_environment()
        if args.command == "plan":
            print(
                json.dumps(
                    {
                        "root": str(ROOT),
                        "backend": NAME,
                        "port": 18547,
                        "commands": ["check", "start", "backend", "research"],
                        "source_sha256": {
                            path.relative_to(ROOT).as_posix(): hashlib.sha256(
                                path.read_bytes()
                            ).hexdigest()
                            for module in ("analytics", "forecasting", "replenishment")
                            for path in sorted((ROOT / "app" / module).glob("*.py"))
                        },
                    }
                )
            )
            return 0
        if args.command == "check" and args.target == "backend":
            check_docker_context()
            check_disk()
            state = check_resource_state()
            if state in ("ABSENT", "STOPPED"):
                port_is_free()
                image = docker_command("image", "inspect", IMAGE, "--format", "{{.Id}}").strip()
                if image != IMAGE:
                    raise GuardError("IMAGE_INVALID")
            print(json.dumps({"backend": NAME, "state": state}))
            return 0
        if args.command == "check" and args.target == "e2e":
            print(json.dumps(e2e_check()))
            return 0
        if args.command == "start" and args.target == "e2e":
            with execution_lock():
                e2e_start()
            return 0
        if args.command == "e2e" and args.target is None and args.suite and args.scenario:
            with execution_lock():
                e2e_run(args.suite, args.scenario)
            return 0
        if args.command == "start" and args.target == "backend":
            check_docker_context()
            check_disk()
            with execution_lock():
                start_backend()
            print(json.dumps({"backend": NAME, "state": "RUNNING"}))
            return 0
        if args.command == "backend" and args.target is None:
            check_docker_context()
            check_disk()
            with execution_lock():
                run_backend()
            return 0
        if args.command == "research" and args.target is None:
            with execution_lock():
                run_research()
            return 0
        raise GuardError("RUNNER_INCOMPLETE")
    except GuardError as exc:
        print(json.dumps({"code": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
