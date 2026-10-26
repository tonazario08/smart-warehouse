"""Synthetic PostgreSQL evidence, never an admitted research dataset."""

import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from threading import Event
from uuid import uuid4

import pytest
from sqlalchemy import event as sql_event
from sqlalchemy import text, update
from sqlalchemy.orm import Session

from app.analytics.schemas import OPERATIONAL_KINDS, Admission, PipelineError
from app.analytics.semantics import prepare_dataset
from app.analytics.snapshot import capture_operational
from app.models import (
    MovementProvenance,
    Outbound,
    Product,
    PurchaseRequest,
    PurchaseRequestWorkflow,
    Stock,
    StockTransaction,
)
from app.purchase_requests.schemas import PurchaseRequestCreate
from tests.demand_data_helpers import admission_values, instant, software
from tests.postgres.test_purchase_request_atomicity import actor, service_for
from tests.postgres.test_purchase_requests_api import body_for, effects, seed_purchase

pytestmark = pytest.mark.postgres


def setup_source(session):
    ids = seed_purchase(session)
    service = service_for(session)
    created, _ = service.create(
        actor(session, ids, "client"), uuid4(), PurchaseRequestCreate(**body_for(ids))
    )
    service.approve(actor(session, ids, "admin"), created.id)
    result = service.fulfill(actor(session, ids, "warehouse"), created.id)
    session.execute(update(PurchaseRequest).values(created_at=instant(19, 6)))
    session.execute(
        update(PurchaseRequestWorkflow).values(
            decided_at=instant(19, 7), fulfilled_at=instant(19, 8)
        )
    )
    session.execute(update(Outbound).values(created_at=instant(19, 8)))
    session.execute(update(StockTransaction).values(created_at=instant(19, 8)))
    session.commit()
    values = admission_values()
    values["source"].update(
        kind="operational_b2b",
        files=(),
        kind_map=OPERATIONAL_KINDS,
        channel="managed_b2b_fulfillment",
        outside_target_kinds=("standard_outbound", "legacy_unknown"),
        availability_policy_ref="immutable-recording-policy",
        database_identity={
            "host": "127.0.0.1",
            "port": 18546,
            "database": "sw_m5_demand_test",
            "username": "sw_m5_demand_test",
        },
    )
    for row in (*values["mappings"], *values["coverage"]):
        row.update(source_product=str(ids["product"]), source_warehouse=str(ids["source"]))
    return ids, result, Admission(**values)


def test_m4_fulfillment_is_one_sanitized_event(postgres_session, postgres_engine):
    ids, result, admitted = setup_source(postgres_session)
    before = effects(postgres_session)
    postgres_session.rollback()
    statements = []

    def record(connection, cursor, statement, parameters, context, many):
        statements.append(statement.lower())

    sql_event.listen(postgres_engine, "before_cursor_execute", record)
    try:
        source = capture_operational(postgres_engine, admitted)
    finally:
        sql_event.remove(postgres_engine, "before_cursor_execute", record)
    assert len(source.records) == 1
    row = source.records[0]
    assert (row.event_id, row.quantity, row.unit, row.kind, row.occurred_at) == (
        f"tx:{result.fulfillment.transaction_id}",
        3,
        "cái",
        "purchase_request_fulfillment",
        instant(19, 8),
    )
    prepared = prepare_dataset(admitted, source, software())
    assert [row.target_quantity for row in prepared.observations] == [3, 0, 0]
    assert effects(postgres_session) == before
    sql = " ".join(statements)
    for private in (
        "users",
        "created_by_id",
        "requested_by_id",
        "fulfilled_by_id",
        "decided_by_id",
        ".note",
        ".reference",
        "idempotency_key",
        "request_fingerprint",
        "updated_at",
        "products",
        "stocks",
    ):
        assert private not in sql
    assert "set transaction read only" in sql


def test_read_only_repeatable_snapshot(postgres_session, postgres_engine):
    _, _, admitted = setup_source(postgres_session)
    observed = []

    def observe(connection, cursor, statement, parameters, context, many):
        if "FROM transactions" in statement:
            observed.append(
                connection.execute(
                    text(
                        "SELECT current_setting('transaction_read_only'), "
                        "current_setting('transaction_isolation')"
                    )
                ).one()
            )

    sql_event.listen(postgres_engine, "before_cursor_execute", observe)
    try:
        capture_operational(postgres_engine, admitted)
    finally:
        sql_event.remove(postgres_engine, "before_cursor_execute", observe)
    assert observed and set(observed) == {("on", "repeatable read")}


