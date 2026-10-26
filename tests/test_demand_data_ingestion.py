import hashlib
import json

import pytest
from pydantic import ValidationError

from app.analytics.ingestion import load_admission, read_source, validate_batch
from app.analytics.schemas import Admission, PipelineError, QualityReport, SourceBatch
from tests.demand_data_helpers import (
    admission_values,
    daily_values,
    event,
    event_values,
    write_source,
)


def raw_source(tmp_path, content, format="jsonl"):
    path = tmp_path / ("data." + format)
    path.write_bytes(content)
    values = admission_values()
    values["source"]["files"] = (
        {"path": path.name, "format": format, "sha256": hashlib.sha256(content).hexdigest()},
    )
    return Admission(**values)


@pytest.mark.parametrize(
    "selector",
    [
        {},
        {"nested": []},
        [[{}]],
        [],
        None,
        0,
        True,
        ["demand-data/1"],
        "demand-data/unknown",
    ],
)
def test_admission_schema_selector_must_be_a_known_string(tmp_path, selector):
    path = tmp_path / "admission.json"
    path.write_text(
        json.dumps({"schema_version": selector, "private": "PRIVATE_SCHEMA_SENTINEL"}),
        encoding="utf-8",
    )
    with pytest.raises(PipelineError, match="^ADMISSION_INVALID$") as caught:
        load_admission(path)
    assert caught.value.report is None


def test_reported_ingestion_preserves_ineligible_source_rows(tmp_path):
    from datetime import date

    from app.analytics.schemas import ReportedSalesBatch
    from tests.demand_data_helpers import reported_record_values, write_reported

    rows = [
        reported_record_values(reported_quantity=0),
        reported_record_values(
            date(2020, 1, 2), reported_quantity=-10, measurement_status="negative_reported_sales"
        ),
        reported_record_values(
            date(2020, 1, 3),
            reported_quantity=0,
            formula_kind="same_row_divide_one",
            measurement_status="missing_formula_operand",
        ),
    ]
    parsed = write_reported(tmp_path, rows)
    batch = read_source(parsed, tmp_path)
    assert isinstance(batch, ReportedSalesBatch)
    assert [r.reported_quantity for r in batch.records] == [0, -10, 0]
    assert batch.report.accepted_rows == 3
    assert batch.report.rejected_rows == batch.report.excluded_rows == 0


def test_reported_source_cell_identity_cannot_describe_two_dates(tmp_path):
    from datetime import date

    from tests.demand_data_helpers import reported_record_values, write_reported

    rows = [reported_record_values(), reported_record_values(date(2020, 1, 2), source_row=2)]
    parsed = write_reported(tmp_path, rows)
    with pytest.raises(PipelineError, match="IDENTITY_CONFLICT"):
        read_source(parsed, tmp_path)


@pytest.mark.parametrize(
    "damage", ["order", "noncanonical", "mapping", "entity", "unit", "knowledge", "identity"]
)
def test_reported_canonical_input_and_identity_are_not_repaired(tmp_path, damage):
    from datetime import date

    from app.analytics.export import canonical_json
    from app.analytics.schemas import ReportedSalesAdmission
    from tests.demand_data_helpers import instant, reported_record_values, reported_values

    rows = [reported_record_values(), reported_record_values(date(2020, 1, 2))]
    if damage == "order":
        rows.reverse()
    elif damage == "mapping":
        rows[0]["source_product"] = "unknown"
    elif damage == "entity":
        rows[0]["source_reporting_entity"] = "warehouse"
    elif damage == "unit":
        rows[0]["unit"] = "kg"
    elif damage == "knowledge":
        rows[0]["available_at"] = instant(24)
    elif damage == "identity":
        rows[1]["observation_id"] = rows[0]["observation_id"]
    body = b"".join(canonical_json(row) for row in rows)
    if damage == "noncanonical":
        body = body.replace(b'":', b'": ')
    digest = hashlib.sha256(body).hexdigest()
    values = reported_values()
    values["source"]["files"][0]["sha256"] = digest
    values["source_evidence"]["normalized_input_sha256"] = digest
    parsed = ReportedSalesAdmission(**values)
    (tmp_path / "daily.jsonl").write_bytes(body)
    with pytest.raises(PipelineError):
        read_source(parsed, tmp_path)


