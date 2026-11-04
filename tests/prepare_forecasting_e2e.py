"""Create isolated, synthetic public catalog scenarios without fitting models.

Only the exact worktree-owned e2e-catalog is writable. Existing trees are checked
byte-for-byte and never overwritten. Select a scenario as the read-only API mount.
"""

import argparse
import hashlib
import json
import stat
from datetime import date, timedelta
from pathlib import Path

from app.analytics.export import canonical_json
from app.forecasting.repository import FailureReceipt, verify_catalog_run

OWNER = b"M6_FORECAST_FIXTURES_V1\n"
RESEARCH_ID = "frv1-" + "1" * 64
OPERATIONAL_ID = "frv1-" + "2" * 64
RATIO_ID = "frv1-" + "3" * 64
ALGORITHMS = ("persistence", "seasonal_naive", "xgboost")
ROOT = Path(__file__).resolve().parents[1] / "artifacts" / "forecasting" / "e2e-catalog"


def safe_path(path):
    path = Path(path)
    if ".." in path.parts or str(path).startswith(("\\\\", "//")):
        raise ValueError("unsafe path")
    path = path.absolute()
    for part in (*reversed(path.parents), path):
        if part.exists() or part.is_symlink():
            info = part.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
                raise ValueError("reparse path")
    return path


def digest(body):
    return hashlib.sha256(body).hexdigest()


def protocol(operational):
    return dict(
        schema_version="forecast-protocol/1",
        partitions=[
            dict(name="train", start="2020-01-01", end="2021-01-01"),
            dict(name="validation", start="2021-01-01", end="2022-01-01"),
            dict(name="final_holdout", start="2022-01-01", end="2023-01-01"),
        ],
        horizons=[1, 7],
        history_days=28,
        imputation="none",
        train_information_cutoff="2020-12-31T00:00:00Z" if operational else None,
        selection_information_cutoff="2021-12-31T00:00:00Z" if operational else None,
        refit_information_cutoff="2021-12-31T00:00:00Z" if operational else None,
    )


def fixture(operational, positive=False):
    version = ("ddv1-" if operational else "ddv2-") + ("2" if operational else "1") * 64
    run_id = OPERATIONAL_ID if operational else RATIO_ID if positive else RESEARCH_ID
    origins = [date(2022, 3, 1)] if operational else [date(2022, 1, d) for d in (1, 2, 3)]
    rows = []
    for horizon in (1, 7):
        for algorithm in ALGORITHMS:
            for origin in origins:
                for lead in range(1, horizon + 1):
                    rows.append(
                        dict(
                            series_key="fixture-series",
                            origin=origin.isoformat(),
                            target_date=(origin + timedelta(days=lead)).isoformat(),
                            lead=lead,
                            horizon=horizon,
                            algorithm=algorithm,
                            prediction=0 if algorithm == "persistence" else 1,
                            actual=None if operational else 2 if positive else 0,
                            unit="each",
                        )
                    )
    rows.sort(
        key=lambda row: (
            row["horizon"],
            row["algorithm"],
            row["series_key"],
            row["origin"],
            row["lead"],
        )
    )
    body = b"".join(canonical_json(row) for row in rows)
    files = {"predictions.jsonl": body}
    binding = None
    if operational:
        binding = dict(
            product_id=1,
            warehouse_id=1,
            product_key="fixture-product",
            warehouse_key="fixture-warehouse",
            unit="each",
            data_version=version,
            approved_at="2020-01-01T00:00:00Z",
            available_at="2020-01-01T00:00:00Z",
            binding_sha256="3" * 64,
        )
        files["binding.json"] = canonical_json(binding)
    else:
        metrics = {}
        for horizon in (1, 7):
            for algorithm in ALGORITHMS:
                pred = 0 if algorithm == "persistence" else 1
                count = len(origins) * horizon
                error = 2 - pred if positive else pred
                wape = error / 2 if positive else None
                metrics[f"{algorithm}:{horizon}"] = dict(
                    count=count,
                    origin_count=len(origins),
                    mae=float(error),
                    wape=wape,
                    origin_total_mae=float(error * horizon),
                    reason=None,
                    wape_reason=None if positive else "ZERO_ACTUAL_TOTAL",
                    per_series={"fixture-series": [count, float(error), wape]},
                )
        files["metrics.json"] = canonical_json(metrics)
    cutoff = "2021-12-31T00:00:00Z" if operational else "2026-01-01T00:00:00Z"
    manifest = dict(
        schema_version="forecast-public-run/1",
        run_id=run_id,
        source_manifest_sha256="4" * 64,
        kind="forecast" if operational else "evaluation",
        mode="operational" if operational else "research",
        dataset_class="fixture",
        data_version=version,
        target="gross_fulfilled_units" if operational else "reported_daily_unit_sales",
        reporting_scope="warehouse" if operational else "company_aggregate",
        unit="each",
        protocol=protocol(operational),
        knowledge_time_mode="historical_as_of" if operational else "retrospective_final_vintage",
        business_timezone="UTC" if operational else None,
        trained_through="2021-12-01",
        training_information_cutoff=cutoff,
        knowledge_bound=cutoff,
        admission_cutoff=cutoff,
        origin_start=min(origins).isoformat(),
        origin_end=max(origins).isoformat(),
        horizons=[1, 7],
        generated_at="2026-01-01T00:00:00Z",
        limitations=["REPORTED_SALES_ONLY"] if not operational else [],
        row_count=len(rows),
        binding=binding,
        artifacts={name: digest(content) for name, content in files.items()},
    )
    files["public-manifest.json"] = canonical_json(
        {**manifest, "projection_sha256": digest(canonical_json(manifest))}
    )
    return run_id, files


