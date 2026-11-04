"""Prepare explicit, isolated M7 browser fixtures; never use real warehouse records."""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_ROOT = Path("C:/Users/TQUOCTOAN/.codex/worktrees/m7-replenishment-policy/smart-warehouse")
OUTPUT = ROOT / "artifacts/replenishment/e2e-fixture-v1"
FORECAST = ROOT / "artifacts/forecasting/m7-e2e-fixture-v1"
BUNDLES = ROOT / "artifacts/demand-data/m7-e2e-fixture-v1"
LEGACY_FORECAST = ROOT / "artifacts/forecasting/e2e-catalog"
RESEARCH_CATALOG = ROOT / "artifacts/replenishment/research/catalog/research"
OWNER = b"M7_REPLENISHMENT_E2E_FIXTURE_V1\n"


def validate_profile(profile, research_run):
    if profile == "local":
        return
    if profile != "synthetic-only" or os.environ.get("QUALITY_CI_PROFILE") != profile:
        raise ValueError("PROFILE_INVALID")
    if research_run is not None:
        raise ValueError("PROFILE_INVALID")
    from tests.run_quality_ci import check_context

    check_context()


def checked_workspace(profile="local"):
    import app
    from app.replenishment.artifacts import _checked

    if profile == "local" and (ROOT != EXPECTED_ROOT.resolve() or Path.cwd().resolve() != ROOT):
        raise ValueError("WORKTREE_INVALID")
    if not Path(app.__file__).resolve().is_relative_to(ROOT / "app"):
        raise ValueError("WORKTREE_INVALID")
    if (ROOT / ".env").exists() or any(
        key in os.environ
        for key in (
            "ANALYTICS_DATABASE_URL",
            "DATABASE_URL",
            "TEST_DATABASE_URL",
            "TEST_MIGRATION_DATABASE_URL",
        )
    ):
        raise ValueError("ENVIRONMENT_INVALID")
    for path in (OUTPUT, FORECAST, BUNDLES, LEGACY_FORECAST):
        _checked(path, must_exist=False)
        if path.exists() or path.is_symlink():
            raise ValueError("OUTPUT_CONFLICT")


def run_cli(*arguments):
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
    env["PYTHONPATH"] = str(ROOT)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    for key in (
        "OMP_NUM_THREADS",
        "OPENBLAS_NUM_THREADS",
        "MKL_NUM_THREADS",
        "NUMEXPR_NUM_THREADS",
    ):
        env[key] = "1"
    process = subprocess.Popen(
        [sys.executable, "-m", *map(str, arguments)],
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        stdout, _ = process.communicate(timeout=600)
    except subprocess.TimeoutExpired:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=15,
                check=False,
            )
        else:
            process.kill()
        try:
            process.communicate(timeout=15)
        except subprocess.TimeoutExpired:
            raise ValueError("CHILD_TERMINATION_UNCONFIRMED") from None
        raise ValueError("CHILD_TIMEOUT") from None
    if process.returncode:
        raise ValueError("CHILD_FAILED")
    return json.loads(stdout)


def fixture_inventory(root, *, exclude=()):
    from app.replenishment.artifacts import _checked

    root = _checked(Path(root))
    entries = sorted(root.rglob("*"))
    if len(entries) > 1000:
        raise ValueError("FIXTURE_CHANGED")
    files, directories = {}, []
    for path in entries:
        _checked(path)
        relative = path.relative_to(root).as_posix()
        if path.is_dir():
            directories.append(relative)
        elif path.is_file() and relative not in exclude:
            digest, size = hashlib.sha256(), 0
            with path.open("rb") as stream:
                while chunk := stream.read(1024 * 1024):
                    size += len(chunk)
                    if size > 64 * 1024 * 1024:
                        raise ValueError("FIXTURE_CHANGED")
                    digest.update(chunk)
            files[relative] = digest.hexdigest()
        elif relative not in exclude:
            raise ValueError("FIXTURE_CHANGED")
    return {"files": files, "directories": directories}


