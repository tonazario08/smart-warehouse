"""Bounded strict decoding and identity admission; no DB or publication side effects."""

import csv
import hashlib
import io
import json
import os
import posixpath
import re
import stat
import uuid
import zipfile
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from xml.etree import ElementTree as ET

from pydantic import ValidationError

from app.analytics.schemas import (
    MAX_DAILY_QUANTITY,
    MAX_EVENT_QUANTITY,
    MAX_INPUT_BYTES,
    MAX_ROWS,
    MEVGAL_ARCHIVE_SHA256,
    MEVGAL_MEMBER_SHA256,
    REPORTED_WARNINGS,
    Admission,
    DailyRecord,
    EventRecord,
    Issue,
    MevgalPreparationConfig,
    PipelineError,
    QualityReport,
    ReportedBenchmarkProtocol,
    ReportedSalesAdmission,
    ReportedSalesBatch,
    ReportedSalesRecord,
    SourceBatch,
    load_timezone,
)


def checked_path(path: Path, *, directory=False, must_exist=True) -> Path:
    """Check lexical ancestors before resolve, including Windows junctions/reparse points."""
    path = Path(path)
    if ".." in path.parts or str(path).startswith(("\\\\", "//")):
        raise PipelineError("OUTPUT_PATH_UNSAFE")
    absolute = path.absolute()
    try:
        for component in (*reversed(absolute.parents), absolute):
            if component.exists() or component.is_symlink():
                attributes = component.lstat()
                if stat.S_ISLNK(attributes.st_mode) or getattr(
                    attributes, "st_file_attributes", 0
                ) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400):
                    raise PipelineError("OUTPUT_PATH_UNSAFE")
        resolved = absolute.resolve(strict=must_exist)
        workspace = Path(__file__).resolve().parents[2]
        if directory:
            if resolved in (Path(resolved.anchor), Path.home().resolve(), workspace):
                raise PipelineError("OUTPUT_PATH_UNSAFE")
            if resolved.is_relative_to(workspace) and not resolved.is_relative_to(
                workspace / "artifacts" / "demand-data"
            ):
                raise PipelineError("OUTPUT_PATH_UNSAFE")
            if resolved.exists() and not resolved.is_dir():
                raise PipelineError("OUTPUT_PATH_UNSAFE")
        return resolved
    except OSError:
        raise PipelineError("IO_UNAVAILABLE") from None


def _decode_json(value):
    def pairs(items):
        result = {}
        for key, item in items:
            if key in result:
                raise PipelineError("INPUT_SCHEMA")
            result[key] = item
        return result

    try:
        return json.loads(
            value,
            object_pairs_hook=pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError()),
        )
    except (ValueError, TypeError, RecursionError):
        raise PipelineError("INPUT_SCHEMA") from None


def _tuples(value):
    if isinstance(value, list):
        return tuple(_tuples(item) for item in value)
    if isinstance(value, dict):
        return {key: _tuples(item) for key, item in value.items()}
    return value


def _bounded_read(path, remaining):
    try:
        if path.stat().st_size > remaining:
            raise PipelineError("INPUT_LIMIT")
        with path.open("rb") as stream:
            value = stream.read(remaining + 1)
        if len(value) > remaining:
            raise PipelineError("INPUT_LIMIT")
        return value
    except OSError:
        raise PipelineError("IO_UNAVAILABLE") from None


def load_admission(path: Path) -> Admission | ReportedSalesAdmission:
    path = checked_path(path)
    checked_path(path.parent, directory=True)
    value = _bounded_read(path, MAX_INPUT_BYTES)
    try:
        decoded = _tuples(_decode_json(value.decode("utf-8-sig")))
        if not isinstance(decoded, dict):
            raise PipelineError("ADMISSION_INVALID")
        schema_version = decoded.get("schema_version")
        if not isinstance(schema_version, str):
            raise PipelineError("ADMISSION_INVALID")
        model = {"demand-data/1": Admission, "demand-data/2": ReportedSalesAdmission}.get(
            schema_version
        )
        if model is None:
            raise PipelineError("ADMISSION_INVALID")
        parsed = model.model_validate(decoded)
    except (ValidationError, UnicodeError, PipelineError, RecursionError) as error:
        if isinstance(error, PipelineError) and error.code in {
            "INPUT_LIMIT",
            "TIMEZONE_UNAVAILABLE",
            "SOURCE_OVERLAP",
            "AFTER_CUTOFF",
            "TIME_VALUE",
            "UNKNOWN_MAPPING",
        }:
            raise
        raise PipelineError("ADMISSION_INVALID") from None
    parsed._input_bytes = len(value)
    parsed._admission_path = str(path)
    return parsed


def _report(accepted, duplicates=0, *, code=None, index=None, row=None):
    rejected = int(row is not None)
    return QualityReport(
        input_rows=accepted + duplicates + rejected,
        accepted_rows=accepted,
        duplicate_rows=duplicates,
        excluded_rows=0,
        rejected_rows=rejected,
        exclusions={},
        issues=(Issue(code=code, input_index=index, row_number=row),) if code else (),
        warnings=(),
    )


