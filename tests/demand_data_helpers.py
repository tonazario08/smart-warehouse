"""Small synthetic inputs; these builders never prepare production outputs."""

import csv
import hashlib
import io
import json
from datetime import UTC, date, datetime, timedelta

from app.analytics.schemas import (
    Admission,
    EventRecord,
    QualityReport,
    SoftwareIdentity,
    SourceBatch,
)


def instant(day=19, hour=8):
    return datetime(2026, 10, day, hour, tzinfo=UTC)


def event_values(**changes):
    return {
        "event_id": "event-1",
        "source_product": "p1",
        "source_warehouse": "w1",
        "unit": "cái",
        "kind": "sale",
        "quantity": 3,
        "occurred_at": instant(),
        "available_at": instant(hour=9),
        **changes,
    }


def event(**changes):
    return EventRecord(**event_values(**changes))


def admission_values(**changes):
    return {
        "schema_version": "demand-data/1",
        "dataset_class": "fixture",
        "source": {
            "kind": "files",
            "namespace": "fixture",
            "snapshot_id": "snapshot-1",
            "representation": "events",
            "channel": "gross_fulfillment",
            "files": ({"path": "events.jsonl", "format": "jsonl", "sha256": "a" * 64},),
            "kind_map": {
                "sale": "customer_fulfillment",
                "inbound": "inbound",
                "transfer_in": "transfer_in",
                "transfer_out": "transfer_out",
                "return": "return",
                "adjustment": "adjustment",
                "cancellation": "cancellation",
                "test": "test",
                "unknown": "unclassified",
            },
            "outside_target_kinds": (),
            "available_at_upper_bound": None,
            "availability_policy_ref": None,
            "database_identity": None,
        },
        "target": "gross_fulfilled_units",
        "business_timezone": "Asia/Ho_Chi_Minh",
        "window_start": date(2026, 10, 19),
        "window_end": date(2026, 10, 22),
        "cutoff": instant(23),
        "mappings": (
            {
                "source_product": "p1",
                "source_warehouse": "w1",
                "product_key": "product-1",
                "warehouse_key": "warehouse-1",
                "unit": "cái",
                "valid_from": date(2026, 10, 19),
                "valid_to": date(2026, 10, 22),
                "lifecycle": "active",
                "available_at": instant(18),
            },
        ),
        "coverage": tuple(
            {
                "source_product": "p1",
                "source_warehouse": "w1",
                "business_date": date(2026, 10, day),
                "status": "complete",
                "available_at": instant(day + 1, 0),
            }
            for day in (19, 20, 21)
        ),
        "availability": (),
        "rights": None,
        **changes,
    }


def admission(**changes):
    return Admission(**admission_values(**changes))


def daily_values(**changes):
    return {
        "observation_id": "observation-1",
        "source_product": "p1",
        "source_warehouse": "w1",
        "unit": "cái",
        "business_date": date(2026, 10, 19),
        "quantity": 0,
        "coverage": "complete",
        "available_at": instant(20),
        **changes,
    }


def rights_values(**changes):
    return {
        "owner_ref": "owner-1",
        "permission_ref": "permission-1",
        "approved_by_ref": "reviewer-1",
        "privacy_ref": "privacy-1",
        "retention_ref": "retention-1",
        "approved_at": instant(18),
        **changes,
    }


def software():
    return SoftwareIdentity(
        python_version="3.12.13",
        packages={
            "pydantic": "2-test",
            "SQLAlchemy": "2-test",
            "psycopg": "3-test",
            "tzdata": "2026.5",
        },
        implementation_sha256="c" * 64,
    )


def day_proof(day, kind="positive", **changes):
    start = datetime.combine(day, datetime.min.time(), UTC) - timedelta(hours=7)
    return {
        "source_product": "p1",
        "source_warehouse": "w1",
        "start_at": start,
        "end_at": start + timedelta(days=1),
        "kind": kind,
        "available_at": start + timedelta(days=1, hours=1),
        **changes,
    }