def require_inventory(root, expected, *, exclude=()):
    if fixture_inventory(root, exclude=exclude) != expected:
        raise ValueError("FIXTURE_CHANGED")


def make_ci_catalogs_readable(catalogs):
    from app.replenishment.artifacts import _checked

    validate_profile("synthetic-only", None)
    if catalogs != OUTPUT / "catalogs":
        raise ValueError("OUTPUT_INVALID")
    root = _checked(catalogs)
    if not root.is_dir():
        raise ValueError("OUTPUT_INVALID")
    paths = [root, *root.rglob("*")]
    if len(paths) > 5000:
        raise ValueError("OUTPUT_INVALID")
    permissions = []
    for path in paths:
        checked = _checked(path)
        if not checked.is_relative_to(root):
            raise ValueError("OUTPUT_INVALID")
        if checked.is_dir():
            permissions.append((checked, 0o755))
        elif checked.is_file():
            permissions.append((checked, 0o644))
        else:
            raise ValueError("OUTPUT_INVALID")
    for path, mode in permissions:
        os.chmod(path, mode)


def prepare(research_run, *, profile="local"):
    from app.analytics.export import canonical_json
    from app.replenishment.artifacts import _checked, publish_failure, verify_public_projection
    from tests.prepare_forecasting_e2e import prepare as prepare_forecast
    from tests.replenishment_helpers import operational_context

    validate_profile(profile, research_run)
    checked_workspace(profile)
    research = None
    if profile == "local":
        research = _checked(Path(research_run))
        research_root = _checked(RESEARCH_CATALOG)
        if research.parent != research_root or research == research_root:
            raise ValueError("RESEARCH_INPUT_INVALID")
        manifest = verify_public_projection(research)
        if (
            manifest["mode"],
            manifest["dataset_class"],
            manifest["target"],
            manifest["reporting_scope"],
        ) != ("research", "research", "reported_daily_unit_sales", "company_aggregate"):
            raise ValueError("RESEARCH_INPUT_INVALID")
        if (
            manifest["forecast_run_id"]
            != "frv1-398a6c1c260e5277a15b647d3f383ef2bc5458978386dd05ccf88eee527c7b82"
        ):
            raise ValueError("RESEARCH_INPUT_INVALID")

    for path in (OUTPUT, FORECAST, BUNDLES):
        path.mkdir(parents=True, exist_ok=False)
        (path / "owner.txt").write_bytes(OWNER)
    bundle, forecast, auth, config = operational_context(
        FORECAST, bundle_root=BUNDLES / "bundles", product_id=2, warehouse_id=2
    )
    if auth.expected_fixture_binding != (2, 2, "unit") or auth.dataset_class != "fixture":
        raise ValueError("FIXTURE_INVALID")
    config_path, auth_path = OUTPUT / "config.json", OUTPUT / "authorization.json"
    config_path.write_bytes(canonical_json(config.model_dump(mode="json")))
    auth_path.write_bytes(canonical_json(auth.model_dump(mode="json")))
    common = (
        "--forecast-dir",
        forecast,
        "--bundle",
        bundle,
        "--config",
        config_path,
        "--authorization",
        auth_path,
    )
    result = run_cli(
        "app.replenishment.cli", "run", *common, "--output-root", OUTPUT / "runs", "--allow-fixture"
    )
    run_id = result["run_id"]
    if not isinstance(run_id, str) or re.fullmatch(r"rrv1-[0-9a-f]{64}", run_id) is None:
        raise ValueError("FIXTURE_INVALID")
    run_dir = OUTPUT / "runs" / run_id
    verified = run_cli(
        "app.replenishment.cli",
        "verify",
        "--run-dir",
        run_dir,
        "--authorization",
        auth_path,
        "--allow-fixture",
    )
    if verified != {"run_id": run_id, "status": "verified"}:
        raise ValueError("FIXTURE_INVALID")
    reconciled = run_cli("tests.reconcile_replenishment_run", "--run-dir", run_dir, *common)
    if reconciled != {"status": "reconciled", "cases": 36, "days": 6408}:
        raise ValueError("FIXTURE_INVALID")
    catalogs = OUTPUT / "catalogs"
    valid = catalogs / "valid"
    published = run_cli(
        "app.replenishment.cli",
        "publish",
        "--run-dir",
        run_dir,
        "--authorization",
        auth_path,
        "--catalog-root",
        valid,
        "--allow-fixture",
    )
    if published != {"run_id": run_id, "status": "published"}:
        raise ValueError("FIXTURE_INVALID")
    fixture = verify_public_projection(valid / "operational" / run_id)
    if (
        fixture["dataset_class"] != "fixture"
        or fixture["binding"]["product_id"] != 2
        or fixture["binding"]["warehouse_id"] != 2
        or fixture["binding"]["unit"] != "unit"
    ):
        raise ValueError("FIXTURE_INVALID")
    if research is not None:
        destination = valid / "research" / research.name
        destination.parent.mkdir(parents=True, exist_ok=False)
        shutil.copytree(research, destination, symlinks=False)
        if verify_public_projection(destination) != manifest:
            raise ValueError("RESEARCH_INPUT_INVALID")
    (catalogs / "unavailable").mkdir(parents=True, exist_ok=False)
    missing = config.model_copy(
        update={"costs": config.costs.model_copy(update={"ordering_cost": None})}
    )
    publish_failure(missing, auth, catalogs / "failed", "ORDERING_COST_MISSING")
    stale = config.model_copy(update={"evaluation_end": date(2023, 2, 1)})
    publish_failure(stale, auth, catalogs / "stale", "FORECAST_STALE")
    for name in ("corrupt", "unsupported"):
        target = catalogs / name / "operational" / run_id
        target.parent.mkdir(parents=True, exist_ok=False)
        shutil.copytree(valid / "operational" / run_id, target, symlinks=False)
        path = target / "public-manifest.json"
        negative = json.loads(path.read_bytes())
        if name == "corrupt":
            negative["projection_sha256"] = "0" * 64
        else:
            negative["schema_version"] = "replenishment-public-run/999"
        path.write_bytes(canonical_json(negative))
    forecast_scenarios = prepare_forecast(LEGACY_FORECAST, add_ratio=True, add_failed_valid=True)
    if profile == "synthetic-only":
        make_ci_catalogs_readable(catalogs)
    receipt = {
        "schema_version": "m7-e2e-fixture/1",
        "status": "verified",
        "fixture_run_id": run_id,
        "research_run_id": research.name if research is not None else None,
        "fixture_manifest_sha256": hashlib.sha256(
            (valid / "operational" / run_id / "public-manifest.json").read_bytes()
        ).hexdigest(),
        "forecast_scenarios": forecast_scenarios["scenarios"],
        "binding": {"product_id": 2, "warehouse_id": 2, "unit": "unit"},
        "inventories": {
            "output": fixture_inventory(OUTPUT, exclude=("fixture-receipt.json",)),
            "forecast": fixture_inventory(FORECAST),
            "bundles": fixture_inventory(BUNDLES),
            "legacy_forecast": fixture_inventory(LEGACY_FORECAST),
        },
    }
    if profile == "synthetic-only":
        receipt["profile"] = profile
    with (OUTPUT / "fixture-receipt.json").open("xb") as stream:
        stream.write(canonical_json(receipt))
        stream.flush()
        os.fsync(stream.fileno())
    return verify_existing(profile=profile)