def _input_tree(root, allowed):
    for current, directories, names in os.walk(root, followlinks=False):
        for name in directories + names:
            path = checked_path(Path(current) / name)
            relative = path.relative_to(root).as_posix()
            if (name in names and relative not in allowed) or (
                name in directories and not any(item.startswith(relative + "/") for item in allowed)
            ):
                raise PipelineError("OUTPUT_PATH_UNSAFE")


def _record_values(row, *, csv_input, daily):
    model = DailyRecord if daily else EventRecord
    if not isinstance(row, dict) or set(row) != set(model.model_fields):
        raise PipelineError("INPUT_SCHEMA")
    row = dict(row)
    if csv_input:
        quantity = row["quantity"]
        if quantity == "" and daily:
            row["quantity"] = None
        else:
            maximum = MAX_DAILY_QUANTITY if daily else MAX_EVENT_QUANTITY
            if (
                not isinstance(quantity, str)
                or len(quantity) > len(str(maximum))
                or re.fullmatch(r"0|[1-9][0-9]*", quantity) is None
            ):
                raise PipelineError("INPUT_SCHEMA")
            row["quantity"] = int(quantity)
        if row["available_at"] == "":
            row["available_at"] = None
    try:
        return model(**row)
    except ValidationError:
        raise PipelineError("INPUT_SCHEMA") from None


