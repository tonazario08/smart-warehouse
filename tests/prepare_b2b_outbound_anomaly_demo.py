"""Offline, isolated demonstration of a committed B2B outbound and its M9 alert."""

import argparse
import json
import os
from collections import Counter
from contextlib import contextmanager
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from alembic.config import Config
from alembic.script import ScriptDirectory
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, literal, make_url, select, text, update
from sqlalchemy.orm import Session

from app.analytics.cli import software_identity
from app.analytics.export import publish_bundle
from app.analytics.ingestion import checked_path
from app.analytics.schemas import OPERATIONAL_KINDS, Admission
from app.analytics.semantics import prepare_dataset
from app.analytics.snapshot import capture_operational
from app.anomalies.catalog import publish_run, verify_run
from app.anomalies.dataset import load_anomaly_dataset
from app.anomalies.features import build_feature_snapshot
from app.anomalies.models import AnomalyAlert
from app.anomalies.outbound_link import bind_verified_outbound, demo_snapshot_id
from app.anomalies.schemas import AnomalyConfig, Label, Partition
from app.anomalies.scoring import fit_and_score
from app.anomalies.service import AnomalyService
from app.auth.security import create_access_token, hash_password
from app.core.config import Settings
from app.db.base import Base
from app.db.session import get_session
from app.models import (
    Outbound,
    Product,
    PurchaseRequest,
    PurchaseRequestWorkflow,
    Stock,
    StockTransaction,
    User,
)
from app.purchase_requests.schemas import PurchaseRequestCreate
from tests.demand_data_helpers import admission_values
from tests.postgres.test_purchase_request_atomicity import actor, service_for
from tests.postgres.test_purchase_requests_api import body_for, seed_purchase

DEMO_DB = "sw_b2b_outbound_demo_test"
TEST_DATABASES = {
    ("127.0.0.1", 18547, "sw_m7_replenishment_test", "sw_m7_replenishment_test"),
    ("127.0.0.1", 55432, "smart_warehouse_test", "smart_warehouse_test"),
    ("127.0.0.1", 18546, "sw_m5_demand_test", "sw_m5_demand_test"),
}
BASE = "/api/v1/purchase-requests"
ANOMALIES = "/api/v1/anomalies"
ORIGIN = datetime(2026, 1, 1, tzinfo=UTC)
TARGET = (1, 15, 0)
CONTROL = (1, 15, 1)
COUNTS_PER_DAY = 30


def _identity(raw_url, app_env, allow_fixture, *, automated_test):
    if app_env not in ("test", "integration") or not allow_fixture:
        raise ValueError("test/integration and explicit fixture opt-in required")
    url = make_url(raw_url)
    identity = (url.host, url.port, url.database, url.username)
    permitted = (
        identity[0] in ("127.0.0.1", "::1")
        and identity[1] is not None
        and identity[2:] == (DEMO_DB, DEMO_DB)
    ) or (automated_test and app_env == "test" and identity in TEST_DATABASES)
    if (
        url.drivername != "postgresql+psycopg"
        or not permitted
        or set(url.query) - {"connect_timeout"}
        or (url.query and url.query.get("connect_timeout") != "5")
    ):
        raise ValueError("dedicated loopback PostgreSQL demo database and role required")
    return dict(zip(("host", "port", "database", "username"), identity, strict=True))


@contextmanager
def _exclusive_fixture_db(engine, identity, repo):
    # Keep the lock on its own PostgreSQL session across the workflow's commits.
    with engine.connect() as guard:
        name, role = guard.execute(text("SELECT current_database(), current_user")).one()
        if (name, role) != (identity["database"], identity["username"]):
            raise ValueError("connected database identity differs from guarded fixture")
        cfg = Config()
        cfg.set_main_option("script_location", str(repo / "alembic"))
        heads = set(ScriptDirectory.from_config(cfg).get_heads())
        revisions = set(guard.scalars(text("SELECT version_num FROM alembic_version")))
        if not heads or revisions != heads:
            raise ValueError("database must be migrated to this checkout's head")
        lock = "pg_try_advisory_lock(734227, 20261122)"
        if not guard.scalar(text(f"SELECT {lock}")):
            raise ValueError("another demo runner is using this database")
        try:
            yield
        finally:
            guard.execute(text("SELECT pg_advisory_unlock(734227, 20261122)"))