def test_ooxml_blank_operand_never_becomes_true_zero():
    from app.analytics.ingestion import parse_reported_sales_workbook
    from tests.demand_data_helpers import instant, ooxml_workbook

    data = ooxml_workbook(
        [
            {"quantity": "0", "operand": "0"},
            {"quantity": "0", "operand": None},
            {"quantity": "-10", "operand": "-10"},
        ]
    )
    records = parse_reported_sales_workbook(
        data, year=2020, source_member="mevgal-product2-2020", available_at=instant(20)
    )
    assert [r.measurement_status for r in records] == [
        "eligible",
        "missing_formula_operand",
        "negative_reported_sales",
    ]
    assert [r.reported_quantity for r in records] == [0, 0, -10]
    assert records[1].formula_operand is None


def test_ooxml_shared_same_row_formula_and_literal_match_exact_decimal():
    from app.analytics.ingestion import parse_reported_sales_workbook
    from tests.demand_data_helpers import instant, ooxml_workbook

    data = ooxml_workbook(
        [
            {"quantity": "2.0", "formula_attrs": ' t="shared" si="0" ref="D2:D4"'},
            {"quantity": "3", "formula": "", "formula_attrs": ' t="shared" si="0"'},
            {"quantity": "4", "formula": None},
        ]
    )
    rows = parse_reported_sales_workbook(
        data, year=2020, source_member="mevgal-product2-2020", available_at=instant(20)
    )
    assert [r.reported_quantity for r in rows] == [2, 3, 4]
    assert [r.formula_kind for r in rows] == [
        "same_row_divide_one",
        "same_row_divide_one",
        "literal",
    ]
    assert [r.source_row for r in rows] == [2, 3, 4]


@pytest.mark.parametrize(
    "changes",
    [
        {"operand": "3"},
        {"formula": "G3/1"},
        {"formula": "G2/0.6"},
        {"quantity": "1.5"},
        {"month": "NotAMonth"},
        {"day": 32},
        {"year": 2021},
        {"quantity": "NaN"},
        {"formula": "", "formula_attrs": ' t="shared" si="2"'},
        {"quantity": "1", "operand": None},
    ],
)
def test_ooxml_invalid_measurements_abort_without_formula_execution(changes):
    from app.analytics.ingestion import parse_reported_sales_workbook
    from tests.demand_data_helpers import instant, ooxml_workbook

    with pytest.raises(PipelineError, match="INPUT_SCHEMA"):
        parse_reported_sales_workbook(
            ooxml_workbook([changes]),
            year=2020,
            source_member="mevgal-product2-2020",
            available_at=instant(20),
        )