def test_database_enforces_read_only_not_just_code_convention(postgres_session, postgres_engine):
    _, _, admitted = setup_source(postgres_session)
    before = effects(postgres_session)

    def attempt_write(connection, cursor, statement, parameters, context, many):
        if "FROM transactions" in statement:
            connection.execute(text("INSERT INTO categories (name) VALUES ('M5 forbidden')"))

    sql_event.listen(postgres_engine, "before_cursor_execute", attempt_write)
    try:
        with pytest.raises(PipelineError, match="DATABASE_READ_ONLY"):
            capture_operational(postgres_engine, admitted)
    finally:
        sql_event.remove(postgres_engine, "before_cursor_execute", attempt_write)
    assert effects(postgres_session) == before


@pytest.mark.parametrize(
    "damage", ["quantity", "purpose", "missing_workflow", "status", "chronology"]
)
def test_corrupt_leg_fails_without_success(postgres_session, postgres_engine, damage):
    _, _, admitted = setup_source(postgres_session)
    if damage == "quantity":
        postgres_session.execute(update(Outbound).values(quantity=4))
    elif damage == "purpose":
        postgres_session.execute(update(MovementProvenance).values(purpose="standard_outbound"))
    elif damage == "missing_workflow":
        postgres_session.execute(text("DELETE FROM purchase_request_workflows"))
    elif damage == "status":
        postgres_session.execute(update(PurchaseRequest).values(status="approved"))
    else:
        postgres_session.execute(update(Outbound).values(created_at=instant(18)))
    postgres_session.commit()
    with pytest.raises(PipelineError, match="LINKAGE_CONFLICT"):
        capture_operational(postgres_engine, admitted)


def test_future_link_information_fails(postgres_session, postgres_engine):
    _, _, admitted = setup_source(postgres_session)
    postgres_session.execute(update(StockTransaction).values(created_at=instant(24)))
    postgres_session.commit()
    with pytest.raises(PipelineError, match="AFTER_CUTOFF"):
        capture_operational(postgres_engine, admitted)


def test_current_catalog_stock_is_not_history(postgres_session, postgres_engine):
    _, _, admitted = setup_source(postgres_session)
    first = capture_operational(postgres_engine, admitted)
    postgres_session.execute(update(Product).values(unit="MUTABLE", is_active=False))
    postgres_session.execute(update(Stock).values(quantity=999))
    postgres_session.execute(update(PurchaseRequest).values(updated_at=instant(25)))
    postgres_session.commit()
    second = capture_operational(postgres_engine, admitted)
    assert second == first
    assert second.records[0].unit == "cái"


def ordinary(session, ids, when, purpose="standard_outbound"):
    outbound = Outbound(
        warehouse_id=ids["source"],
        product_id=ids["product"],
        quantity=1,
        created_by_id=ids["warehouse"],
        created_at=when,
    )
    session.add(outbound)
    session.flush()
    transaction = StockTransaction(
        transaction_type="outbound",
        warehouse_id=ids["source"],
        product_id=ids["product"],
        quantity=1,
        outbound_id=outbound.id,
        created_by_id=ids["warehouse"],
        created_at=when,
    )
    session.add(transaction)
    session.flush()
    if purpose:
        session.add(MovementProvenance(transaction_id=transaction.id, purpose=purpose))
    session.commit()