def write_source(root, rows, format="jsonl", representation="events", **changes):
    path = root / ("data." + format)
    if format == "jsonl":
        content = "".join(
            json.dumps(row, default=lambda value: value.isoformat(), ensure_ascii=False) + "\n"
            for row in rows
        )
    else:
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(
            stream, fieldnames=tuple(rows[0]) if rows else tuple(event_values())
        )
        writer.writeheader()
        writer.writerows(
            {
                key: value.isoformat()
                if isinstance(value, (date, datetime))
                else ""
                if value is None
                else value
                for key, value in row.items()
            }
            for row in rows
        )
        content = stream.getvalue()
    path.write_bytes(content.encode("utf-8"))
    values = admission_values(**changes)
    values["source"].update(
        representation=representation,
        files=(
            {
                "path": path.name,
                "format": format,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            },
        ),
    )
    if representation == "daily":
        values["coverage"] = ()
    return Admission(**values)


def batch(*records):
    return SourceBatch(
        source_checksum="b" * 64,
        records=tuple(records),
        report=QualityReport(
            input_rows=len(records),
            accepted_rows=len(records),
            duplicate_rows=0,
            excluded_rows=0,
            rejected_rows=0,
            exclusions={},
            issues=(),
            warnings=(),
        ),
    )


# Captured verbatim before recorded-vending changes: the 23Oct gross fixture.
# Compression is only test-source storage; each decoded artifact retains its original bytes.
def old_gross_bundle_bytes():
    import base64
    import zlib

    encoded = (
        "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"
        "/55d//AeoEU8k="
    )
    files = json.loads(zlib.decompress(base64.b64decode(encoded)))
    return {name: base64.b64decode(value) for name, value in files.items()}


def recorded_admission_values(**changes):
    values = admission_values(target="recorded_vend_units", coverage=(), **changes)
    values["source"].update(representation="daily", channel="recorded_vends", kind_map={})
    values["mappings"] = tuple(
        {**row, "lifecycle": "unknown", "unit": "vend_unit"} for row in values["mappings"]
    )
    return values


def vend_values(**changes):
    return daily_values(**{"unit": "vend_unit", "coverage": "partial", "quantity": 3, **changes})


def write_vends(root, rows, **changes):
    values = recorded_admission_values(**changes)
    values.pop("schema_version")
    return write_source(root, rows, representation="daily", **values)


