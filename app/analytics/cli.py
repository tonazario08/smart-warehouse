"""Explicit, import-inactive offline composition with bounded public diagnostics."""

import argparse
import hashlib
import os
import platform
import sys
from collections.abc import Sequence
from importlib.metadata import version
from pathlib import Path

from app.analytics.export import canonical_json, publish_bundle
from app.analytics.ingestion import load_admission, prepare_mevgal_inputs, read_source
from app.analytics.schemas import PipelineError, SoftwareIdentity
from app.analytics.semantics import prepare_dataset


def software_identity() -> SoftwareIdentity:
    root = Path(__file__).resolve().parents[2]
    names = sorted(
        [
            f"app/analytics/{name}.py"
            for name in (
                "__init__",
                "schemas",
                "ingestion",
                "semantics",
                "snapshot",
                "export",
                "cli",
            )
        ]
        + ["app/models/domain.py", "app/db/base.py"]
    )
    digest = hashlib.sha256()
    for name in names:
        content = (root / name).read_text(encoding="utf-8").replace("\r\n", "\n")
        digest.update(name.encode("utf-8") + b"\n" + content.encode("utf-8") + b"\n")
    return SoftwareIdentity(
        python_version=platform.python_version(),
        packages={name: version(name) for name in ("pydantic", "SQLAlchemy", "psycopg", "tzdata")},
        implementation_sha256=digest.hexdigest(),
    )


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise PipelineError("ADMISSION_INVALID")


def _arguments(argv):
    parser = _Parser(add_help=False)
    parser.add_argument("command", choices=("validate", "build", "prepare-mevgal"))
    parser.add_argument("--admission", type=Path)
    parser.add_argument("--input-root", type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--destination-root", type=Path)
    result = parser.parse_args(argv)
    preparation = (result.archive, result.config, result.destination_root)
    if result.command == "prepare-mevgal":
        if not all(preparation) or any((result.admission, result.input_root, result.output_root)):
            raise PipelineError("ADMISSION_INVALID")
    elif (
        any(preparation)
        or result.admission is None
        or (result.command == "build") != (result.output_root is not None)
    ):
        raise PipelineError("ADMISSION_INVALID")
    return result


def _source(admission, input_root):
    if admission.source.kind == "files":
        if input_root is None:
            raise PipelineError("ADMISSION_INVALID")
        return read_source(admission, input_root)
    if input_root is not None:
        raise PipelineError("ADMISSION_INVALID")
    value = os.environ.get("ANALYTICS_DATABASE_URL")
    if not value:
        raise PipelineError("DATABASE_UNAVAILABLE")
    from sqlalchemy import create_engine
    from sqlalchemy.pool import NullPool

    from app.analytics.snapshot import capture_operational, validate_database_url

    url = validate_database_url(value, admission.source.database_identity)
    engine = None
    try:
        engine = create_engine(url, poolclass=NullPool, hide_parameters=True)
        return capture_operational(engine, admission)
    finally:
        if engine is not None:
            engine.dispose()


def _failure(error):
    if error.code.startswith("OUTPUT_") or error.code == "SOURCE_SNAPSHOT_CONFLICT":
        status, message = 3, "Không thể công bố bộ dữ liệu an toàn."
    elif error.code.startswith("DATABASE_"):
        status, message = 4, "Không thể đọc nguồn cơ sở dữ liệu đã khai báo."
    elif error.code == "IO_UNAVAILABLE":
        status, message = 5, "Không thể hoàn thành thao tác dữ liệu."
    else:
        status, message = 2, "Dữ liệu hoặc tham số không hợp lệ; chưa công bố bộ dữ liệu."
    _emit(
        sys.stderr,
        {
            "code": error.code,
            "message": message,
            "report": error.report.model_dump() if error.report else None,
        },
    )
    return status


def _emit(stream, value):
    data = canonical_json(value)
    if hasattr(stream, "buffer"):
        stream.buffer.write(data)
        stream.buffer.flush()
    else:
        stream.write(data.decode("utf-8"))


def main(argv: Sequence[str] | None = None) -> int:
    try:
        args = _arguments(argv)
        if args.command == "prepare-mevgal":
            result = prepare_mevgal_inputs(
                args.archive, args.config, args.destination_root, software=software_identity()
            )
            _emit(
                sys.stdout,
                {
                    **result,
                    "message": "Đã chuẩn bị dữ liệu doanh số báo cáo; chưa công bố bộ dữ liệu.",
                },
            )
            return 0
        admission = load_admission(args.admission)
        prepared = prepare_dataset(
            admission, _source(admission, args.input_root), software_identity()
        )
        if args.command == "validate":
            result = {
                "message": "Dữ liệu hợp lệ; chưa công bố bộ dữ liệu.",
                "report": prepared.quality.model_dump(),
            }
        else:
            published = publish_bundle(prepared, args.output_root)
            result = {
                "data_version": published.data_version,
                "reused": published.reused,
                "dataset_class": admission.dataset_class,
                "message": (
                    "Đã công bố bộ dữ liệu doanh số báo cáo để đánh giá hồi cứu; "
                    "không xác nhận nhu cầu thực hoặc xuất kho."
                    if admission.target == "reported_daily_unit_sales"
                    else "Đã công bố mô tả lượt bán được ghi nhận; không xác nhận xuất kho thực tế."
                    if admission.target == "recorded_vend_units"
                    else "Đã kiểm tra và công bố bộ dữ liệu."
                ),
            }
        _emit(sys.stdout, result)
        return 0
    except KeyboardInterrupt:
        _emit(sys.stderr, {"code": "INTERRUPTED", "message": "Đã dừng thao tác.", "report": None})
        return 130
    except PipelineError as error:
        return _failure(error)
    except Exception:
        return _failure(PipelineError("IO_UNAVAILABLE"))


if __name__ == "__main__":
    raise SystemExit(main())
