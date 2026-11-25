"""Provenance and authorization of the fixture-only anomaly voucher link."""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text, update

from app.anomalies.catalog import verify_run
from app.anomalies.models import AnomalyAlert, AnomalyOutboundLink
from app.anomalies.outbound_link import bind_verified_outbound, demo_snapshot_id
from app.auth.dependencies import PERMISSION_ROLES, Permission
from app.auth.security import create_access_token
from app.core.config import Settings
from app.db.session import get_session
from app.models import MovementProvenance, Outbound, StockTransaction, User, UserRole
from tests.prepare_b2b_outbound_anomaly_demo import _admission, _identity, prepare

pytestmark = pytest.mark.postgres


def test_snapshot_id_is_scoped_to_the_demo_instance():
    assert demo_snapshot_id(UUID(int=1)) != demo_snapshot_id(UUID(int=2))


def _settings(url, demo_id):
    return Settings(
        app_env="test",
        database_url=url,
        anomalies_allow_fixture=True,
        anomalies_outbound_link_demo_id=demo_id,
        jwt_secret_key=uuid4().hex + uuid4().hex,
        _env_file=None,
    )


def _client(settings, postgres_session):
    from app.main import create_app

    app = create_app(settings)
    app.dependency_overrides[get_session] = lambda: postgres_session
    return TestClient(app)


def _header(settings, uid):
    return {"Authorization": f"Bearer {create_access_token(uid, settings)}"}


def test_verified_voucher_requires_exact_transaction_and_dual_permission(
    postgres_session, postgres_url, tmp_path, monkeypatch
):
    import app.anomalies.router as router

    demo = uuid4()
    settings = _settings(postgres_url, demo)
    root = tmp_path / "linked-demo"
    session = postgres_session
    try:
        report = prepare(
            root,
            postgres_url,
            app_env="test",
            allow_fixture=True,
            automated_test=True,
            demo_id=demo,
        )
        alert_id = report["alert_id"]
        link = session.get(AnomalyOutboundLink, alert_id)
        tx = session.get(StockTransaction, link.transaction_id)
        assert tx.outbound_id == link.outbound_id != link.transaction_id
        assert session.get(Outbound, link.transaction_id) is not None
        voucher = session.get(Outbound, link.outbound_id)
        decoy = session.scalar(
            select(StockTransaction)
            .join(Outbound, StockTransaction.outbound_id == Outbound.id)
            .where(
                Outbound.quantity == voucher.quantity,
                Outbound.product_id == voucher.product_id,
                Outbound.warehouse_id == voucher.warehouse_id,
                Outbound.created_at == voucher.created_at,
                StockTransaction.id != tx.id,
            )
        )
        assert decoy and decoy.id != tx.id
        roles = {user.role.value: user.id for user in session.scalars(select(User))}
        generic = session.scalar(
            select(AnomalyAlert.id).where(AnomalyAlert.id != alert_id).limit(1)
        )
        assert generic
        path = "/api/v1" + report["outbound_path"]
        get_voucher = router.verified_outbound
        lookups = []

        def track(*args):
            lookups.append(args[-1])
            return get_voucher(*args)

        monkeypatch.setattr(router, "verified_outbound", track)
        with _client(settings, session) as client:
            assert client.get(path).status_code == 401
            assert client.get(path, headers=_header(settings, roles["client"])).status_code == 403
            missing = "/api/v1/anomalies/not-a-real-alert/outbound"
            assert (
                client.get(missing, headers=_header(settings, roles["client"])).status_code == 403
            )
            assert not lookups

            for role in ("admin", "warehouse"):
                headers = _header(settings, roles[role])
                response = client.get(path, headers=headers)
                assert response.status_code == 200
                assert response.headers["cache-control"] == "no-store"
                payload = response.json()
                assert payload["outbound_id"] == voucher.id
                assert payload["quantity"] == 10000 and payload["unit"] == "each"
                assert payload["performed_by_id"] == voucher.created_by_id
                assert set(payload) == {
                    "outbound_id",
                    "product_name",
                    "product_sku",
                    "warehouse_code",
                    "warehouse_name",
                    "quantity",
                    "unit",
                    "occurred_at",
                    "performed_by_id",
                }
                generic_path = f"/api/v1/anomalies/{generic}"
                assert client.get(generic_path, headers=headers).status_code == 200
                assert client.get(generic_path + "/outbound", headers=headers).status_code == 404

        with monkeypatch.context() as scoped:
            # Anomaly access alone must not be enough even if role maps diverge later.
            scoped.setitem(PERMISSION_ROLES, Permission.INVENTORY_HISTORY_READ, {UserRole.ADMIN})
            with _client(settings, session) as client:
                headers = _header(settings, roles["warehouse"])
                lookup_count = len(lookups)
                assert (
                    client.get(f"/api/v1/anomalies/{alert_id}", headers=headers).status_code == 200
                )
                assert client.get(path, headers=headers).status_code == 403
                assert len(lookups) == lookup_count

        for wrong in (None, uuid4()):
            hidden = _settings(postgres_url, wrong)
            with _client(hidden, session) as client:
                assert client.get(path, headers=_header(hidden, roles["admin"])).status_code == 404

        run = verify_run(root / "catalog", report["run_id"])
        records = session.execute(
            select(StockTransaction.product_id, StockTransaction.warehouse_id)
            .distinct()
            .order_by(StockTransaction.product_id)
        ).all()
        admission = _admission(
            dict(enumerate(records, start=1)),
            _identity(postgres_url, "test", True, automated_test=True),
            demo,
        )
        bundle = root / "bundles" / report["bundle_id"]
        kwargs = {
            "run": run,
            "alert_id": alert_id,
            "bundle_path": bundle,
            "admission": admission,
            "request_reference": voucher.reference,
        }
        with pytest.raises(ValueError, match="alert mismatch"):
            bind_verified_outbound(session, settings, event_id=f"tx:{decoy.id}", **kwargs)
        with pytest.raises(ValueError, match="bundle mismatch"):
            bind_verified_outbound(
                session, _settings(postgres_url, uuid4()), event_id=f"tx:{tx.id}", **kwargs
            )
        with pytest.raises(ValueError, match="transaction mismatch"):
            bind_verified_outbound(
                session,
                settings,
                event_id=f"tx:{tx.id}",
                **{**kwargs, "request_reference": "PR-" + uuid4().hex},
            )
        changed_fingerprint = session.execute(
            update(AnomalyOutboundLink)
            .where(AnomalyOutboundLink.alert_id == alert_id)
            .values(source_fingerprint="0" * 64)
        )
        assert changed_fingerprint.rowcount == 1
        with _client(settings, session) as client:
            assert client.get(path, headers=_header(settings, roles["admin"])).status_code == 404
        # No arbitrary link can replace the valid persisted proof.
        with pytest.raises(ValueError, match="conflicts with prior proof"):
            bind_verified_outbound(session, settings, event_id=f"tx:{tx.id}", **kwargs)
        session.rollback()
        changed = session.execute(
            update(MovementProvenance)
            .where(MovementProvenance.transaction_id == tx.id)
            .values(purpose="standard_outbound")
        )
        assert changed.rowcount == 1
        with _client(settings, session) as client:
            assert client.get(path, headers=_header(settings, roles["admin"])).status_code == 404
        session.rollback()
        assert session.scalar(select(AnomalyOutboundLink.alert_id)) == alert_id
    finally:
        if root.exists():
            session.rollback()
            session.execute(
                text(
                    "TRUNCATE anomaly_outbound_links, anomaly_reviews, anomaly_alerts, anomaly_runs"
                )
            )
            session.commit()