def old_vend_bundle_bytes():
    """Actual tiny synthetic rules2 bytes captured before reported-sales changes."""
    import base64
    import zlib

    encoded = (
        "eNrtWFtzo8gZ/Stb85xKcTGTJVV5sIwaQUQzQtBAvwmwFkEjaa0rpPLfc7ol2bJnZpOazOM+ULbo23c53/lO869P3WK9Wj7v"
        "9n9tdpv1p7//8um592vu6tvSpNvCeFiF690qz3i9SM913ondIossr9kW2fy0ytdsWKSWwNxl5Yo9z7bHoktW4coflYaop1p9"
        "zDS6WTCbYt7GW2GNYRs8wxkG5ol9NX3ymyqLjrzLsc7rA8czpvH4NI29gTmPD2HzeJLPFE/g4CGbFda0eRbVpcG0zKC7PKOD"
        "12xWvBMP1YT1fO7tvE6vy8loW3TVIO2VflUd2RYuWRUuW+bZ7MN544c/OG+3SLnITdEUrvJPL7r9oTCrg/SpnPhHPmFNRewX"
        "nrVy/FR2dlulVMO+cv1QmKzPDbZ8nfvkffbWj2e13rD1sqMiM6u67NgGcwf4gPFSjVeptb3M56LoouX19w6/68IVbWbwvjC0"
        "j/5Yam1HYDvWuL9+jG+vxg3S87Q+VhnON/biWZ17b4d29ta6zFO/SKtNNQlWYWfphXvC+YiDy4bM5KJcX/Gy8lue6nXRzfbl"
        "mu14FhyDlbSVNguX7XOm8g/c2AeVM/kutdppGtWVOz4GczUX9viNjMF93oDBbTURy9K14RO1MtMXfOV9LnBO8XS6w+kZvhAt"
        "M9mpdFmfGf4RMWuBg0OVnncScwuXHIqO7aQN8LUpTGk34tSxA4ePmPOyUGsUrqQfr+8yA9hCPp5NDTiz6iJlQ+kSZa/X8e3z"
        "JEI+EzkffkTwNUJugdeuEhIjco+y9z6nuiZjKIAJASwfKpdob3GBz5P2gp2OnEoDOSL2lisc0EOejYaFayt8LVGLWNtz1MM3"
        "/SE28Co0nInzKtREdKx0G1iafQcT4sBd28xMquWZr/YMmseerrRz8KSdw7lvw666XEdb3pFGYQI8URj+gNwaqE1gwRqm3XbA"
        "XxXjIKYtj9tz4ASnYEgsms7OQTN+yLvACoxI8KYWwRA13B2fwthvw9R7yI1xzx3a8NQzeUo63ngDbYQInUeTGrMHqvwheq5w"
        "0R4WwE2xkjkINOq0JncIYuA3efx44k2Cd35LU/kuMHiHvTpW58asDwy6ClN/RZtRR43cDJ3fhjDOz3QYCdhn8mY8cEflArVC"
        "j2UXvfONOo8Dx/wwLuFb3geo5bypuzCenfI06Cn2o4an07i1gjgwQsez8iEYeBfVPE3OGNdhp0At4Dcep27pSsUYeQQurvHN"
        "U8QiG2kyr+AXU2IomJ++xc9/8zrUUAculHNde8D7bSW5uXmU9aUVBn3B3uBPG/zDesyVWD/hzDduazaDxBZ46wCOQv1ba9Tc"
        "tjR2l3x3NtZLrIgGORcSmwHqEOfBRgtYJrvv73nXB6Rvhr0v3bOo3JuNI4WvPD3h9xi/2WFhWMdKckyjYtNW2UjyAHiDvcUD"
        "5/OsbooJa9/FCe9h/wn1+C524M8OObVy4ywucQOeXWHIWr6uqXPzPnb3dlBpB/zy9xKDz4ih5CT40ksOUXZ3t/healud259k"
        "jf6Oc7WPNoKHL/x14wu1z8i+9byvuHaSn6dxYtJhbFIn6FFTqAfMbVqDxzMtGIBup+3DOHkImt/OPMW4gfkdOi5qjrrBKXQx"
        "Z3jUuINO7noP3PHroAmufU/f3nhJcVbvj1hL/HhMnubJ2WdELFliTePWzmLJ8y0lsaBfklaEkW6zuN2HsV6FklfmieXEmj6L"
        "xyyJmO3EOidJSyaR5PzW+hK3xGFjkWIsmCeczHThxGPFo9gjWkatPY8SOkrwf9KyUUTa1zHYk0SJlWRaROKEhNHTZU9GsIZR"
        "MmO+Myf2eMaikbQF9i5nmk2T8ZmwMVuyMZlHGkuS/rIu0ziLxxx+nullXxrMEkHlWpwN2/1xlERL1rIwInQZa1aQzv3qNWbX"
        "mr1hLl8LTfaQsMnNIIbOcHINc7fFeqSD1zvUr1AYGKR2EYdygto00T9MhaOLFpG1BSwt0G8yI6qfs7sxR2FkyI1aFCmRvN9D"
        "g135MJLvDvxJVxiaprIeox2f/3rTH101kT0/udqsn9DX97KGr1y+RP8BJhJD8l1u0OanP4rLR+DjPTiBDaoWBY2Q153ySekq"
        "r5+CZ0pzJvN+KqUeM0dr1V96HfGl2kWPiTZX/BN8XKM9d0pnvPW9JlH9E2s09NPD+/ryhmkz7vEM3lp70yXMllqmWZhUL1TP"
        "91f5T3+81XK2+cenv/zyaVPsnl+Oi/1qs94poS5uSv29Mmq/UqYfFdGHTt4HZHYKnQ3Qg+fp4YakhVp7p+6hRjSlbhrvFDT5"
        "HgjGo6oP3dmCuvWl0gaTiWHRS4XyxpKXLoaodmR9UbVvzP7flPVNUSiWzFhdYJ3yswkkWqB6Ix3svFwYzFLK51VdaxdkyzWu"
        "0J6Z3SFO6yuDzcAGyTwhAar6Cyp4PksqIue/Mpl4z0DZncLKTKk4gK5Lp70pSqWwpA33iut/V9jaP39CPs/h/5PP5vEH8/lu"
        "7Mfy+Xqj+OGcvnaaP3N6n9Pxnzn9yTmVjPz7YSFW+/7dVxN0MdzkoIKJ3SM28ovE+UdU6vX9cFNcl1vmV4pAvhtKk4n7m+QC"
        "Nz+c077Nk4pV+mC9fgm5qiIXCobMNBIrhZSQcTq/KR/6JWajIGIRyfRolLQVYSS4Ki3bZcnZhfIL4oSFWIu4Qw3KtULuh73G"
        "bJxB2cVtFGeaHcZQaVl2idvLc7l5qb7TxL79WcY7/cFnGSmX4Riu37otpY34+qoq5dTlKpSnlRrHVb2HxK8LKRE/yHNcZ9SV"
        "//1V9mGvPkt08gokr89kh2tTx9dUXucHeSWEnBquV51zBalVSTDPr1L/9fPOrRBm6hPRu08dzDZx1RaQIHppqCIzL+MoRBUT"
        "WWAWEnv5raTBv/8DlaTCSQ=="
    )
    files = json.loads(zlib.decompress(base64.b64decode(encoded)))
    return {name: base64.b64decode(value) for name, value in files.items()}


