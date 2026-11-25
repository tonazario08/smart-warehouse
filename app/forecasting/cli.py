"""Explicit, bounded offline forecasting commands."""

import argparse
import json
import os
import sys
from pathlib import Path


class _InputError(Exception):
    pass


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise _InputError


def _parser():
    parser = _Parser(prog="python -m app.forecasting.cli")
    commands = parser.add_subparsers(dest="command", required=True, parser_class=_Parser)
    tune = commands.add_parser("tune")
    for name in ("bundle", "config", "output-root"):
        tune.add_argument("--" + name, required=True)
    for name in ("evaluate", "forecast"):
        command = commands.add_parser(name)
        for field in ("bundle", "selection-dir", "output-root"):
            command.add_argument("--" + field, required=True)
        if name == "forecast":
            command.add_argument("--binding", required=True)
            command.add_argument("--origin", required=True)
    verify = commands.add_parser("verify")
    verify.add_argument("--run-dir", required=True)
    publish = commands.add_parser("publish")
    for field in ("run-dir", "catalog-root", "bundle", "selection-dir"):
        publish.add_argument("--" + field, required=True)
    failure = commands.add_parser("publish-failure")
    failure.add_argument("--attempt", required=True)
    failure.add_argument("--catalog-root", required=True)
    for command in (
        tune,
        commands.choices["evaluate"],
        commands.choices["forecast"],
        verify,
        publish,
        failure,
    ):
        command.add_argument("--allow-fixture", action="store_true")
    return parser


def _file(path, limit=1024 * 1024):
    from app.analytics.ingestion import _bounded_read
    from app.forecasting.artifacts import _checked, _owned_root

    candidate = _owned_root(Path(path))
    return _bounded_read(_checked(candidate), limit)


def _approved_bundle(path):
    from app.forecasting.artifacts import _checked

    configured = os.environ.get("FORECAST_APPROVED_BUNDLE_ROOT")
    if not configured:
        raise ValueError("approved bundle root required")
    root, candidate = Path(configured), Path(path)
    if not root.is_absolute() or not candidate.is_absolute():
        raise ValueError("absolute bundle paths required")
    root, candidate = _checked(root), _checked(candidate)
    if (
        not root.is_dir()
        or not candidate.is_dir()
        or candidate == root
        or not candidate.is_relative_to(root)
    ):
        raise ValueError("bundle outside approved root")
    return candidate


def main(argv=None):
    config = None
    phase = "input"
    try:
        args = _parser().parse_args(argv)
    except _InputError:
        print('{"code":"INPUT_SCHEMA"}', file=sys.stderr)
        return 2
    try:
        from app.analytics.ingestion import _decode_json
        from app.forecasting.artifacts import (
            publish_catalog,
            publish_failure,
            publish_run,
            publish_selection,
            verify_run,
            verify_selection,
        )
        from app.forecasting.dataset import FixtureNotAllowed, load_dataset
        from app.forecasting.evaluation import evaluate_holdout, forecast, tune
        from app.forecasting.schemas import ForecastConfig, OperationalBinding

        if args.command == "publish-failure":
            from app.forecasting.repository import FailureReceipt

            receipt = FailureReceipt.model_validate_json(_file(args.attempt, 4096))
            if receipt.dataset_class == "fixture" and not args.allow_fixture:
                raise FixtureNotAllowed("fixture requires opt-in")
            phase = "publication"
            path = publish_failure(Path(args.attempt), Path(args.catalog_root))
            print(json.dumps({"attempt_id": path.stem, "status": "published"}))
            return 0

        if args.command == "verify":
            run = verify_run(Path(args.run_dir))
            if run.manifest["config"]["dataset_class"] == "fixture" and not args.allow_fixture:
                raise FixtureNotAllowed("fixture requires opt-in")
            print(json.dumps({"run_id": run.run_id, "status": "verified"}))
            return 0
        if args.command == "tune":
            config = ForecastConfig.model_validate_json(_file(args.config))
        else:
            manifest = _decode_json(_file(str(Path(args.selection_dir) / "selection.json")))
            config = ForecastConfig.model_validate_json(json.dumps(manifest["config"]))
        bundle = _approved_bundle(args.bundle)
        dataset = load_dataset(bundle, config, allow_fixture=args.allow_fixture)
        if args.command == "tune":
            phase = "fitting"
            result = tune(dataset, config)
            phase = "publication"
            output = publish_selection(result, Path(args.output_root), dataset=dataset)
            print(json.dumps({"selection_id": output.selection_id, "reused": output.reused}))
        else:
            selected = verify_selection(Path(args.selection_dir), dataset=dataset)
            if args.command == "publish":
                verified = verify_run(Path(args.run_dir))
                phase = "publication"
                run_id = publish_catalog(
                    verified, Path(args.catalog_root), dataset=dataset, selection=selected
                )
                print(json.dumps({"run_id": run_id, "status": "published"}))
            else:
                if args.command == "evaluate":
                    phase = "fitting"
                    result = evaluate_holdout(dataset, selected.selection)
                else:
                    from datetime import date

                    binding = OperationalBinding.model_validate_json(_file(args.binding))
                    origin = date.fromisoformat(args.origin)
                    phase = "fitting"
                    result = forecast(dataset, selected.selection, binding, origin)
                phase = "publication"
                output = publish_run(
                    result, Path(args.output_root), dataset=dataset, selection=selected
                )
                print(json.dumps({"run_id": output.run_id, "reused": output.reused}))
        return 0
    except Exception as error:
        if isinstance(error, OSError):
            code, exit_code = "IO_UNAVAILABLE", 5
        elif isinstance(error, FixtureNotAllowed):
            code, exit_code = "INPUT_UNADMITTED", 3
        elif (
            phase == "publication"
            and isinstance(error, ValueError)
            and str(error)
            in {"publication busy", "selection conflict", "artifact conflict", "receipt conflict"}
        ):
            code, exit_code = "OUTPUT_CONFLICT", 4
        elif (
            phase == "fitting"
            and isinstance(error, ValueError)
            and str(error)
            in {
                "no eligible train or validation windows",
                "label unavailable at information cutoff",
                "ineligible history",
                "selection or refit not known at origin",
                "training targets after origin",
            }
        ):
            code, exit_code = "INPUT_UNADMITTED", 3
        elif phase == "fitting":
            code, exit_code = "FIT_FAILED", 6
        else:
            code, exit_code = "INPUT_INVALID", 2
        if config is not None and hasattr(args, "output_root"):
            try:
                from app.forecasting.artifacts import write_failure_receipt

                write_failure_receipt(config, Path(args.output_root), code)
            except Exception:
                pass
        print(json.dumps({"code": code}), file=sys.stderr)
        return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