def _admission(pairs, identity, demo_id=None):
    start, end = date(2026, 1, 1), date(2026, 1, 21)
    data = admission_values(
        business_timezone="UTC",
        window_start=start,
        window_end=end,
        cutoff=ORIGIN + timedelta(days=20),
    )
    data["source"].update(
        kind="operational_b2b",
        files=(),
        kind_map=OPERATIONAL_KINDS,
        channel="managed_b2b_fulfillment",
        outside_target_kinds=("standard_outbound", "legacy_unknown"),
        availability_policy_ref="synthetic-recording-policy",
        database_identity=identity,
    )
    if demo_id is not None:
        data["source"]["snapshot_id"] = demo_snapshot_id(demo_id)
    data["mappings"] = tuple(
        {
            **data["mappings"][0],
            "source_product": str(p),
            "source_warehouse": str(w),
            "product_key": f"product-{k}",
            "warehouse_key": f"warehouse-{k}",
            "unit": "each",
            "valid_from": start,
            "valid_to": end,
            "available_at": ORIGIN - timedelta(days=1),
        }
        for k, (p, w) in pairs.items()
    )
    data["coverage"] = tuple(
        {
            "source_product": str(p),
            "source_warehouse": str(w),
            "business_date": start + timedelta(days=day),
            "status": "complete",
            "available_at": ORIGIN + timedelta(days=day + 1),
        }
        for p, w in pairs.values()
        for day in range(20)
    )
    return Admission(**data)


def _normalize_fixture_time(session, order_id, fulfillment, time):
    """Fixture-only timestamps; real workflow and stock mutations have already committed."""
    session.execute(
        update(PurchaseRequest)
        .where(PurchaseRequest.id == order_id)
        .values(created_at=time - timedelta(seconds=2))
    )
    session.execute(
        update(PurchaseRequestWorkflow)
        .where(PurchaseRequestWorkflow.purchase_request_id == order_id)
        .values(decided_at=time - timedelta(seconds=1), fulfilled_at=time)
    )
    session.execute(
        update(Outbound).where(Outbound.id == fulfillment["outbound_id"]).values(created_at=time)
    )
    session.execute(
        update(StockTransaction)
        .where(StockTransaction.id == fulfillment["transaction_id"])
        .values(created_at=time)
    )
    session.commit()


def _demo_email(role):
    return f"b2b-outbound-demo-{role}@example.com"


def _checked(response, status):
    if response.status_code != status:
        raise RuntimeError(f"unexpected demo API status: {response.status_code}, expected {status}")
    return response.json()


def _action(client, headers, order, action, role, status=200, body=None):
    return _checked(
        client.post(f"{BASE}/{order}/{action}", json=body or {}, headers=headers[role]), status
    )


def _create(client, headers, key, body, status=201):
    return _checked(
        client.post(
            BASE,
            headers={**headers["client"], "Idempotency-Key": str(key)},
            json=body,
        ),
        status,
    )["id"]