def reported_protocol_values():
    return {
        "version": "reported-sales-protocol/1",
        "knowledge_time_mode": "retrospective_final_vintage",
        "calendar": "publisher_gregorian_date",
        "partitions": tuple(
            {"name": name, "start": date(year, 1, 1), "end": date(year + 1, 1, 1)}
            for name, year in (("train", 2020), ("validation", 2021), ("final_holdout", 2022))
        ),
        "horizons": (1, 7),
        "history_days": 28,
        "imputation": "none",
        "missing_policy": "retain_null_mask",
    }


def reported_values(**changes):
    return {
        "schema_version": "demand-data/2",
        "target": "reported_daily_unit_sales",
        "dataset_class": "fixture",
        "source": {
            "kind": "files",
            "namespace": "fixture:reported",
            "snapshot_id": "mevgal-product2-v1:" + "d" * 64,
            "representation": "daily",
            "channel": "reported_daily_sales",
            "files": ({"path": "daily.jsonl", "format": "jsonl", "sha256": "a" * 64},),
            "kind_map": {},
            "outside_target_kinds": (),
            "available_at_upper_bound": instant(20),
            "availability_policy_ref": "retrospective-qualification",
            "database_identity": None,
        },
        "window_start": date(2020, 1, 1),
        "window_end": date(2023, 1, 1),
        "cutoff": instant(23),
        "mappings": (
            {
                "source_product": "product2",
                "source_reporting_entity": "mevgal",
                "product_key": "mevgal:product2",
                "reporting_entity_key": "mevgal:company",
                "unit": "unit",
                "valid_from": date(2020, 1, 1),
                "valid_to": date(2023, 1, 1),
                "available_at": instant(20),
            },
        ),
        "rights": rights_values(),
        "protocol": reported_protocol_values(),
        "source_evidence": {
            "source_ref": "synthetic:mevgal-layout",
            "cohort": "fixture:mevgal-product2-v1",
            "archive_sha256": "b" * 64,
            "member_sha256": {
                f"mevgal-product2-{year}": str(year - 2019) * 64 for year in (2020, 2021, 2022)
            },
            "normalized_input_sha256": "a" * 64,
            "preparation_config_sha256": "c" * 64,
            "provenance_sha256": "d" * 64,
            "acquired_at": instant(19),
            "qualified_at": instant(20),
        },
        **changes,
    }


def reported_record_values(day=date(2020, 1, 1), **changes):
    return {
        "observation_id": "report:" + day.isoformat(),
        "source_product": "product2",
        "source_reporting_entity": "mevgal",
        "unit": "unit",
        "business_date": day,
        "source_member": "mevgal-product2-" + str(day.year),
        "source_row": (day - date(day.year, 1, 1)).days + 2,
        "reported_quantity": 2,
        "formula_kind": "literal",
        "formula_operand": None,
        "measurement_status": "eligible",
        "available_at": instant(20),
        **changes,
    }


def reported_observation_values(**changes):
    return {
        "product_key": "mevgal:product2",
        "reporting_entity_key": "mevgal:company",
        "reporting_entity_scope": "company_aggregate",
        "unit": "unit",
        "business_date": date(2020, 1, 1),
        "observed_quantity": 0,
        "target_quantity": 0,
        "measurement_status": "eligible",
        "reporting_coverage": "reported",
        "lifecycle": "unknown",
        "availability": "unknown",
        "censoring_risk": "unknown",
        "available_at": instant(20),
        "quality_flags": (),
        **changes,
    }


def reported_rows():
    day = date(2020, 1, 1)
    rows = []
    while day < date(2023, 1, 1):
        rows.append(reported_record_values(day))
        day += timedelta(days=1)
    return rows