def verify_existing(*, profile="local"):
    from app.analytics.export import canonical_json
    from app.replenishment.artifacts import _checked, verify_public_projection, verify_run
    from app.replenishment.repository import ReplenishmentRepository, UnsupportedSchema
    from app.replenishment.schemas import InputAuthorization, StudyConfig
    from tests.prepare_forecasting_e2e import prepare as prepare_forecast

    validate_profile(profile, None)
    receipt_path = OUTPUT / "fixture-receipt.json"
    if not receipt_path.is_file() or receipt_path.is_symlink():
        raise ValueError("FIXTURE_INCOMPLETE")
    raw = _checked(receipt_path).read_bytes()
    if len(raw) > 1024 * 1024:
        raise ValueError("FIXTURE_CHANGED")
    receipt = json.loads(raw)
    if (
        canonical_json(receipt) != raw
        or set(receipt)
        != {
            "schema_version",
            "status",
            "fixture_run_id",
            "research_run_id",
            "fixture_manifest_sha256",
            "forecast_scenarios",
            "binding",
            "inventories",
        }
        | ({"profile"} if profile == "synthetic-only" else set())
        or receipt["schema_version"] != "m7-e2e-fixture/1"
        or receipt["status"] != "verified"
        or (profile == "synthetic-only" and receipt["profile"] != profile)
    ):
        raise ValueError("FIXTURE_CHANGED")
    inventories = receipt["inventories"]
    if set(inventories) != {"output", "forecast", "bundles", "legacy_forecast"}:
        raise ValueError("FIXTURE_CHANGED")
    for root, name in (
        (OUTPUT, "output"),
        (FORECAST, "forecast"),
        (BUNDLES, "bundles"),
        (LEGACY_FORECAST, "legacy_forecast"),
    ):
        require_inventory(
            root, inventories[name], exclude=("fixture-receipt.json",) if root == OUTPUT else ()
        )
    for root in (OUTPUT, FORECAST, BUNDLES):
        if _checked(root / "owner.txt").read_bytes() != OWNER:
            raise ValueError("FIXTURE_CHANGED")
    run_id, research_id = receipt["fixture_run_id"], receipt["research_run_id"]
    if (
        not isinstance(run_id, str)
        or re.fullmatch(r"rrv1-[0-9a-f]{64}", run_id) is None
        or (
            profile == "local"
            and (
                not isinstance(research_id, str)
                or re.fullmatch(r"rrv1-[0-9a-f]{64}", research_id) is None
            )
        )
        or (profile == "synthetic-only" and research_id is not None)
    ):
        raise ValueError("FIXTURE_CHANGED")
    if receipt["binding"] != {"product_id": 2, "warehouse_id": 2, "unit": "unit"}:
        raise ValueError("FIXTURE_CHANGED")
    auth_path, config_path = OUTPUT / "authorization.json", OUTPUT / "config.json"
    auth = InputAuthorization.model_validate_json(_checked(auth_path).read_bytes())
    config = StudyConfig.model_validate_json(_checked(config_path).read_bytes())
    if (
        (auth.mode, auth.dataset_class, auth.allow_fixture, auth.expected_fixture_binding)
        != ("operational", "fixture", True, (2, 2, "unit"))
        or (config.mode, config.dataset_class, config.forecast_run_id)
        != ("operational", "fixture", auth.forecast_run_id)
        or not auth.bundle_path.is_relative_to(BUNDLES / "bundles")
        or not auth.forecast_dir.is_relative_to(FORECAST)
    ):
        raise ValueError("FIXTURE_CHANGED")
    run = OUTPUT / "runs" / run_id
    if verify_run(run, auth).run_id != run_id:
        raise ValueError("FIXTURE_CHANGED")
    catalog = OUTPUT / "catalogs"
    public_path = catalog / "valid" / "operational" / run_id
    public = verify_public_projection(public_path)
    if (
        public["dataset_class"] != "fixture"
        or public["binding"]["product_id"] != 2
        or public["binding"]["warehouse_id"] != 2
        or public["binding"]["unit"] != "unit"
        or hashlib.sha256(_checked(public_path / "public-manifest.json").read_bytes()).hexdigest()
        != receipt["fixture_manifest_sha256"]
    ):
        raise ValueError("FIXTURE_CHANGED")
    if profile == "local":
        research = _checked(RESEARCH_CATALOG / research_id)
        copied = catalog / "valid" / "research" / research_id
        if verify_public_projection(research) != verify_public_projection(copied):
            raise ValueError("FIXTURE_CHANGED")
        for name in (
            "public-manifest.json",
            "calibration.json",
            "summaries.json",
            "days.jsonl",
            "orders.jsonl",
        ):
            if _checked(research / name).read_bytes() != _checked(copied / name).read_bytes():
                raise ValueError("FIXTURE_CHANGED")
    elif (catalog / "valid" / "research").exists():
        raise ValueError("FIXTURE_CHANGED")
    common = (
        "--forecast-dir",
        auth.forecast_dir,
        "--bundle",
        auth.bundle_path,
        "--config",
        config_path,
        "--authorization",
        auth_path,
    )
    if run_cli("tests.reconcile_replenishment_run", "--run-dir", run, *common) != {
        "status": "reconciled",
        "cases": 36,
        "days": 6408,
    }:
        raise ValueError("FIXTURE_CHANGED")
    if ReplenishmentRepository(catalog / "unavailable", allow_fixture=True).index("operational"):
        raise ValueError("FIXTURE_CHANGED")
    for name, reason in (("failed", "ORDERING_COST_MISSING"), ("stale", "FORECAST_STALE")):
        failure = ReplenishmentRepository(catalog / name, allow_fixture=True).latest_failure(
            "operational"
        )
        if failure is None or failure.reason_code != reason:
            raise ValueError("FIXTURE_CHANGED")
    for name, expected in (("corrupt", ValueError), ("unsupported", UnsupportedSchema)):
        try:
            ReplenishmentRepository(catalog / name, allow_fixture=True).index("operational")
        except expected:
            pass
        else:
            raise ValueError("FIXTURE_CHANGED")
    expected_forecast_scenarios = {
        "valid",
        "unavailable",
        "corrupt",
        "unsupported",
        "ratio",
        "failed-valid",
    }
    if (
        set(receipt["forecast_scenarios"]) != expected_forecast_scenarios
        or not (LEGACY_FORECAST / "ratio").is_dir()
        or not (LEGACY_FORECAST / "failed-valid").is_dir()
    ):
        raise ValueError("FIXTURE_CHANGED")
    forecast_info = prepare_forecast(LEGACY_FORECAST, add_ratio=True, add_failed_valid=True)
    if forecast_info["scenarios"] != receipt["forecast_scenarios"]:
        raise ValueError("FIXTURE_CHANGED")
    return {
        "status": "verified",
        "fixture_run_id": run_id,
        "research_run_id": research_id,
        "receipt": str(receipt_path),
        "catalogs": str(catalog),
    }