@pytest.mark.parametrize(
    "damage", ["dtd", "external", "unsafe", "duplicate_cell", "duplicate_date", "limit"]
)
def test_ooxml_source_integrity_is_bounded(damage, monkeypatch):
    from app.analytics import ingestion
    from tests.demand_data_helpers import instant, ooxml_workbook

    data = ooxml_workbook([{}, {}] if damage == "duplicate_date" else [{}])
    import io
    import zipfile

    with zipfile.ZipFile(io.BytesIO(data)) as z:
        parts = {n: z.read(n) for n in z.namelist()}
    if damage == "dtd":
        parts["xl/sharedStrings.xml"] = (
            b'<!DOCTYPE x [<!ENTITY x "bad">]>' + parts["xl/sharedStrings.xml"]
        )
    elif damage == "external":
        parts["xl/_rels/workbook.xml.rels"] = parts["xl/_rels/workbook.xml.rels"].replace(
            b'Target="worksheets/sheet1.xml"',
            b'TargetMode="External" Target="https://private.invalid/sheet"',
        )
    elif damage == "unsafe":
        parts["../unsafe.xml"] = b"<x/>"
    elif damage == "duplicate_cell":
        parts["xl/worksheets/sheet1.xml"] = parts["xl/worksheets/sheet1.xml"].replace(
            b'<c r="A2"><v>1</v></c>', b'<c r="A2"><v>1</v></c><c r="A2"><v>1</v></c>'
        )
    elif damage == "duplicate_date":
        parts["xl/worksheets/sheet1.xml"] = parts["xl/worksheets/sheet1.xml"].replace(
            b'<c r="A3"><v>2</v></c>', b'<c r="A3"><v>1</v></c>'
        )
    else:
        monkeypatch.setattr(ingestion, "MAX_INPUT_BYTES", 16)
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as z:
        for name, body in parts.items():
            z.writestr(name, body)
    with pytest.raises(PipelineError):
        ingestion.parse_reported_sales_workbook(
            stream.getvalue(),
            year=2020,
            source_member="mevgal-product2-2020",
            available_at=instant(20),
        )


@pytest.mark.parametrize("damage", ["utf16_dtd", "formula_attributes"])
def test_ooxml_refuses_hidden_dtd_and_unsupported_formula_attributes(damage):
    import io
    import zipfile

    from app.analytics.ingestion import parse_reported_sales_workbook
    from tests.demand_data_helpers import instant, ooxml_workbook

    rows = (
        [{"formula_attrs": ' t="shared" si="0" ref="D2:D2" ca="1"'}]
        if damage == "formula_attributes"
        else [{}]
    )
    data = ooxml_workbook(rows)
    if damage == "utf16_dtd":
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            parts = {name: archive.read(name) for name in archive.namelist()}
        xml = parts["xl/sharedStrings.xml"].decode()
        parts["xl/sharedStrings.xml"] = (
            '<!DOCTYPE sst [<!ENTITY unused "private">]>' + xml
        ).encode("utf-16")
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w") as archive:
            for name, body in parts.items():
                archive.writestr(name, body)
        data = stream.getvalue()
    with pytest.raises(PipelineError, match="INPUT_SCHEMA"):
        parse_reported_sales_workbook(
            data, year=2020, source_member="mevgal-product2-2020", available_at=instant(20)
        )


@pytest.mark.parametrize("damage", ["unbound", "redirected"])
def test_ooxml_shared_strings_must_match_the_declared_relationship(damage):
    import io
    import zipfile

    from app.analytics.ingestion import parse_reported_sales_workbook
    from tests.demand_data_helpers import instant, ooxml_workbook

    data = ooxml_workbook([{}])
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        parts = {name: archive.read(name) for name in archive.namelist()}
    rel = parts["xl/_rels/workbook.xml.rels"]
    if damage == "unbound":
        rel = rel.replace(
            b'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings"',
            b'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles"',
        )
    else:
        rel = rel.replace(b'Target="sharedStrings.xml"', b'Target="otherStrings.xml"')
        parts["xl/otherStrings.xml"] = parts["xl/sharedStrings.xml"]
    parts["xl/_rels/workbook.xml.rels"] = rel
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        for name, body in parts.items():
            archive.writestr(name, body)
    with pytest.raises(PipelineError, match="INPUT_SCHEMA"):
        parse_reported_sales_workbook(
            stream.getvalue(),
            year=2020,
            source_member="mevgal-product2-2020",
            available_at=instant(20),
        )


def test_ooxml_previous_day_plain_formula_uses_proven_cached_evidence():
    from datetime import date

    from app.analytics.ingestion import parse_reported_sales_workbook
    from tests.demand_data_helpers import instant, ooxml_workbook

    data = ooxml_workbook(
        [
            {"day": 1, "month": "December", "year": 2022},
            {"day": 2, "month": "December", "year": 2022, "day_formula": "A2+1"},
            {"day": 3, "month": "December", "year": 2022, "day_formula": "A3+1"},
        ]
    )
    rows = parse_reported_sales_workbook(
        data, year=2022, source_member="mevgal-product2-2022", available_at=instant(20)
    )
    assert [row.business_date for row in rows] == [
        date(2022, 12, 1),
        date(2022, 12, 2),
        date(2022, 12, 3),
    ]
    assert [row.reported_quantity for row in rows] == [2, 2, 2]
    assert [row.source_row for row in rows] == [2, 3, 4]


