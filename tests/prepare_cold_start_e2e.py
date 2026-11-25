"""Generate an isolated, synthetic M8 catalog; never read warehouse records.

The caller owns the new output directory and its parent. Only catalogs/ may be
mounted by the isolated API; temporary M5 bundles are removed before return.
"""

import argparse
import json
import os
import shutil
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.analytics.ingestion import checked_path
from app.cold_start.benchmark import evaluate_cold_start
from app.cold_start.catalog import entries, publish_failure, publish_report, read_report
from app.cold_start.dataset import load_fixture_dataset
from tests.cold_start_helpers import fixture_config


def prepare(output_root: Path):
    target = checked_path(output_root, directory=True, must_exist=False)
    checked_path(target.parent, directory=True)
    if target.exists() or target.is_symlink():
        raise ValueError("OUTPUT_CONFLICT")
    target.mkdir()
    os.chmod(target, 0o755)
    catalogs = target / "catalogs"
    catalogs.mkdir()
    os.chmod(catalogs, 0o755)
    now = datetime.now(UTC)
    with tempfile.TemporaryDirectory(prefix="sw-m8-synthetic-") as temporary:
        work = Path(temporary)
        low, high, mixed = (work / name for name in ("low", "high", "mixed"))
        for folder in (low, high, mixed):
            folder.mkdir()
        low_cfg = fixture_config(low, count=8, quantity=2)
        high_cfg = fixture_config(high, count=8, quantity=8)
        chosen = []
        for i in range(8):
            high_group = i in (3, 4, 5, 7)
            source_root, source_cfg = (high, high_cfg) if high_group else (low, low_cfg)
            item = source_cfg.skus[i]
            shutil.copytree(source_root / item.bundle_path, mixed / item.bundle_path)
            snapshot = item.snapshot.model_copy(
                update={"supplier": "synthetic-high" if high_group else "synthetic-low"}
            )
            chosen.append(item.model_copy(update={"snapshot": snapshot}))
        config = low_cfg.model_copy(update={"skus": tuple(chosen), "created_at": now})
        dataset = load_fixture_dataset(config, mixed)
        report = evaluate_cold_start(dataset)
        if report.selected_k != 2 or report.selection_reason != "validation_common_horizon_7_mae":
            raise ValueError("FIXTURE_CLUSTER_INVALID")
        if not report.predictions or any(
            row.prediction != 8 * row.horizon or row.baseline != 5 * row.horizon
            for row in report.predictions
        ):
            raise ValueError("FIXTURE_COMPARISON_INVALID")
        ready = catalogs / "ready"
        ready_id = publish_report(report, ready)
        empty = catalogs / "empty"
        empty.mkdir()
        failed = catalogs / "failed"
        publish_failure(failed, "EVALUATION_FAILED", now)
        stale = catalogs / "stale"
        stale_id = publish_report(
            report.model_copy(update={"created_at": now - timedelta(days=8)}), stale
        )
        if (
            read_report(ready, ready_id).selected_k != 2
            or len(entries(empty)) != 0
            or len(entries(failed)) != 1
            or len(entries(stale)) != 1
        ):
            raise ValueError("CATALOG_INVALID")
    for directory in (ready, empty, failed, stale):
        os.chmod(directory, 0o755)
        for path in directory.iterdir():
            if not path.is_file() or path.is_symlink():
                raise ValueError("CATALOG_INVALID")
            os.chmod(path, 0o644)
    return {
        "ready_run_id": ready_id,
        "stale_run_id": stale_id,
        "selected_k": 2,
        "horizon_1_prediction": 8,
        "horizon_1_comparison": 5,
        "horizon_7_prediction": 56,
        "horizon_7_comparison": 35,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    try:
        print(json.dumps(prepare(args.output_root), sort_keys=True))
    except Exception:
        print("FIXTURE_PREPARATION_FAILED")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