def seed_owned_database():
    from sqlalchemy import create_engine, func, select, text
    from sqlalchemy.engine import make_url
    from sqlalchemy.orm import Session

    from app.models import (
        Product,
        PurchaseRequest,
        User,
        UserRole,
        Warehouse,
    )
    from app.models.domain import PurchaseRequestStatus

    if os.environ.get("M7_E2E_SEED_RELEASE") != "1" or os.environ.get("APP_ENV") != "integration":
        raise ValueError("SEED_NOT_RELEASED")
    url = make_url(os.environ.get("DATABASE_URL", ""))
    if (url.drivername, url.host, url.port, url.database, url.username) not in {
        ("postgresql+psycopg", "db", None, "sw_m7_replenishment_e2e", "sw_m7_replenishment_e2e"),
        ("postgresql+psycopg", "db", 5432, "sw_m7_replenishment_e2e", "sw_m7_replenishment_e2e"),
    } or url.query:
        raise ValueError("DATABASE_INVALID")
    email = os.environ.get("SEED_CLIENT_EMAIL", "")
    if not email:
        raise ValueError("SEED_CLIENT_MISSING")
    engine = create_engine(url)
    try:
        with Session(engine) as session, session.begin():
            session.execute(text("SET LOCAL lock_timeout = '3s'"))
            session.execute(text("SET LOCAL statement_timeout = '15s'"))
            identity = session.execute(
                text(
                    "select current_database(), current_user, pg_get_userbyid(datdba) "
                    "from pg_database where datname=current_database()"
                )
            ).one()
            if tuple(identity) != (url.database, url.username, url.username):
                raise ValueError("DATABASE_INVALID")
            session.execute(text("LOCK TABLE stocks, outbounds, transactions IN SHARE MODE"))

            def snapshots():
                result = {}
                for table in ("stocks", "outbounds", "transactions"):
                    rows = session.execute(
                        text(f"SELECT CAST(row_to_json(t) AS text) FROM {table} t ORDER BY id")
                    ).scalars()
                    digest = hashlib.sha256()
                    count = 0
                    for row in rows:
                        digest.update(row.encode("utf8") + b"\n")
                        count += 1
                    result[table] = {"count": count, "sha256": digest.hexdigest()}
                return result

            before = snapshots()
            if session.scalar(select(func.count()).select_from(Product)) != 1:
                raise ValueError("SEED_CONFLICT")
            if session.scalar(select(func.count()).select_from(Warehouse)) != 1:
                raise ValueError("SEED_CONFLICT")
            demo = session.get(Product, 1)
            warehouse = session.get(Warehouse, 1)
            client = session.scalar(select(User).where(User.email == email))
            if (
                demo is None
                or demo.sku != "DEMO-001"
                or demo.unit != "each"
                or warehouse is None
                or warehouse.code != "HCM-01"
                or client is None
                or client.role != UserRole.CLIENT
            ):
                raise ValueError("SEED_CONFLICT")
            product = Product(
                sku="M7-E2E-SYNTHETIC",
                name="M7-E2E-SYNTHETIC",
                category_id=demo.category_id,
                unit="unit",
                reorder_level=0,
            )
            destination = Warehouse(
                code="M7-E2E-SYNTHETIC",
                name="M7-E2E-SYNTHETIC",
                address="Synthetic isolated fixture",
            )
            session.add_all((product, destination))
            session.flush()
            if (product.id, destination.id) != (2, 2):
                raise ValueError("SEED_CONFLICT")
            legacy_product = Product(
                sku="M4-LEGACY-M7",
                name="M4-LEGACY-M7",
                category_id=demo.category_id,
                unit="each",
                reorder_level=0,
            )
            session.add(legacy_product)
            session.flush()
            request = PurchaseRequest(
                request_number="M4-LEGACY-M7",
                product_id=legacy_product.id,
                warehouse_id=destination.id,
                quantity=1,
                status=PurchaseRequestStatus.PENDING,
                requested_by_id=client.id,
            )
            session.add(request)
            session.flush()
            if before != snapshots():
                raise ValueError("SEED_EFFECT_MISMATCH")
            result = {
                "legacy_request_id": request.id,
                "binding": [2, 2, "unit"],
                "protected_tables": before,
            }
        return result
    finally:
        engine.dispose()


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--seed-db", action="store_true")
    parser.add_argument("--research-run")
    args = parser.parse_args(argv)
    try:
        if args.seed_db:
            if args.execute or args.research_run:
                raise ValueError("INVALID_ARGUMENTS")
            print(json.dumps(seed_owned_database()))
            return 0
        checked_workspace()
        if not args.execute:
            print(
                json.dumps(
                    {
                        "status": "preflight",
                        "output": str(OUTPUT),
                        "fixture_binding": [2, 2, "unit"],
                    }
                )
            )
            return 0
        if os.environ.get("M7_E2E_PREPARE_RELEASE") != "1" or not args.research_run:
            raise ValueError("EXECUTION_NOT_RELEASED")
        print(json.dumps(prepare(args.research_run)))
        return 0
    except Exception:
        print('{"code":"E2E_FIXTURE_PREPARATION_FAILED"}', file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