def test_ooxml_real_shaped_day_shared_chain_never_materializes_absent_row():
    from datetime import date, timedelta

    from app.analytics.ingestion import parse_reported_sales_workbook
    from tests.demand_data_helpers import instant, ooxml_workbook

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
    values = []
    for index in range(365):
        day = date(2022, 1, 1) + timedelta(days=index)
        values.append(
            {"day": day.day, "month": months[day.month - 1], "year": 2022, "formula": None}
        )
    values[335]["day_formula"] = "A336+1"  # A337, stored day 2.
    values[336].update(
        day_formula="A337+1", day_formula_attrs=' t="shared" si="18" ref="A338:A367"'
    )
    for index in range(337, 365):
        values[index].update(day_formula="", day_formula_attrs=' t="shared" si="18"')
    rows = parse_reported_sales_workbook(
        ooxml_workbook(values),
        year=2022,
        source_member="mevgal-product2-2022",
        available_at=instant(20),
    )
    assert len(rows) == 365
    assert rows[334].business_date == date(2022, 12, 1)
    assert rows[335].business_date == date(2022, 12, 2)
    assert rows[336].business_date == date(2022, 12, 3)
    assert rows[-1].business_date == date(2022, 12, 31)
    assert rows[-1].source_row == 366
    assert all(row.formula_kind == "literal" and row.reported_quantity == 2 for row in rows)
    assert not any(row.source_row == 367 for row in rows)