def _seed(engine, session, client, headers, ids, admission, pairs, *, link_enabled):
    service = service_for(session)
    labels, fixed = [], {}
    for k, (product, warehouse) in pairs.items():
        for day in range(20):
            for index in range(COUNTS_PER_DAY):
                coordinate = (k, day, index)
                injected = (k == 1 and day == 8 and index == 0) or (day >= 15 and index == 0)
                minute = index
                # A perfectly similar voucher still cannot identify the selected fulfillment.
                if link_enabled and (k, day, index) == (1, 15, 2):
                    injected, minute = True, 0
                when = ORIGIN + timedelta(days=day, hours=23 if injected else 12, minutes=minute)
                quantity = 10000 if injected else 1 + index % 7
                key = uuid5(NAMESPACE_URL, f"b2b-demo-{k}-{day}-{index}")
                payload = body_for(
                    ids, warehouse_id=warehouse, product_id=product, quantity=quantity, note=None
                )
                if coordinate in (TARGET, CONTROL):
                    order_id = _create(client, headers, key, payload)
                    if coordinate == TARGET:
                        _action(client, headers, order_id, "approve", "client", 403)
                        _action(client, headers, order_id, "approve", "warehouse", 403)
                        _action(client, headers, order_id, "fulfill", "warehouse", 409)
                        _action(client, headers, order_id, "fulfill", "client", 403)
                        count = len(capture_operational(engine, admission).records)
                        assert count == len(labels)
                    _action(client, headers, order_id, "approve", "admin")
                    if coordinate == TARGET:
                        assert len(capture_operational(engine, admission).records) == count
                    role = "warehouse" if coordinate == TARGET else "admin"
                    fulfilled = _action(client, headers, order_id, "fulfill", role)
                    fulfillment = fulfilled["fulfillment"]
                    assert (
                        _action(client, headers, order_id, "fulfill", role)["fulfillment"]
                        == fulfillment
                    )
                    fixed[coordinate] = (
                        f"tx:{fulfillment['transaction_id']}",
                        fulfilled["request_number"],
                    )
                else:
                    order, _ = service.create(
                        actor(session, ids, "client"), key, PurchaseRequestCreate(**payload)
                    )
                    order_id = order.id
                    service.approve(actor(session, ids, "admin"), order_id)
                    fulfillment = service.fulfill(
                        actor(session, ids, "warehouse"), order_id
                    ).fulfillment.model_dump()
                _normalize_fixture_time(session, order_id, fulfillment, when)
                labels.append(
                    Label(
                        namespace="fixture",
                        product_key=f"product-{k}",
                        warehouse_key=f"warehouse-{k}",
                        unit="each",
                        event_id=f"tx:{fulfillment['transaction_id']}",
                        label="anomaly" if injected else "normal",
                    )
                )
    reject = _create(client, headers, uuid4(), body_for(ids, note=None))
    reason = {"rejection_reason": "Kịch bản đối chứng"}
    _action(client, headers, reject, "reject", "warehouse", 403, reason)
    _action(client, headers, reject, "reject", "admin", body=reason)
    _action(client, headers, reject, "fulfill", "warehouse", 409)
    return tuple(labels), fixed


def _business_snapshot(session):
    return tuple(
        tuple(
            tuple(row.values())
            for row in session.execute(select(table).order_by(table.c.id)).mappings()
        )
        for table in (
            model.__table__ for model in (PurchaseRequest, Stock, Outbound, StockTransaction)
        )
    )


