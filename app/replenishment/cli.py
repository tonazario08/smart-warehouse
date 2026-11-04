"""Offline replenishment commands with bounded, sanitized diagnostics."""

import argparse
import json
import sys
from pathlib import Path


class _ParseError(Exception):
    pass


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise _ParseError


def _parser():
    parser = _Parser(prog="python -m app.replenishment.cli")
    commands = parser.add_subparsers(dest="command", required=True, parser_class=_Parser)
    run = commands.add_parser("run")
    for name in ("forecast-dir", "bundle", "config", "authorization", "output-root"):
        run.add_argument("--" + name, required=True)
    verify = commands.add_parser("verify")
    for name in ("run-dir", "authorization"):
        verify.add_argument("--" + name, required=True)
    publish = commands.add_parser("publish")
    for name in ("run-dir", "authorization", "catalog-root"):
        publish.add_argument("--" + name, required=True)
    for command in (run, verify, publish):
        command.add_argument("--allow-fixture", action="store_true")
    return parser


def main(argv=None):
    try:
        args = _parser().parse_args(argv)
    except _ParseError:
        print('{"code":"INPUT_SCHEMA"}', file=sys.stderr)
        return 2
    try:
        from app.replenishment.artifacts import (
            _owned,
            _read,
            publish_catalog,
            publish_run,
            verify_run,
        )
        from app.replenishment.calibration import calibrate
        from app.replenishment.inputs import load_inputs, validate_forecast_coverage
        from app.replenishment.schemas import InputAuthorization, StudyConfig
        from app.replenishment.simulation import simulate

        authorization = InputAuthorization.model_validate_json(
            _read(_owned(Path(args.authorization)))
        )
        if authorization.dataset_class == "fixture" and not args.allow_fixture:
            print('{"code":"INPUT_UNADMITTED"}', file=sys.stderr)
            return 3
        if args.command == "run":
            config = StudyConfig.model_validate_json(_read(_owned(Path(args.config))))
            inputs = load_inputs(Path(args.forecast_dir), Path(args.bundle), config, authorization)
            validate_forecast_coverage(
                inputs.forecast.rows, config.evaluation_start, config.evaluation_end
            )
            result = simulate(inputs, calibrate(inputs, config), config)
            published = publish_run(inputs, config, result, authorization, Path(args.output_root))
            output = {"run_id": published.run_id, "reused": published.reused}
        elif args.command == "verify":
            verified = verify_run(Path(args.run_dir), authorization)
            output = {"run_id": verified.run_id, "status": "verified"}
        else:
            path = publish_catalog(Path(args.run_dir), authorization, Path(args.catalog_root))
            output = {"run_id": path.name, "status": "published"}
        print(json.dumps(output, separators=(",", ":")))
        return 0
    except OSError:
        print('{"code":"IO_UNAVAILABLE"}', file=sys.stderr)
        return 5
    except ValueError as error:
        safe = {
            "ORDERING_COST_MISSING",
            "ORDERING_COST_ZERO",
            "HOLDING_COST_MISSING",
            "HOLDING_COST_ZERO",
            "UNSUPPORTED_INVENTORY_STATE",
            "CALENDAR_UNAVAILABLE",
            "NO_EVALUATION_WINDOWS",
            "FORECAST_STALE",
        }
        code = (
            "INSUFFICIENT_CALIBRATION"
            if str(error) == "insufficient calibration"
            else str(error)
            if str(error) in safe
            else "INPUT_INVALID"
        )
        print(json.dumps({"code": code}, separators=(",", ":")), file=sys.stderr)
        return 2
    except Exception:
        print('{"code":"INPUT_INVALID"}', file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