@pytest.mark.parametrize(
    "damage",
    [
        "stale_cache",
        "fraction_cache",
        "wrong_row",
        "step_two",
        "wrong_column",
        "absolute_ref",
        "no_predecessor",
        "month_change",
        "month_rollover",
        "year_change",
        "unbound_shared",
        "wrong_anchor_column",
        "wrong_anchor_start",
        "reversed_range",
        "oversized_range",
        "shared_extra_attribute",
        "plain_extra_attribute",
        "duplicate_anchor",
        "shared_child_ref",
        "child_outside_range",
        "column_shared_identity",
        "formula_in_b",
        "formula_in_c",
        "formula_in_g",
    ],
)
def test_ooxml_previous_day_formula_rejects_unproven_or_unsupported_chain(damage):
    import io
    import zipfile

    from app.analytics.ingestion import parse_reported_sales_workbook
    from tests.demand_data_helpers import instant, ooxml_workbook

    values = [
        {"day": 1, "month": "December", "year": 2022},
        {"day": 2, "month": "December", "year": 2022, "day_formula": "A2+1"},
        {"day": 3, "month": "December", "year": 2022, "day_formula": "A3+1"},
    ]
    if damage == "stale_cache":
        values[1]["day"] = 4
    elif damage == "fraction_cache":
        values[1]["day"] = "2.5"
    elif damage == "wrong_row":
        values[1]["day_formula"] = "A1+1"
    elif damage == "step_two":
        values[1]["day_formula"] = "A2+2"
    elif damage == "wrong_column":
        values[1]["day_formula"] = "G2+1"
    elif damage == "absolute_ref":
        values[1]["day_formula"] = "$A$2+1"
    elif damage == "no_predecessor":
        values[0]["day_formula"] = "A1+1"
    elif damage == "month_change":
        values[0].update(day=29, month="November")
        values[1].update(day=30, month="December")
        values[2]["day"] = 31
    elif damage == "month_rollover":
        values[0].update(day=30, month="November")
        values[1]["day"] = 1
    elif damage == "year_change":
        values[0]["year"] = 2021
    elif damage == "unbound_shared":
        values[1].update(day_formula="", day_formula_attrs=' t="shared" si="18"')
    elif damage == "plain_extra_attribute":
        values[1]["day_formula_attrs"] = ' ca="1"'
    else:
        values[1]["day_formula_attrs"] = ' t="shared" si="18" ref="A3:A4"'
        values[2].update(day_formula="", day_formula_attrs=' t="shared" si="18"')
        if damage == "wrong_anchor_column":
            values[1]["day_formula_attrs"] = ' t="shared" si="18" ref="D3:D4"'
        elif damage == "wrong_anchor_start":
            values[1]["day_formula_attrs"] = ' t="shared" si="18" ref="A2:A4"'
        elif damage == "reversed_range":
            values[1]["day_formula_attrs"] = ' t="shared" si="18" ref="A3:A2"'
        elif damage == "oversized_range":
            values[1]["day_formula_attrs"] = ' t="shared" si="18" ref="A3:A100002"'
        elif damage == "shared_extra_attribute":
            values[1]["day_formula_attrs"] += ' ca="1"'
        elif damage == "duplicate_anchor":
            values[2].update(
                day_formula="A3+1", day_formula_attrs=' t="shared" si="18" ref="A4:A5"'
            )
        elif damage == "shared_child_ref":
            values[2]["day_formula_attrs"] += ' ref="A4:A5"'
        elif damage == "child_outside_range":
            values[1]["day_formula_attrs"] = ' t="shared" si="18" ref="A3:A3"'
        elif damage == "column_shared_identity":
            values[0]["formula_attrs"] = ' t="shared" si="18" ref="D2:D4"'
    data = ooxml_workbook(values)
    if damage.startswith("formula_in_"):
        column = damage[-1].upper()
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            parts = {name: archive.read(name) for name in archive.namelist()}
        prefix = f'<c r="{column}3"'.encode()
        body = parts["xl/worksheets/sheet1.xml"]
        start = body.index(b">", body.index(prefix)) + 1
        parts["xl/worksheets/sheet1.xml"] = body[:start] + b"<f>1+1</f>" + body[start:]
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w") as archive:
            for name, value in parts.items():
                archive.writestr(name, value)
        data = stream.getvalue()
    with pytest.raises(PipelineError, match="INPUT_SCHEMA"):
        parse_reported_sales_workbook(
            data, year=2022, source_member="mevgal-product2-2022", available_at=instant(20)
        )


def fixture_preparation(tmp_path, monkeypatch):
    import io
    import zipfile

    from app.analytics import ingestion
    from app.analytics.export import canonical_json
    from tests.demand_data_helpers import instant, ooxml_workbook, rights_values

    raw = tmp_path / "raw"
    raw.mkdir()
    stream = io.BytesIO()
    hashes = {}
    with zipfile.ZipFile(stream, "w") as archive:
        for year in (2020, 2021, 2022):
            workbook = ooxml_workbook([{"year": year}])
            archive.writestr(f"product 2/product 2 {year}.xlsx", workbook)
            hashes[f"mevgal-product2-{year}"] = hashlib.sha256(workbook).hexdigest()
    data = stream.getvalue()
    path = raw / "Product_Sales_Dataset.zip"
    path.write_bytes(data)
    config = tmp_path / "preparation.json"
    config.write_bytes(
        canonical_json(
            {
                "schema_version": "mevgal-preparation/1",
                "dataset_class": "fixture",
                "rights": rights_values(),
                "acquired_at": instant(19),
                "qualified_at": instant(20),
                "cutoff": instant(23),
            }
        )
    )
    monkeypatch.setattr(ingestion, "MEVGAL_ARCHIVE_SHA256", hashlib.sha256(data).hexdigest())
    monkeypatch.setattr(ingestion, "MEVGAL_MEMBER_SHA256", hashes)
    monkeypatch.setattr(
        ingestion, "MEVGAL_CONTROLS", {year: (1, 1, 0, 2) for year in (2020, 2021, 2022)}
    )
    monkeypatch.setattr(ingestion, "MEVGAL_ANOMALIES", {})
    return path, config, tmp_path / "prepared"