def test_bounded_window_ignores_unmapped_history_but_fetches_straddling_link(
    postgres_session, postgres_engine
):
    ids, _, admitted = setup_source(postgres_session)
    values = admitted.model_dump()
    values["window_start"] = date(2026, 10, 20)
    values["mappings"][0]["valid_from"] = date(2026, 10, 20)
    values["coverage"] = tuple(
        row for row in values["coverage"] if row["business_date"] >= date(2026, 10, 20)
    )
    admitted = Admission(**values)
    ordinary(postgres_session, ids, instant(17))
    ordinary(postgres_session, ids, instant(25))
    # Fulfillment occurs just after business midnight while its linked creations are on prior day.
    postgres_session.execute(update(PurchaseRequestWorkflow).values(fulfilled_at=instant(19, 18)))
    postgres_session.execute(
        update(Outbound).where(Outbound.quantity == 3).values(created_at=instant(19, 16))
    )
    postgres_session.execute(
        update(StockTransaction)
        .where(StockTransaction.quantity == 3)
        .values(created_at=instant(19, 16))
    )
    postgres_session.commit()
    captured = capture_operational(postgres_engine, admitted)
    assert len(captured.records) == 1
    assert [
        row.target_quantity for row in prepare_dataset(admitted, captured, software()).observations
    ] == [3, 0]
    postgres_session.execute(update(Outbound).where(Outbound.quantity == 3).values(quantity=4))
    postgres_session.commit()
    with pytest.raises(PipelineError, match="LINKAGE_CONFLICT"):
        capture_operational(postgres_engine, admitted)


def test_ordinary_and_legacy_movements_do_not_become_sales(postgres_session, postgres_engine):
    ids, _, admitted = setup_source(postgres_session)
    ordinary(postgres_session, ids, instant(19, 9))
    ordinary(postgres_session, ids, instant(19, 10), purpose=None)
    captured = capture_operational(postgres_engine, admitted)
    prepared = prepare_dataset(admitted, captured, software())
    assert [row.target_quantity for row in prepared.observations] == [3, 0, 0]
    assert prepared.quality.exclusions == {"UNCLASSIFIED": 2}
    assert {row["kind"] for row in prepared.normalized_records} == {
        "purchase_request_fulfillment",
        "standard_outbound",
        "legacy_unknown",
    }


def test_concurrent_source_commit_does_not_mix_snapshot(postgres_session, postgres_engine):
    ids, _, admitted = setup_source(postgres_session)
    baseline = capture_operational(postgres_engine, admitted)
    started, release = Event(), Event()
    reader_pid = []

    def held(connection, cursor, statement, parameters, context, many):
        if "FROM transactions" in statement and not started.is_set():
            reader_pid.append(connection.scalar(text("SELECT pg_backend_pid()")))
            # The adapter already performed identity SELECT, fixing its transaction snapshot.
            started.set()
            assert release.wait(15)

    sql_event.listen(postgres_engine, "before_cursor_execute", held)
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(capture_operational, postgres_engine, admitted)
            try:
                assert started.wait(15)
                with postgres_engine.connect() as monitor:
                    assert (
                        monitor.scalar(
                            text(
                                "SELECT backend_xmin IS NOT NULL FROM pg_stat_activity "
                                "WHERE pid=:pid"
                            ),
                            {"pid": reader_pid[0]},
                        )
                        is True
                    )
                with Session(postgres_engine) as writer:
                    ordinary(writer, ids, instant(19, 9))
            finally:
                release.set()
            captured = future.result(timeout=20)
    finally:
        sql_event.remove(postgres_engine, "before_cursor_execute", held)
    assert captured == baseline
    next_snapshot = capture_operational(postgres_engine, admitted)
    assert len(next_snapshot.records) == 2
    assert next_snapshot.source_checksum != baseline.source_checksum


def test_real_operational_cli_build_reuses_without_source_effects(
    postgres_session, postgres_url, tmp_path
):
    _, _, admitted = setup_source(postgres_session)
    path = tmp_path / "admission.json"
    path.write_text(admitted.model_dump_json(), encoding="utf-8")
    output = tmp_path / "bundles"
    before = effects(postgres_session)
    postgres_session.rollback()
    env = dict(os.environ, ANALYTICS_DATABASE_URL=postgres_url)
    env.pop("DATABASE_URL", None)
    command = [
        sys.executable,
        "-m",
        "app.analytics.cli",
        "build",
        "--admission",
        str(path),
        "--output-root",
        str(output),
    ]
    first = subprocess.run(
        command, env=env, capture_output=True, text=True, encoding="utf-8", timeout=30, check=False
    )
    assert first.returncode == 0 and first.stderr == ""
    value = json.loads(first.stdout)
    assert value["dataset_class"] == "fixture" and value["reused"] is False
    second = subprocess.run(
        command, env=env, capture_output=True, text=True, encoding="utf-8", timeout=30, check=False
    )
    assert second.returncode == 0 and second.stderr == ""
    assert json.loads(second.stdout) == {**value, "reused": True}
    assert effects(postgres_session) == before