def prepare(path, add_ratio=False, add_failed_valid=False):
    path = safe_path(path)
    if path != safe_path(ROOT):
        raise ValueError("unapproved catalog root")
    expected = {"owner.txt": OWNER}
    for scenario in ("valid", "unavailable", "failed", "corrupt", "unsupported"):
        expected[f"{scenario}/owner.txt"] = OWNER
    for operational in (False, True):
        run_id, files = fixture(operational)
        mode = "operational" if operational else "research"
        for name, content in files.items():
            expected[f"valid/{mode}/{run_id}/{name}"] = content
    failure = dict(
        state="failed",
        error_code="FIT_FAILED",
        mode="operational",
        dataset_class="fixture",
        reporting_scope="warehouse",
        config_sha256="5" * 64,
        created_at="2026-01-01T00:00:00Z",
        attempt_id="6" * 32,
    )
    expected[f"failed/operational/failures/{failure['attempt_id']}.json"] = canonical_json(failure)
    for scenario in ("corrupt", "unsupported"):
        run_id, files = fixture(False)
        for name, content in files.items():
            if name == "public-manifest.json":
                manifest = json.loads(content)
                if scenario == "unsupported":
                    manifest["schema_version"] = "forecast-public-run/999"
                else:
                    manifest["projection_sha256"] = "0" * 64
                content = canonical_json(manifest)
            expected[f"{scenario}/research/{run_id}/{name}"] = content
    ratio_files = {"ratio/owner.txt": OWNER}
    ratio_id, ratio_projection = fixture(False, positive=True)
    for name, content in ratio_projection.items():
        ratio_files[f"ratio/research/{ratio_id}/{name}"] = content
    failed_valid = {
        "failed-valid/owner.txt": OWNER,
        f"failed-valid/operational/failures/{failure['attempt_id']}.json": canonical_json(
            FailureReceipt.model_validate_json(canonical_json(failure))
        ),
    }
    ratio_exists = (path / "ratio").exists()
    failed_valid_exists = (path / "failed-valid").exists()
    if ratio_exists:
        expected.update(ratio_files)
    if failed_valid_exists:
        expected.update(failed_valid)
    if path.exists():
        if not path.is_dir() or safe_path(path / "owner.txt").read_bytes() != OWNER:
            raise ValueError("existing root not owned")
        expected_dirs = {
            parent.as_posix()
            for name in expected
            for parent in Path(name).parents
            if parent != Path(".")
        }
        entries = list(path.rglob("*"))
        for entry in entries:
            safe_path(entry)
        actual = {p.relative_to(path).as_posix() for p in entries if p.is_file()}
        directories = {p.relative_to(path).as_posix() for p in entries if p.is_dir()}
        if (
            actual != set(expected)
            or directories != expected_dirs
            or any(safe_path(path / n).read_bytes() != b for n, b in expected.items())
        ):
            raise ValueError("existing fixture differs")
    else:
        path.mkdir(parents=True, exist_ok=False)
        for name, content in expected.items():
            destination = path / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(content)
    if add_ratio and not ratio_exists:
        for name, content in ratio_files.items():
            destination = safe_path(path / name)
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open("xb") as output:
                output.write(content)
        expected.update(ratio_files)
    if add_failed_valid and not failed_valid_exists:
        for name, content in failed_valid.items():
            destination = safe_path(path / name)
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open("xb") as output:
                output.write(content)
        expected.update(failed_valid)
    for run_id, mode in ((RESEARCH_ID, "research"), (OPERATIONAL_ID, "operational")):
        run = verify_catalog_run(path / "valid" / mode / run_id, allow_fixture=True)
        if run.manifest.dataset_class != "fixture":
            raise ValueError("fixture class required")
    if ratio_exists or add_ratio:
        verify_catalog_run(path / "ratio" / "research" / RATIO_ID, allow_fixture=True)
    return {
        "status": "verified",
        "research_id": RESEARCH_ID,
        "operational_id": OPERATIONAL_ID,
        "scenarios": ["valid", "unavailable", "corrupt", "unsupported"]
        + (["ratio"] if ratio_exists or add_ratio else [])
        + (["failed-valid"] if failed_valid_exists or add_failed_valid else []),
        "negative_legacy": ["failed"],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog-root", required=True)
    parser.add_argument("--add-ratio", action="store_true")
    parser.add_argument("--add-failed-valid", action="store_true")
    args = parser.parse_args()
    try:
        print(
            json.dumps(
                prepare(args.catalog_root, args.add_ratio, args.add_failed_valid), sort_keys=True
            )
        )
    except Exception:
        print('{"status":"fixture_preparation_failed"}')
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