def test_prepared_input_reuse_refuses_conflict_or_escape(tmp_path, monkeypatch):
    from app.analytics.ingestion import prepare_mevgal_inputs
    from tests.demand_data_helpers import software

    archive, config, root = fixture_preparation(tmp_path, monkeypatch)
    first = prepare_mevgal_inputs(archive, config, root, software=software())
    assert first["reused"] is False
    version = root / first["input_version"]
    expected = {"admission.json", "provenance.json", "input/daily.jsonl"}
    before = {
        p.relative_to(version).as_posix(): p.read_bytes() for p in version.rglob("*") if p.is_file()
    }
    assert set(before) == expected
    second = prepare_mevgal_inputs(archive, config, root, software=software())
    assert second == {**first, "reused": True}
    parsed = load_admission(version / "admission.json")
    assert parsed.dataset_class == "fixture"
    assert len(read_source(parsed, version / "input").records) == 3
    with pytest.raises(PipelineError, match="OUTPUT_PATH_UNSAFE"):
        prepare_mevgal_inputs(archive, config, archive.parent / "nested", software=software())
    (version / "input/daily.jsonl").write_bytes(b"private tamper")
    with pytest.raises(PipelineError, match="OUTPUT_CONFLICT"):
        prepare_mevgal_inputs(archive, config, root, software=software())
    assert (version / "input/daily.jsonl").read_bytes() == b"private tamper"
    assert (version / "admission.json").read_bytes() == before["admission.json"]


@pytest.mark.parametrize("checkpoint", [0, 1, 2, 3])
def test_preparation_write_rename_failure_never_publishes_success(
    tmp_path, monkeypatch, checkpoint
):
    from app.analytics import export, ingestion
    from tests.demand_data_helpers import software

    archive, config, root = fixture_preparation(tmp_path, monkeypatch)
    original, count = export._write_file, 0

    def fail(*args):
        nonlocal count
        current = count
        count += 1
        if current == checkpoint:
            raise OSError("private fixture")
        return original(*args)

    monkeypatch.setattr(export, "_write_file", fail)
    if checkpoint == 3:

        def fail_rename(*args):
            raise OSError("private fixture")

        monkeypatch.setattr(export, "_rename_stage", fail_rename)
    with pytest.raises(PipelineError, match="IO_UNAVAILABLE"):
        ingestion.prepare_mevgal_inputs(archive, config, root, software=software())
    assert list(root.iterdir()) == []


def test_csv_jsonl_equivalence(tmp_path):
    left, right = tmp_path / "left", tmp_path / "right"
    left.mkdir()
    right.mkdir()
    csv = read_source(write_source(left, [daily_values()], "csv", "daily"), left)
    jsonl = read_source(write_source(right, [daily_values()], "jsonl", "daily"), right)
    assert csv.records == jsonl.records
    assert csv.records[0].quantity == 0
    assert csv.source_checksum != jsonl.source_checksum
    from app.analytics.semantics import prepare_dataset
    from tests.demand_data_helpers import software

    csv_admission = write_source(left, [daily_values()], "csv", "daily")
    json_admission = write_source(right, [daily_values()], "jsonl", "daily")
    assert prepare_dataset(csv_admission, csv, software()).observations == (
        prepare_dataset(json_admission, jsonl, software()).observations
    )


@pytest.mark.parametrize(
    "content,format",
    [
        (b'{"event_id":"a","event_id":"b"}\n', "jsonl"),
        (b"event_id,event_id\na,b\n", "csv"),
        (b"\xff", "jsonl"),
        (b"[]\n", "jsonl"),
    ],
)
def test_duplicate_json_keys_and_limits(tmp_path, content, format):
    with pytest.raises(PipelineError, match="INPUT_SCHEMA"):
        read_source(raw_source(tmp_path, content, format), tmp_path)