def read_source(
    admission: Admission | ReportedSalesAdmission, input_root: Path
) -> SourceBatch | ReportedSalesBatch:
    if isinstance(admission, ReportedSalesAdmission):
        return _read_reported_source(admission, input_root)
    if admission.source.kind != "files":
        raise PipelineError("ADMISSION_INVALID")
    root = checked_path(input_root, directory=True)
    allowed = {item.path for item in admission.source.files}
    if admission._admission_path and Path(admission._admission_path).is_relative_to(root):
        allowed.add(Path(admission._admission_path).relative_to(root).as_posix())
    _input_tree(root, allowed)
    size, records, positions = admission._input_bytes, [], []
    declared = sorted(admission.source.files, key=lambda item: (item.format, item.sha256))
    lineage = [{"format": item.format, "sha256": item.sha256} for item in declared]
    checksum = hashlib.sha256(
        json.dumps(lineage, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
        + b"\n"
    ).hexdigest()
    for index, item in enumerate(declared):
        try:
            path = checked_path(root / item.path)
            if not path.is_relative_to(root) or not path.is_file():
                raise PipelineError("OUTPUT_PATH_UNSAFE")
            data = _bounded_read(path, MAX_INPUT_BYTES - size)
            size += len(data)
            if hashlib.sha256(data).hexdigest() != item.sha256:
                raise PipelineError("INPUT_HASH_MISMATCH")
            value = data.decode("utf-8-sig")
            if item.format == "jsonl":
                rows = enumerate(value.splitlines(), start=1)
            else:
                reader = csv.reader(io.StringIO(value, newline=""), strict=True)
                columns = next(reader, [])
                expected = (
                    DailyRecord if admission.source.representation == "daily" else EventRecord
                )
                if len(set(columns)) != len(columns) or set(columns) != set(expected.model_fields):
                    raise PipelineError("INPUT_SCHEMA")
                rows = enumerate(reader, start=2)
            for row_number, row in rows:
                if len(records) >= MAX_ROWS:
                    raise PipelineError(
                        "INPUT_LIMIT", _report(len(records), code="INPUT_LIMIT", index=index)
                    )
                try:
                    if item.format == "jsonl":
                        raw = _decode_json(row)
                    else:
                        if len(row) != len(columns):
                            raise PipelineError("INPUT_SCHEMA")
                        raw = dict(zip(columns, row, strict=True))
                    record = _record_values(
                        raw,
                        csv_input=item.format == "csv",
                        daily=admission.source.representation == "daily",
                    )
                    records.append(record)
                    positions.append((index, row_number))
                except PipelineError as error:
                    raise PipelineError(
                        error.code,
                        _report(len(records), code=error.code, index=index, row=row_number),
                    ) from None
        except (UnicodeError, csv.Error, PipelineError) as error:
            if isinstance(error, PipelineError) and error.report is not None:
                raise
            code = error.code if isinstance(error, PipelineError) else "INPUT_SCHEMA"
            raise PipelineError(code, _report(len(records), code=code, index=index)) from None
    batch = SourceBatch(
        source_checksum=checksum, records=tuple(records), report=_report(len(records))
    )
    batch._positions = tuple(positions)
    batch._input_root = root
    return validate_batch(admission, batch)


def validate_batch(
    admission: Admission | ReportedSalesAdmission, batch: SourceBatch | ReportedSalesBatch
) -> SourceBatch | ReportedSalesBatch:
    if isinstance(admission, ReportedSalesAdmission):
        return _validate_reported_batch(admission, batch)
    seen, days, records, positions = {}, set(), [], []
    duplicates = batch.report.duplicate_rows
    zone = load_timezone(admission.business_timezone)
    for offset, record in enumerate(batch.records):
        position = batch._positions[offset] if batch._positions else (0, offset + 1)
        try:
            expected = DailyRecord if admission.source.representation == "daily" else EventRecord
            if not isinstance(record, expected):
                raise PipelineError("INPUT_SCHEMA")
            if admission.target == "recorded_vend_units" and (
                not isinstance(record, DailyRecord)
                or record.coverage == "complete"
                or (record.coverage == "partial" and not record.quantity)
            ):
                raise PipelineError("INPUT_SCHEMA")
            identity = record.observation_id if isinstance(record, DailyRecord) else record.event_id
            payload = record.model_dump_json()
            if identity in seen:
                if seen[identity] != payload:
                    raise PipelineError("IDENTITY_CONFLICT")
                duplicates += 1
                continue
            day = (
                record.business_date
                if isinstance(record, DailyRecord)
                else (record.occurred_at.astimezone(zone).date())
            )
            mappings = [
                mapping
                for mapping in admission.mappings
                if mapping.source_product == record.source_product
                and mapping.source_warehouse == record.source_warehouse
            ]
            if not mappings:
                raise PipelineError("UNKNOWN_MAPPING")
            matching = [
                mapping for mapping in mappings if mapping.valid_from <= day < mapping.valid_to
            ]
            if matching and record.unit != matching[0].unit:
                raise PipelineError("UNIT_MISMATCH")
            if not matching and admission.window_start <= day < admission.window_end:
                raise PipelineError("UNKNOWN_MAPPING")
            if not any(mapping.unit == record.unit for mapping in mappings):
                raise PipelineError("UNIT_MISMATCH")
            if isinstance(record, EventRecord) and record.kind not in admission.source.kind_map:
                raise PipelineError("INPUT_SCHEMA")
            if isinstance(record, DailyRecord):
                day_key = (record.source_product, record.source_warehouse, record.unit, day)
                if day_key in days:
                    raise PipelineError("SOURCE_OVERLAP")
                days.add(day_key)
            seen[identity] = payload
            records.append(record)
            positions.append(position)
        except PipelineError as error:
            raise PipelineError(
                error.code,
                _report(
                    len(records), duplicates, code=error.code, index=position[0], row=position[1]
                ),
            ) from None
    result = SourceBatch(
        source_checksum=batch.source_checksum,
        records=tuple(records),
        report=_report(len(records), duplicates),
    )
    result._positions = tuple(positions)
    result._input_root = batch._input_root
    return result


def _validate_reported_batch(admission, batch):
    if not isinstance(batch, ReportedSalesBatch):
        raise PipelineError("INPUT_SCHEMA")
    seen, dates, cells, rows, positions = {}, set(), set(), [], []
    duplicates = batch.report.duplicate_rows
    for index, record in enumerate(batch.records):
        position = batch._positions[index] if batch._positions else (0, index + 1)
        try:
            if record.observation_id in seen:
                if seen[record.observation_id] != record:
                    raise PipelineError("IDENTITY_CONFLICT")
                duplicates += 1
                continue
            source_key = (record.source_member, record.source_row)
            if source_key in cells:
                raise PipelineError("IDENTITY_CONFLICT")
            mapping = [
                m
                for m in admission.mappings
                if m.source_product == record.source_product
                and m.source_reporting_entity == record.source_reporting_entity
                and m.valid_from <= record.business_date < m.valid_to
            ]
            if len(mapping) != 1:
                raise PipelineError("UNKNOWN_MAPPING")
            if record.unit != mapping[0].unit:
                raise PipelineError("UNIT_MISMATCH")
            if (
                record.available_at != admission.source_evidence.qualified_at
                or record.available_at > admission.cutoff
            ):
                raise PipelineError("AFTER_CUTOFF")
            key = (record.source_product, record.source_reporting_entity, record.business_date)
            if key in dates:
                raise PipelineError("SOURCE_OVERLAP")
            seen[record.observation_id] = record
            cells.add(source_key)
            dates.add(key)
            rows.append(record)
            positions.append(position)
        except PipelineError as error:
            raise PipelineError(
                error.code,
                _report(len(rows), duplicates, code=error.code, index=position[0], row=position[1]),
            ) from None
    result = ReportedSalesBatch(
        source_checksum=batch.source_checksum,
        records=tuple(rows),
        report=_report(len(rows), duplicates),
    )
    result._positions, result._input_root = tuple(positions), batch._input_root
    return result


def _read_reported_source(admission, input_root):
    from app.analytics.export import canonical_json

    root = checked_path(input_root, directory=True)
    item = admission.source.files[0]
    allowed = {item.path}
    if admission._admission_path and Path(admission._admission_path).is_relative_to(root):
        allowed.add(Path(admission._admission_path).relative_to(root).as_posix())
    _input_tree(root, allowed)
    path = checked_path(root / item.path)
    if not path.is_relative_to(root) or not path.is_file():
        raise PipelineError("OUTPUT_PATH_UNSAFE")
    content = _bounded_read(path, MAX_INPUT_BYTES - admission._input_bytes)
    if hashlib.sha256(content).hexdigest() != item.sha256:
        raise PipelineError("INPUT_HASH_MISMATCH")
    rows, previous = [], None
    try:
        for index, line in enumerate(content.splitlines(keepends=True), 1):
            if index > MAX_ROWS or len(line) > 16384:
                raise PipelineError("INPUT_LIMIT")
            record = ReportedSalesRecord.model_validate(_tuples(_decode_json(line.decode("utf-8"))))
            if canonical_json(record) != line or (
                previous is not None and record.observation_id <= previous
            ):
                raise PipelineError("INPUT_SCHEMA")
            previous = record.observation_id
            rows.append(record)
    except (ValidationError, UnicodeError, PipelineError) as error:
        code = error.code if isinstance(error, PipelineError) else "INPUT_SCHEMA"
        raise PipelineError(
            code, _report(len(rows), code=code, index=0, row=len(rows) + 1)
        ) from None
    lineage = [{"format": "jsonl", "sha256": item.sha256}]
    checksum = hashlib.sha256(canonical_json(lineage)).hexdigest()
    result = ReportedSalesBatch(
        source_checksum=checksum, records=tuple(rows), report=_report(len(rows))
    )
    result._input_root = root
    result._positions = tuple((0, i) for i in range(1, len(rows) + 1))
    return _validate_reported_batch(admission, result)


def parse_reported_sales_workbook(
    data: bytes, *, year: int, source_member: str, available_at
) -> tuple[ReportedSalesRecord, ...]:
    try:
        if year not in (2020, 2021, 2022) or source_member != f"mevgal-product2-{year}":
            raise ValueError
        with _checked_zip(data) as archive:
            parts = {item.filename: archive.read(item) for item in archive.infolist()}
        roots = {
            name: _xml(value) for name, value in parts.items() if name.endswith((".xml", ".rels"))
        }
        for name, root in roots.items():
            if name.endswith(".rels"):
                base = (
                    posixpath.dirname(name.replace("/_rels/", "/")) if name != "_rels/.rels" else ""
                )
                seen = set()
                for rel in root:
                    target = rel.attrib.get("Target", "")
                    resolved = (
                        posixpath.normpath(posixpath.join(base, target.lstrip("/")))
                        if not target.startswith("/")
                        else target.lstrip("/")
                    )
                    if (
                        rel.attrib.get("TargetMode", "Internal") != "Internal"
                        or not target
                        or any(c in target for c in ("\\", ":", "\0"))
                        or resolved.startswith(("../", "/"))
                        or resolved not in parts
                        or rel.attrib.get("Id") in seen
                    ):
                        raise ValueError
                    seen.add(rel.attrib.get("Id"))
        ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
        workbook = roots["xl/workbook.xml"]
        sheets = workbook.findall(f"{ns}sheets/{ns}sheet")
        if (
            len(sheets) != 1
            or sheets[0].attrib.get("name") != "Export"
            or sheets[0].attrib.get("sheetId") != "1"
        ):
            raise ValueError
        rels = roots["xl/_rels/workbook.xml.rels"]
        string_links = [r for r in rels if r.attrib.get("Type", "").endswith("/sharedStrings")]
        if len(string_links) != 1 or string_links[0].attrib.get("Target") != "sharedStrings.xml":
            raise ValueError
        sheet_id = sheets[0].attrib.get(
            "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
        )
        selected = [r for r in rels if r.attrib.get("Id") == sheet_id]
        if (
            len(selected) != 1
            or selected[0].attrib.get("Target") != "worksheets/sheet1.xml"
            or not selected[0].attrib.get("Type", "").endswith("/worksheet")
        ):
            raise ValueError
        strings = roots["xl/sharedStrings.xml"].findall(f"{ns}si")
        if len(strings) > MAX_ROWS * 16:
            raise PipelineError("INPUT_LIMIT")
        text = ["".join(node.text or "" for node in item.iter(f"{ns}t")) for item in strings]
        worksheet = roots["xl/worksheets/sheet1.xml"]
        if worksheet.find(f"{ns}mergeCells") is not None:
            raise ValueError
        raw_rows = worksheet.findall(f"{ns}sheetData/{ns}row")
        if not 2 <= len(raw_rows) <= MAX_ROWS + 1:
            raise PipelineError("INPUT_LIMIT")
        shared, seen_cells, seen_dates, result = {}, set(), set(), []
        day_shared = {}
        months = (
            "January",
            "February",
            "March",
            "April",
            "May",
            "June",
            "July",
            "August",
            "September",
            "October",
            "November",
            "December",
        )
        for number, raw_row in enumerate(raw_rows, 1):
            if raw_row.attrib.get("r") != str(number):
                raise ValueError
            cells = {}
            for cell in raw_row:
                if cell.tag != f"{ns}c":
                    raise ValueError
                coordinate = cell.attrib.get("r", "")
                match = re.fullmatch(r"([A-Z]{1,3})([1-9][0-9]{0,5})", coordinate)
                if not match or int(match[2]) != number or coordinate in seen_cells:
                    raise ValueError
                seen_cells.add(coordinate)
                cells[match[1]] = cell
            if len(cells) > 32 or not {"A", "B", "C", "D"}.issubset(cells):
                raise ValueError

            def value(column, *, string=False, blank=False, cells=cells):
                cell = cells.get(column)
                if cell is None:
                    if blank:
                        return None
                    raise ValueError
                values = cell.findall(f"{ns}v")
                if len(values) > 1:
                    raise ValueError
                raw = values[0].text if values else None
                if string:
                    if (
                        cell.attrib.get("t") != "s"
                        or raw is None
                        or not re.fullmatch(r"0|[1-9][0-9]*", raw)
                        or int(raw) >= len(text)
                    ):
                        raise ValueError
                    return text[int(raw)]
                if cell.attrib.get("t", "n") != "n":
                    raise ValueError
                if raw is None:
                    if blank:
                        return None
                    raise ValueError
                if (
                    not re.fullmatch(r"[+-]?[0-9]+(?:\.[0-9]+)?(?:[Ee][+-]?[0-9]+)?", raw)
                    or len(raw) > 80
                ):
                    raise ValueError
                numeric = Decimal(raw)
                if (
                    not numeric.is_finite()
                    or numeric != numeric.to_integral_value()
                    or abs(numeric) > MAX_DAILY_QUANTITY
                ):
                    raise ValueError
                return int(numeric)

            if number == 1:
                for column, expected in {
                    "A": "Day",
                    "B": "Month",
                    "C": "Year",
                    "D": "daily_unit_sales",
                    "G": "daily_unit_sales_kg",
                }.items():
                    if value(column, string=True) != expected:
                        raise ValueError
                continue
            for col in ("B", "C", "G"):
                if col in cells and cells[col].find(f"{ns}f") is not None:
                    raise ValueError
            month = value("B", string=True)
            if month not in months or value("C") != year:
                raise ValueError
            cached_day = value("A")
            day_formulas = cells["A"].findall(f"{ns}f")
            if len(day_formulas) > 1:
                raise ValueError
            if day_formulas:
                previous = result[-1] if result else None
                if (
                    previous is None
                    or previous.source_row != number - 1
                    or previous.business_date.year != year
                    or previous.business_date.month != months.index(month) + 1
                    or cached_day != previous.business_date.day + 1
                ):
                    raise ValueError
                formula = day_formulas[0]
                if formula.attrib.get("t") == "shared":
                    if set(formula.attrib) - {"t", "si", "ref"}:
                        raise ValueError
                    si = formula.attrib.get("si", "")
                    if (
                        len(si) > 10
                        or not re.fullmatch(r"0|[1-9][0-9]*", si)
                        or int(si) > 4294967295
                    ):
                        raise ValueError
                    if formula.text:
                        reference_text = formula.attrib.get("ref", "")
                        if len(reference_text) > 32:
                            raise ValueError
                        reference = re.fullmatch(r"A([1-9][0-9]*):A([1-9][0-9]*)", reference_text)
                        if (
                            si in day_shared
                            or si in shared
                            or not reference
                            or int(reference[1]) != number
                            or not number <= int(reference[2]) <= MAX_ROWS + 1
                        ):
                            raise ValueError
                        day_shared[si] = (number, int(reference[2]))
                        expression = formula.text
                    else:
                        if (
                            si not in day_shared
                            or not day_shared[si][0] <= number <= day_shared[si][1]
                            or "ref" in formula.attrib
                        ):
                            raise ValueError
                        expression = f"A{number - 1}+1"
                elif formula.attrib:
                    raise ValueError
                else:
                    expression = formula.text
                if expression != f"A{number - 1}+1":
                    raise ValueError
            day = date(year, months.index(month) + 1, cached_day)
            if day in seen_dates or (result and day <= result[-1].business_date):
                raise ValueError
            seen_dates.add(day)
            quantity = value("D")
            formulas = cells["D"].findall(f"{ns}f")
            if len(formulas) > 1:
                raise ValueError
            kind, operand = "literal", None
            if formulas:
                formula = formulas[0]
                kind = "same_row_divide_one"
                if formula.attrib.get("t") == "shared":
                    if set(formula.attrib) - {"t", "si", "ref"}:
                        raise ValueError
                    si = formula.attrib.get("si", "")
                    if not re.fullmatch(r"0|[1-9][0-9]*", si):
                        raise ValueError
                    if formula.text:
                        reference = re.fullmatch(
                            r"D([1-9][0-9]*):D([1-9][0-9]*)", formula.attrib.get("ref", "")
                        )
                        if (
                            si in shared
                            or si in day_shared
                            or not reference
                            or int(reference[1]) != number
                            or not number <= int(reference[2]) <= MAX_ROWS + 1
                        ):
                            raise ValueError
                        shared[si] = (number, int(reference[2]))
                        expression = formula.text
                    else:
                        if (
                            si not in shared
                            or not shared[si][0] <= number <= shared[si][1]
                            or "ref" in formula.attrib
                        ):
                            raise ValueError
                        expression = f"G{number}/1"
                elif formula.attrib:
                    raise ValueError
                else:
                    expression = formula.text
                if expression != f"G{number}/1":
                    raise ValueError
                operand = value("G", blank=True)
                if (operand is None and quantity != 0) or (
                    operand is not None and operand != quantity
                ):
                    raise ValueError
            status = (
                "missing_formula_operand"
                if kind == "same_row_divide_one" and operand is None
                else "negative_reported_sales"
                if quantity < 0
                else "eligible"
            )
            result.append(
                ReportedSalesRecord(
                    observation_id=f"{source_member}:row{number}",
                    source_product="product2",
                    source_reporting_entity="mevgal",
                    unit="unit",
                    business_date=day,
                    source_member=source_member,
                    source_row=number,
                    reported_quantity=quantity,
                    formula_kind=kind,
                    formula_operand=operand,
                    measurement_status=status,
                    available_at=available_at,
                )
            )
        return tuple(result)
    except (
        ValueError,
        KeyError,
        TypeError,
        IndexError,
        InvalidOperation,
        ET.ParseError,
        zipfile.BadZipFile,
        ValidationError,
    ):
        raise PipelineError("INPUT_SCHEMA") from None


def _checked_zip(data):
    if not isinstance(data, bytes) or len(data) > MAX_INPUT_BYTES:
        raise PipelineError("INPUT_LIMIT")
    archive = zipfile.ZipFile(io.BytesIO(data))
    names, total = set(), 0
    try:
        if len(archive.infolist()) > 128:
            raise PipelineError("INPUT_LIMIT")
        for item in archive.infolist():
            name = item.filename
            if (
                name in names
                or name.startswith(("/", "\\"))
                or any(c in name for c in ("\\", ":", "\0"))
                or any(p in ("", ".", "..") for p in name.rstrip("/").split("/"))
                or item.flag_bits & 1
                or stat.S_ISLNK(item.external_attr >> 16)
            ):
                raise PipelineError("INPUT_SCHEMA")
            names.add(name)
            total += item.file_size
            if item.file_size > MAX_INPUT_BYTES or total > MAX_INPUT_BYTES:
                raise PipelineError("INPUT_LIMIT")
        return archive
    except BaseException:
        archive.close()
        raise


def _xml(data):
    text = data.decode("utf-8-sig")
    if (
        len(data) > MAX_INPUT_BYTES
        or "\0" in text
        or "<!DOCTYPE" in text.upper()
        or "<!ENTITY" in text.upper()
    ):
        raise PipelineError("INPUT_SCHEMA")
    rows = cells = 0
    parser = ET.iterparse(io.BytesIO(data), events=("start",))
    for _, node in parser:
        rows += node.tag.endswith("}row")
        cells += node.tag.endswith("}c")
        if rows > MAX_ROWS + 1 or cells > (MAX_ROWS + 1) * 32:
            raise PipelineError("INPUT_LIMIT")
    return parser.root


MEVGAL_CONTROLS = {
    2020: (362, 362, 3, 306309),
    2021: (364, 360, 1, 291446),
    2022: (365, 362, 0, 269336),
}
MEVGAL_ANOMALIES = {
    "2021-01-01": "negative_reported_sales",
    "2021-03-14": "missing_formula_operand",
    "2021-05-02": "missing_formula_operand",
    "2021-05-03": "missing_formula_operand",
    "2022-01-01": "missing_formula_operand",
    "2022-03-06": "missing_formula_operand",
    "2022-04-24": "missing_formula_operand",
}


def prepare_mevgal_inputs(
    archive_path: Path, config_path: Path, destination_root: Path, *, software
):
    from app.analytics.export import _rename_stage, _write_file, canonical_json

    archive_path, config_path = checked_path(archive_path), checked_path(config_path)
    root = checked_path(destination_root, directory=True, must_exist=False)
    if (
        root.is_relative_to(archive_path.parent)
        or archive_path.parent.is_relative_to(root)
        or config_path.is_relative_to(root)
    ):
        raise PipelineError("OUTPUT_PATH_UNSAFE")
    raw_config = _bounded_read(config_path, MAX_INPUT_BYTES)
    try:
        config = MevgalPreparationConfig.model_validate(
            _tuples(_decode_json(raw_config.decode("utf-8")))
        )
    except (ValidationError, UnicodeError):
        raise PipelineError("ADMISSION_INVALID") from None
    archive_bytes = _bounded_read(archive_path, MAX_INPUT_BYTES - len(raw_config))
    archive_hash = hashlib.sha256(archive_bytes).hexdigest()
    if archive_hash != MEVGAL_ARCHIVE_SHA256:
        raise PipelineError("INPUT_HASH_MISMATCH")
    records, controls, member_hashes = [], {}, {}
    try:
        with _checked_zip(archive_bytes) as archive:
            for year in (2020, 2021, 2022):
                member = f"mevgal-product2-{year}"
                content = archive.read(f"product 2/product 2 {year}.xlsx")
                member_hashes[member] = hashlib.sha256(content).hexdigest()
                if member_hashes[member] != MEVGAL_MEMBER_SHA256[member]:
                    raise PipelineError("INPUT_HASH_MISMATCH")
                rows = parse_reported_sales_workbook(
                    content, year=year, source_member=member, available_at=config.qualified_at
                )
                eligible = [row for row in rows if row.measurement_status == "eligible"]
                counts = (
                    len(rows),
                    len(eligible),
                    sum(row.reported_quantity == 0 for row in eligible),
                    sum(row.reported_quantity for row in eligible),
                )
                if counts != MEVGAL_CONTROLS[year]:
                    raise PipelineError("INPUT_SCHEMA")
                controls[str(year)] = dict(
                    zip(
                        ("source_rows", "eligible_labels", "genuine_zeros", "eligible_sum"),
                        counts,
                        strict=True,
                    )
                )
                records.extend(rows)
    except (KeyError, zipfile.BadZipFile):
        raise PipelineError("INPUT_SCHEMA") from None
    anomalies = {
        row.business_date.isoformat(): row.measurement_status
        for row in records
        if row.measurement_status != "eligible"
    }
    if anomalies != MEVGAL_ANOMALIES:
        raise PipelineError("INPUT_SCHEMA")
    daily = b"".join(
        canonical_json(row) for row in sorted(records, key=lambda row: row.observation_id)
    )
    input_hash, config_hash = (
        hashlib.sha256(daily).hexdigest(),
        hashlib.sha256(raw_config).hexdigest(),
    )
    provenance = {
        "schema_version": "mevgal-provenance/1",
        "dataset_class": config.dataset_class,
        "archive_sha256": archive_hash,
        "member_sha256": member_hashes,
        "normalized_input_sha256": input_hash,
        "preparation_config_sha256": config_hash,
        "software": software.model_dump(),
        "controls": controls,
        "anomalies": anomalies,
        "acquired_at": config.acquired_at,
        "qualified_at": config.qualified_at,
        "rights": config.rights.model_dump(),
        "limitations": sorted(REPORTED_WARNINGS),
        "source_columns": {
            "day": "A",
            "month": "B",
            "year": "C",
            "reported_quantity": "D",
            "formula_operand": "G",
        },
    }
    provenance_body = canonical_json(provenance)
    provenance_hash = hashlib.sha256(provenance_body).hexdigest()
    version = "piv1-" + provenance_hash
    protocol = ReportedBenchmarkProtocol(
        version="reported-sales-protocol/1",
        knowledge_time_mode="retrospective_final_vintage",
        calendar="publisher_gregorian_date",
        partitions=tuple(
            {"name": name, "start": date(year, 1, 1), "end": date(year + 1, 1, 1)}
            for name, year in (("train", 2020), ("validation", 2021), ("final_holdout", 2022))
        ),
        horizons=(1, 7),
        history_days=28,
        imputation="none",
        missing_policy="retain_null_mask",
    )
    source_ref = (
        "zenodo:7853252" if config.dataset_class == "research" else "synthetic:mevgal-layout"
    )
    admission = ReportedSalesAdmission(
        schema_version="demand-data/2",
        target="reported_daily_unit_sales",
        dataset_class=config.dataset_class,
        source={
            "kind": "files",
            "namespace": source_ref,
            "snapshot_id": "mevgal-product2-v1:" + provenance_hash,
            "representation": "daily",
            "channel": "reported_daily_sales",
            "files": ({"path": "daily.jsonl", "format": "jsonl", "sha256": input_hash},),
            "kind_map": {},
            "outside_target_kinds": (),
            "available_at_upper_bound": config.qualified_at,
            "availability_policy_ref": "retrospective-final-vintage",
            "database_identity": None,
        },
        window_start=date(2020, 1, 1),
        window_end=date(2023, 1, 1),
        cutoff=config.cutoff,
        mappings=(
            {
                "source_product": "product2",
                "source_reporting_entity": "mevgal",
                "product_key": "mevgal:product2",
                "reporting_entity_key": "mevgal:company",
                "unit": "unit",
                "valid_from": date(2020, 1, 1),
                "valid_to": date(2023, 1, 1),
                "available_at": config.qualified_at,
            },
        ),
        rights=config.rights,
        protocol=protocol,
        source_evidence={
            "source_ref": source_ref,
            "cohort": "mevgal-product2-v1"
            if config.dataset_class == "research"
            else "fixture:mevgal-product2-v1",
            "archive_sha256": archive_hash,
            "member_sha256": member_hashes,
            "normalized_input_sha256": input_hash,
            "preparation_config_sha256": config_hash,
            "provenance_sha256": provenance_hash,
            "acquired_at": config.acquired_at,
            "qualified_at": config.qualified_at,
        },
    )
    contents = {
        "input/daily.jsonl": daily,
        "provenance.json": provenance_body,
        "admission.json": canonical_json(admission),
    }
    token, stage, owned, created = uuid.uuid4().hex, None, False, {}
    try:
        root.mkdir(parents=True, exist_ok=True)
        checked_path(root, directory=True)
        lock = checked_path(root / ".prepare.lock", must_exist=False)
        try:
            with lock.open("x", encoding="ascii") as stream:
                stream.write(token)
            owned = True
        except FileExistsError:
            raise PipelineError("OUTPUT_BUSY") from None
        target = root / version
        for candidate in root.iterdir():
            if candidate.name == ".prepare.lock":
                continue
            if not re.fullmatch(r"piv1-[0-9a-f]{64}", candidate.name):
                raise PipelineError("OUTPUT_CONFLICT")
            _verify_prepared_tree(candidate)
        if target.exists():
            if any(
                checked_path(target / name).read_bytes() != body for name, body in contents.items()
            ):
                raise PipelineError("OUTPUT_CONFLICT")
            reused = True
        else:
            stage = root / (".staging-" + uuid.uuid4().hex)
            stage.mkdir(mode=0o700)
            (stage / "input").mkdir(mode=0o700)
            for name, body in contents.items():
                created[name] = hashlib.sha256(body).hexdigest()
                _write_file(checked_path(stage / name, must_exist=False), body)
            _verify_prepared_tree(stage, version=version)
            _rename_stage(stage, target)
            stage, reused = None, False
        return {
            "input_version": version,
            "reused": reused,
            "normalized_input_sha256": input_hash,
            "provenance_sha256": provenance_hash,
        }
    except OSError:
        raise PipelineError("IO_UNAVAILABLE") from None
    finally:
        if owned:
            try:
                _clean_prepared_stage(stage, created)
            finally:
                if checked_path(lock).read_text(encoding="ascii") != token:
                    raise PipelineError("OUTPUT_CONFLICT")
                lock.unlink()


def _verify_prepared_tree(root, *, version=None):
    from app.analytics.export import canonical_json

    try:
        root = checked_path(root, directory=True)
        if {p.name for p in root.iterdir()} != {"admission.json", "provenance.json", "input"}:
            raise ValueError
        input_root = checked_path(root / "input", directory=True)
        if {p.name for p in input_root.iterdir()} != {"daily.jsonl"}:
            raise ValueError
        parsed = load_admission(root / "admission.json")
        if not isinstance(parsed, ReportedSalesAdmission):
            raise ValueError
        raw = _bounded_read(checked_path(root / "provenance.json"), MAX_INPUT_BYTES)
        provenance = _decode_json(raw.decode("utf-8"))
        digest = hashlib.sha256(raw).hexdigest()
        evidence = parsed.source_evidence
        if (
            canonical_json(provenance) != raw
            or (version or root.name) != "piv1-" + digest
            or evidence.provenance_sha256 != digest
        ):
            raise ValueError
        for key in (
            "archive_sha256",
            "member_sha256",
            "normalized_input_sha256",
            "preparation_config_sha256",
            "acquired_at",
            "qualified_at",
        ):
            if canonical_json(provenance[key]) != canonical_json(getattr(evidence, key)):
                raise ValueError
        if canonical_json(parsed) != (root / "admission.json").read_bytes():
            raise ValueError
        _read_reported_source(parsed, input_root)
    except (ValueError, OSError, KeyError, TypeError, PipelineError):
        raise PipelineError("OUTPUT_CONFLICT") from None


def _clean_prepared_stage(stage, created):
    if stage is None or not stage.exists():
        return
    checked_path(stage, directory=True)
    present = {p.relative_to(stage).as_posix() for p in stage.rglob("*")}
    if not present.issubset(set(created) | {"input"}):
        raise PipelineError("OUTPUT_CONFLICT")
    for name in present - {"input"}:
        path = checked_path(stage / name)
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != created[name]:
            raise PipelineError("OUTPUT_CONFLICT")
    for name in present - {"input"}:
        checked_path(stage / name).unlink()
    if "input" in present:
        checked_path(stage / "input", directory=True).rmdir()
    stage.rmdir()