def _analyze(engine, session, ids, admission, labels, fixed, root, settings):
    before = _business_snapshot(session)
    source = capture_operational(engine, admission)
    records = {row.event_id: row for row in source.records}
    assert len(records) == len(source.records) == len(labels) == 1200
    assert set(records) == {label.event_id for label in labels}
    target, control = records[fixed[TARGET][0]], records[fixed[CONTROL][0]]
    assert (target.quantity, control.quantity, target.unit, control.unit) == (
        10000,
        2,
        "each",
        "each",
    )
    assert target.kind == control.kind == "purchase_request_fulfillment"
    bundle = publish_bundle(
        prepare_dataset(admission, source, software_identity()), root / "bundles"
    )
    partitions = tuple(
        Partition(
            name=name,
            start=date(2026, 1, a),
            end=date(2026, 1, b),
            information_cutoff=datetime(2026, 1, b, tzinfo=UTC),
        )
        for name, a, b in (("train", 8, 12), ("validation", 12, 16), ("final_holdout", 16, 20))
    )
    config = AnomalyConfig(
        data_version=bundle.data_version,
        allow_fixture=True,
        created_at=ORIGIN + timedelta(days=20),
        partitions=partitions,
        labels=labels,
    )
    snapshot = build_feature_snapshot(load_anomaly_dataset(config, bundle.path))
    counts = Counter((sample.partition, sample.label) for sample in snapshot.samples)
    result = fit_and_score(snapshot)
    if result.state != "available":
        raise RuntimeError(f"demo scoring unavailable: {result.reason}")
    [target_index] = [i for i, s in enumerate(snapshot.samples) if s.event_id == target.event_id]
    [control_index] = [i for i, s in enumerate(snapshot.samples) if s.event_id == control.event_id]
    target_sample, control_sample = snapshot.samples[target_index], snapshot.samples[control_index]
    # Other matching quantities are genuine but cannot identify the selected fulfillment.
    duplicate_shape = {
        row.event_id
        for row in records.values()
        if row.event_id != target.event_id
        and (row.source_product, row.source_warehouse, row.quantity, row.unit)
        == (target.source_product, target.source_warehouse, target.quantity, target.unit)
    }
    assert any(
        s.event_id in duplicate_shape and s.source_record_key != target_sample.source_record_key
        for s in snapshot.samples
    )
    target_score, control_score = result.scores[target_index], result.scores[control_index]
    assert target_sample.partition == control_sample.partition == "final_holdout"
    if not target_score > result.threshold >= control_score:
        raise RuntimeError(
            f"fixed target/control failed threshold check: {target_score}, "
            f"{result.threshold}, {control_score}"
        )
    catalog = root / "catalog"
    run_id = publish_run(result, catalog)
    verified = verify_run(catalog, run_id)
    [alert] = [
        a for a in verified.payload.alerts if a.source_record_key == target_sample.source_record_key
    ]
    assert all(
        a.source_record_key != control_sample.source_record_key for a in verified.payload.alerts
    )
    assert alert.explanation.state == "available"
    assert (
        abs(alert.explanation.base_value + sum(alert.explanation.contributions) - alert.score)
        <= 1e-8
    )
    anomaly = AnomalyService(session, app_env=settings.app_env, allow_fixture=True)
    first = anomaly.import_run(ids["admin"], verified)
    [alert_id] = session.scalars(
        select(AnomalyAlert.id).where(
            AnomalyAlert.run_id == run_id,
            AnomalyAlert.source_record_key == alert.source_record_key,
        )
    )
    bind_kwargs = {
        "run": verified,
        "alert_id": alert_id,
        "bundle_path": bundle.path,
        "admission": admission,
        "event_id": target.event_id,
        "request_reference": fixed[TARGET][1],
    }
    link_enabled = settings.anomalies_outbound_link_demo_id is not None
    if link_enabled:
        assert bind_verified_outbound(session, settings, **bind_kwargs)
    session.commit()
    retry = anomaly.import_run(ids["admin"], verified)
    if link_enabled:
        assert not bind_verified_outbound(session, settings, **bind_kwargs)
    session.commit()
    assert not first.replayed and retry.replayed and first.run_id == retry.run_id == run_id
    assert _business_snapshot(session) == before
    return dict(
        event_count=len(records),
        validation_normal=counts[("validation", "normal")],
        target_score=target_score,
        control_score=control_score,
        threshold=result.threshold,
        shap_residual=alert.explanation.residual,
        bundle_id=bundle.data_version,
        run_id=run_id,
        alert_path=f"/anomalies/{alert_id}",
        alert_id=alert_id,
        outbound_path=f"/anomalies/{alert_id}/outbound" if link_enabled else None,
        synthetic_holdout_metrics=result.synthetic_metrics,
    )


def _review(client, headers, session, report, *, save_review):
    path = ANOMALIES + "/" + report["alert_id"]
    _checked(client.get(path, headers=headers["client"]), 403)
    for role in ("admin", "warehouse"):
        detail = _checked(client.get(path, headers=headers[role]), 200)
        assert detail["explanation"]["state"] == "available"
        assert detail["run"]["dataset_class"] == "fixture"
    if report["outbound_path"] is not None:
        voucher = _checked(client.get(path + "/outbound", headers=headers["warehouse"]), 200)
        assert voucher["quantity"] == 10000 and voucher["unit"] == "each"
        _checked(client.get(path + "/outbound", headers=headers["client"]), 403)
        report["outbound_id"] = voucher["outbound_id"]
    before = _business_snapshot(session)
    session.rollback()
    review = {"expected_version": 1, "decision": "confirmed", "note": "Chỉ dành cho demo"}
    key = str(uuid4())
    _checked(
        client.patch(
            path + "/review", headers={**headers["client"], "Idempotency-Key": key}, json=review
        ),
        403,
    )
    if save_review:
        result = _checked(
            client.patch(
                path + "/review",
                headers={**headers["warehouse"], "Idempotency-Key": key},
                json=review,
            ),
            200,
        )
        assert result["version"] == 2
        report["review_version"] = result["version"]
        assert _business_snapshot(session) == before


