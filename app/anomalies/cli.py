"""Offline fixture evaluation and authorized catalog import."""

import argparse
from pathlib import Path

from app.analytics.ingestion import _bounded_read, checked_path


def main(argv=None):
    parser = argparse.ArgumentParser(description="Offline synthetic anomaly evaluation and import")
    sub = parser.add_subparsers(dest="command", required=True)
    evaluate = sub.add_parser("evaluate", help="Publish a verified synthetic fixture catalog")
    evaluate.add_argument("--config", required=True, type=Path)
    evaluate.add_argument("--input-root", required=True, type=Path)
    evaluate.add_argument("--output-root", required=True, type=Path)
    evaluate.add_argument("--allow-fixture", action="store_true")
    importer = sub.add_parser(
        "import-run", help="Import a verified fixture run into the configured database"
    )
    importer.add_argument("--run-id", required=True)
    importer.add_argument("--catalog-root", required=True, type=Path)
    importer.add_argument(
        "--actor-id", required=True, type=int, help="Existing active admin or warehouse user ID"
    )
    importer.add_argument("--allow-fixture", action="store_true")
    args = parser.parse_args(argv)
    if not args.allow_fixture:
        parser.error("fixture requires --allow-fixture")
    try:
        if args.command == "evaluate":
            from app.anomalies.catalog import publish_run
            from app.anomalies.dataset import load_anomaly_dataset
            from app.anomalies.features import build_feature_snapshot
            from app.anomalies.schemas import AnomalyConfig
            from app.anomalies.scoring import fit_and_score

            config = AnomalyConfig.model_validate_json(
                _bounded_read(checked_path(args.config), 1024 * 1024)
            )
            result = fit_and_score(
                build_feature_snapshot(load_anomaly_dataset(config, args.input_root))
            )
            if result.state != "available":
                print(result.reason)
                return 2
            print(publish_run(result, args.output_root))
            return 0
        from sqlalchemy import create_engine
        from sqlalchemy.orm import Session

        from app.anomalies.catalog import verify_run
        from app.anomalies.service import AnomalyService
        from app.core.config import get_settings

        settings = get_settings()
        if settings.app_env not in ("test", "integration") or not settings.anomalies_allow_fixture:
            raise ValueError("fixture import disabled")
        verified = verify_run(args.catalog_root, args.run_id)
        engine = create_engine(settings.database_url)
        try:
            with Session(engine) as session, session.begin():
                result = AnomalyService(
                    session,
                    app_env=settings.app_env,
                    allow_fixture=settings.anomalies_allow_fixture,
                ).import_run(args.actor_id, verified)
            print(result.run_id)
        finally:
            engine.dispose()
        return 0
    except Exception:
        print("ANOMALY_OPERATION_FAILED")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