def test_identity_not_quantity_dedup(tmp_path):
    parsed = write_source(
        tmp_path, [event_values(), event_values(), event_values(event_id="event-2")]
    )
    batch = read_source(parsed, tmp_path)
    assert [row.event_id for row in batch.records] == ["event-1", "event-2"]
    assert batch.report.model_dump() == {
        "input_rows": 3,
        "accepted_rows": 2,
        "duplicate_rows": 1,
        "excluded_rows": 0,
        "rejected_rows": 0,
        "exclusions": {},
        "issues": (),
        "warnings": (),
    }


def test_conflicting_identity_aborts(tmp_path):
    parsed = write_source(tmp_path, [event_values(), event_values(quantity=4)])
    with pytest.raises(PipelineError, match="IDENTITY_CONFLICT") as error:
        read_source(parsed, tmp_path)
    assert error.value.report.input_rows == 2
    assert error.value.report.rejected_rows == 1
    assert error.value.report.accepted_rows == 1


def test_one_source_and_one_representation(tmp_path):
    parsed = write_source(tmp_path, [daily_values()], representation="events")
    with pytest.raises(PipelineError, match="INPUT_SCHEMA"):
        read_source(parsed, tmp_path)
    values = admission_values()
    values["source"]["edition"] = "second-source-edition"
    with pytest.raises(ValidationError):
        Admission(**values)
    parsed = write_source(
        tmp_path, [daily_values(), daily_values(observation_id="other")], representation="daily"
    )
    with pytest.raises(PipelineError, match="SOURCE_OVERLAP"):
        read_source(parsed, tmp_path)


def test_mapping_alias_overlap_refused():
    values = admission_values()
    values["mappings"] = (values["mappings"][0], {**values["mappings"][0], "source_product": "p2"})
    with pytest.raises(PipelineError, match="SOURCE_OVERLAP"):
        Admission(**values)


@pytest.mark.parametrize(
    "changes,code",
    [
        ({"source_product": "unmapped"}, "UNKNOWN_MAPPING"),
        ({"unit": "box"}, "UNIT_MISMATCH"),
        ({"kind": "not-admitted"}, "INPUT_SCHEMA"),
    ],
)
def test_unknown_mapping_unit_and_hash_abort(tmp_path, changes, code):
    with pytest.raises(PipelineError, match=code):
        read_source(write_source(tmp_path, [event_values(**changes)]), tmp_path)


def test_hash_is_checked_before_parsing(tmp_path):
    parsed = write_source(tmp_path, [event_values()])
    (tmp_path / "data.jsonl").write_text("broken JSON", encoding="utf-8")
    with pytest.raises(PipelineError, match="INPUT_HASH_MISMATCH"):
        read_source(parsed, tmp_path)


@pytest.mark.parametrize(
    "quantity",
    ["01", "+1", "1.5", "1e2", " 1", "true", "9" * 5000],
    ids=["leading_zero", "sign", "fraction", "exponent", "space", "bool", "huge_decimal"],
)
def test_csv_quantities_are_canonical_decimals(tmp_path, quantity):
    parsed = write_source(tmp_path, [event_values(quantity=quantity)], format="csv")
    with pytest.raises(PipelineError, match="INPUT_SCHEMA"):
        read_source(parsed, tmp_path)


def test_rejections_never_echo_private_values(tmp_path):
    sentinel = "PRIVATE_SENTINEL_PASSWORD_EMAIL"
    parsed = write_source(tmp_path, [event_values(note=sentinel)])
    with pytest.raises(PipelineError) as error:
        read_source(parsed, tmp_path)
    assert str(error.value) == "INPUT_SCHEMA"
    assert sentinel not in str(error.value.report.model_dump())
    assert error.value.report.issues[0].model_dump() == {
        "code": "INPUT_SCHEMA",
        "input_index": 0,
        "row_number": 1,
    }
    assert not (tmp_path / "manifest.json").exists()