def prepare(
    root,
    database_url,
    *,
    app_env,
    allow_fixture,
    automated_test=False,
    demo_password=None,
    demo_id=None,
):
    if not __debug__:
        raise RuntimeError("Python optimization disables required fixture assertions")
    identity = _identity(database_url, app_env, allow_fixture, automated_test=automated_test)
    output = checked_path(root, directory=True, must_exist=False)
    repo = Path(__file__).resolve().parents[1]
    if output.exists() or output.is_relative_to(repo):
        raise ValueError("new external proof directory required")
    settings = Settings(
        app_env=app_env,
        database_url=database_url,
        anomalies_allow_fixture=True,
        anomalies_outbound_link_demo_id=demo_id,
        jwt_secret_key=uuid4().hex + uuid4().hex,
        _env_file=None,
    )
    from app.main import create_app

    engine = create_engine(database_url, hide_parameters=True)
    try:
        with _exclusive_fixture_db(engine, identity, repo), Session(engine) as session:
            if any(
                session.scalar(select(literal(1)).select_from(table).limit(1)) is not None
                for table in Base.metadata.sorted_tables
            ):
                raise ValueError("database is not empty; use a fresh migrated fixture DB")
            session.rollback()
            output.mkdir(mode=0o700)
            (output / "bundles").mkdir()
            (output / "catalog").mkdir()
            if demo_id is not None:
                # Fixture only: distinguish transaction and voucher IDs; ID 451 is a decoy voucher.
                session.execute(
                    text("SELECT setval(pg_get_serial_sequence('outbounds', 'id'), 401, false)")
                )
            ids = seed_purchase(session, quantity=200000)
            second = Product(
                sku="M9-B2B-DEMO-2",
                name="Sản phẩm mẫu số 2",
                category_id=session.get(Product, ids["product"]).category_id,
                unit="each",
            )
            session.add(second)
            session.flush()
            second_id = second.id
            session.add(
                Stock(product_id=second_id, warehouse_id=ids["destination"], quantity=200000)
            )
            if demo_password is not None:
                password_hash = hash_password(demo_password)
                for role, user_id in ids.items():
                    if role in ("client", "other", "admin", "warehouse"):
                        session.execute(
                            update(User)
                            .where(User.id == user_id)
                            .values(email=_demo_email(role), password_hash=password_hash)
                        )
            session.commit()
            pairs = {1: (ids["product"], ids["source"]), 2: (second_id, ids["destination"])}
            headers = {
                role: {"Authorization": f"Bearer {create_access_token(ids[role], settings)}"}
                for role in ("client", "admin", "warehouse")
            }
            app = create_app(settings)

            def db_session():
                with Session(engine) as request_session:
                    yield request_session

            app.dependency_overrides[get_session] = db_session
            with TestClient(app) as client:
                if demo_password is not None:
                    for role in headers:
                        login = _checked(
                            client.post(
                                "/api/v1/auth/login",
                                json={"email": _demo_email(role), "password": demo_password},
                            ),
                            200,
                        )
                        assert login["user"]["role"] == role
                        headers[role] = {"Authorization": f"Bearer {login['access_token']}"}
                admission = _admission(pairs, identity, demo_id)
                labels, fixed = _seed(
                    engine,
                    session,
                    client,
                    headers,
                    ids,
                    admission,
                    pairs,
                    link_enabled=demo_id is not None,
                )
                report = _analyze(engine, session, ids, admission, labels, fixed, output, settings)
                _review(client, headers, session, report, save_review=automated_test)
            return report
    finally:
        engine.dispose()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    args = parser.parse_args()
    password = os.environ.get("B2B_OUTBOUND_DEMO_PASSWORD")
    if not password or len(password) < 12:
        parser.error("Set B2B_OUTBOUND_DEMO_PASSWORD to an isolated demo password (12+ characters)")
    instance = os.environ.get("ANOMALIES_OUTBOUND_LINK_DEMO_ID")
    print(
        json.dumps(
            prepare(
                args.root,
                os.environ.get("DATABASE_URL", ""),
                app_env=os.environ.get("APP_ENV", ""),
                allow_fixture=os.environ.get("ANOMALIES_ALLOW_FIXTURE", "").lower() == "true",
                demo_password=password,
                demo_id=UUID(instance) if instance else None,
            ),
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