def write_reported(root, rows):
    from app.analytics.export import canonical_json
    from app.analytics.ingestion import load_admission

    body = b"".join(
        canonical_json(row) for row in sorted(rows, key=lambda row: row["observation_id"])
    )
    digest = hashlib.sha256(body).hexdigest()
    values = reported_values()
    values["source"]["files"][0]["sha256"] = digest
    values["source_evidence"]["normalized_input_sha256"] = digest
    (root / "daily.jsonl").write_bytes(body)
    (root / "admission.json").write_bytes(canonical_json(values))
    return load_admission(root / "admission.json")


def ooxml_workbook(rows, *, overrides=None):
    """Tiny synthetic selected-source shape; never real research workbook data."""
    import zipfile
    from xml.sax.saxutils import escape

    ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    names = [
        "Day",
        "Month",
        "Year",
        "daily_unit_sales",
        "daily_unit_sales_kg",
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
    ]
    cells = [
        '<row r="1">'
        + "".join(
            f'<c r="{col}1" t="s"><v>{i}</v></c>'
            for col, i in (("A", 0), ("B", 1), ("C", 2), ("D", 3), ("G", 4))
        )
        + "</row>"
    ]
    for number, row in enumerate(rows, 2):
        month = row.get("month", "January")
        if month not in names:
            names.append(month)
        formula = row.get("formula", f"G{number}/1")
        attrs = row.get("formula_attrs", "")
        f = f"<f{attrs}>{escape(formula)}</f>" if formula is not None else ""
        operand = row.get("operand", row.get("quantity", "2"))
        g = "<v>" + str(operand) + "</v>" if operand is not None else ""
        day_formula = row.get("day_formula")
        day_attrs = row.get("day_formula_attrs", "")
        a_formula = f"<f{day_attrs}>{escape(day_formula)}</f>" if day_formula is not None else ""
        cells.append(
            f'<row r="{number}"><c r="A{number}">{a_formula}'
            f"<v>{row.get('day', number - 1)}</v></c>"
            f'<c r="B{number}" t="s"><v>{names.index(month)}</v></c>'
            f'<c r="C{number}"><v>{row.get("year", 2020)}</v></c>'
            f'<c r="D{number}">{f}<v>{row.get("quantity", "2")}</v></c>'
            f'<c r="G{number}">{g}</c></row>'
        )
    parts = {
        "xl/workbook.xml": (
            f'<workbook xmlns="{ns}" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets><sheet name="Export" sheetId="1" r:id="rId1"/></sheets></workbook>'
        ),
        "xl/_rels/workbook.xml.rels": (
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
            'Target="worksheets/sheet1.xml"/><Relationship Id="rId2" '
            'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/'
            'sharedStrings" '
            'Target="sharedStrings.xml"/></Relationships>'
        ),
        "xl/sharedStrings.xml": f'<sst xmlns="{ns}">'
        + "".join("<si><t>" + escape(s) + "</t></si>" for s in names)
        + "</sst>",
        "xl/worksheets/sheet1.xml": f'<worksheet xmlns="{ns}"><sheetData>'
        + "".join(cells)
        + "</sheetData></worksheet>",
    }
    parts.update(overrides or {})
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, value in parts.items():
            archive.writestr(name, value)
    return stream.getvalue()


def reported_inputs(rows=None):
    from app.analytics.export import canonical_json
    from app.analytics.schemas import (
        ReportedSalesAdmission,
        ReportedSalesBatch,
        ReportedSalesRecord,
    )

    rows = reported_rows() if rows is None else rows
    typed = tuple(ReportedSalesRecord(**row) for row in rows)
    body = b"".join(
        canonical_json(row) for row in sorted(typed, key=lambda row: row.observation_id)
    )
    digest = hashlib.sha256(body).hexdigest()
    values = reported_values()
    values["source"]["files"][0]["sha256"] = digest
    values["source_evidence"]["normalized_input_sha256"] = digest
    checksum = hashlib.sha256(canonical_json([{"format": "jsonl", "sha256": digest}])).hexdigest()
    return ReportedSalesAdmission(**values), ReportedSalesBatch(
        source_checksum=checksum,
        records=typed,
        report=QualityReport(
            input_rows=len(typed),
            accepted_rows=len(typed),
            duplicate_rows=0,
            excluded_rows=0,
            rejected_rows=0,
            exclusions={},
            issues=(),
            warnings=(),
        ),
    )
