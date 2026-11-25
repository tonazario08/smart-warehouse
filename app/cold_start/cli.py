"""Run an explicitly opted-in fixture benchmark and publish its safe projection."""

import argparse
from datetime import UTC, datetime
from pathlib import Path

from app.analytics.export import _bounded_read
from app.analytics.ingestion import _decode_json, checked_path
from app.cold_start.benchmark import ColdStartUnavailable, evaluate_cold_start
from app.cold_start.catalog import publish_failure, publish_report
from app.cold_start.dataset import load_fixture_dataset
from app.cold_start.schemas import ColdStartConfig


def main(argv=None):
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    evaluate = sub.add_parser("evaluate")
    evaluate.add_argument("--config", required=True, type=Path)
    evaluate.add_argument("--input-root", required=True, type=Path)
    evaluate.add_argument("--output-root", required=True, type=Path)
    evaluate.add_argument("--allow-fixture", action="store_true")
    args = parser.parse_args(argv)
    if not args.allow_fixture:
        parser.error("fixture requires --allow-fixture")
    try:
        body = _bounded_read(checked_path(args.config), 256 * 1024)
        config = ColdStartConfig.model_validate(_decode_json(body.decode("utf-8")))
        report = evaluate_cold_start(load_fixture_dataset(config, args.input_root))
        print(publish_report(report, args.output_root))
        return 0
    except ColdStartUnavailable:
        try:
            publish_failure(args.output_root, "NO_ELIGIBLE_TRAINING_SNAPSHOTS", datetime.now(UTC))
        except Exception:
            print("EVALUATION_FAILED")
            return 1
        print("NO_ELIGIBLE_TRAINING_SNAPSHOTS")
        return 2
    except Exception:
        print("EVALUATION_FAILED")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