def test_admission_json_parsing_is_explicit_and_rejects_duplicate_fields(tmp_path):
    path = tmp_path / "admission.json"
    values = admission_values()
    path.write_text(json.dumps(values, default=lambda value: value.isoformat()), encoding="utf-8")
    assert load_admission(path).mappings[0].unit == "cái"
    path.write_text('{"dataset_class":"fixture","dataset_class":"research"}', encoding="utf-8")
    with pytest.raises(PipelineError, match="ADMISSION_INVALID"):
        load_admission(path)


def test_validate_batch_deduplicates_without_a_file_or_clock():
    from tests.demand_data_helpers import admission

    batch = SourceBatch(
        source_checksum="b" * 64,
        records=(event(), event()),
        report=QualityReport(
            input_rows=2,
            accepted_rows=2,
            duplicate_rows=0,
            excluded_rows=0,
            rejected_rows=0,
            exclusions={},
            issues=(),
            warnings=(),
        ),
    )
    result = validate_batch(admission(), batch)
    assert len(result.records) == 1
    assert result.report.duplicate_rows == 1


def test_input_byte_budget_includes_admission_and_checks_before_decode(tmp_path):
    path = tmp_path / "data.jsonl"
    with path.open("wb") as stream:
        stream.truncate(67108865)
    values = admission_values()
    values["source"]["files"] = ({"path": path.name, "format": "jsonl", "sha256": "b" * 64},)
    with pytest.raises(PipelineError, match="INPUT_LIMIT"):
        read_source(Admission(**values), tmp_path)
    parsed = write_source(tmp_path, [event_values()])
    parsed._input_bytes = 67108864
    with pytest.raises(PipelineError, match="INPUT_LIMIT"):
        read_source(parsed, tmp_path)


def test_physical_row_limit_precedes_identity_dedup(tmp_path):
    parsed = write_source(tmp_path, [event_values()])
    path = tmp_path / "data.jsonl"
    content = path.read_bytes() * 100001
    path.write_bytes(content)
    values = parsed.model_dump()
    values["source"]["files"] = (
        {"path": path.name, "format": "jsonl", "sha256": hashlib.sha256(content).hexdigest()},
    )
    with pytest.raises(PipelineError, match="INPUT_LIMIT") as failure:
        read_source(Admission(**values), tmp_path)
    assert failure.value.report.input_rows == 100000
    assert failure.value.report.issues[0].code == "INPUT_LIMIT"


def test_unexpected_input_file_does_not_get_silently_ignored(tmp_path):
    parsed = write_source(tmp_path, [event_values()])
    (tmp_path / "PRIVATE_EXTRA.txt").write_bytes(b"keep")
    with pytest.raises(PipelineError, match="OUTPUT_PATH_UNSAFE"):
        read_source(parsed, tmp_path)
    assert (tmp_path / "PRIVATE_EXTRA.txt").read_bytes() == b"keep"


@pytest.mark.parametrize(
    "changes",
    [
        {"quantity": 0},
        {"coverage": "complete"},
        {"quantity": True},
        {"quantity": 1.5},
        {"coverage": "unknown", "quantity": 3},
    ],
)
def test_recorded_vends_refuses_complete_or_zero(tmp_path, changes):
    from tests.demand_data_helpers import vend_values, write_vends

    parsed = write_vends(tmp_path, [dict(vend_values(), **changes)])
    with pytest.raises(PipelineError, match="INPUT_SCHEMA"):
        read_source(parsed, tmp_path)


def test_recorded_daily_source_keeps_positive_partial_and_unknown_null(tmp_path):
    from tests.demand_data_helpers import vend_values, write_vends

    parsed = write_vends(
        tmp_path,
        [
            vend_values(),
            dict(
                vend_values(),
                observation_id="unknown-2",
                business_date="2026-10-20",
                coverage="unknown",
                quantity=None,
                available_at=None,
            ),
        ],
    )
    result = read_source(parsed, tmp_path)
    assert [row.quantity for row in result.records] == [3, None]
    assert result.report.accepted_rows == 2
