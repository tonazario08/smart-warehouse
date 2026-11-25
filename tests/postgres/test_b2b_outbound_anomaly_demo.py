"""Run the B2B→M5→M9 thesis fixture against disposable PostgreSQL."""

from shutil import copytree

import pytest
from sqlalchemy import text

from app.anomalies.catalog import verify_run
from tests.prepare_b2b_outbound_anomaly_demo import prepare

pytestmark = pytest.mark.postgres


def test_b2b_outbound_anomaly_demo(postgres_url, postgres_session, tmp_path):
    # Shared PG test fixture cleans business rows; this test also owns its imported rows.
    root = tmp_path / "b2b-outbound"
    try:
        report = prepare(
            root, postgres_url, app_env="test", allow_fixture=True, automated_test=True
        )
    finally:
        if root.exists():
            postgres_session.execute(
                text(
                    "TRUNCATE anomaly_outbound_links, anomaly_reviews, anomaly_alerts, anomaly_runs"
                )
            )
            postgres_session.commit()
    assert report["event_count"] == 1200
    assert report["validation_normal"] >= 100
    assert report["target_score"] > report["threshold"] >= report["control_score"]
    assert abs(report["shap_residual"]) <= 1e-8
    assert report["alert_path"].startswith("/anomalies/alv1-")
    assert report["review_version"] == 2
    catalog = tmp_path / "tampered"
    copytree(root / "catalog", catalog)
    public = next(catalog.rglob("*.json"))
    public.write_bytes(public.read_bytes() + b" ")
    with pytest.raises(ValueError):
        verify_run(catalog, report["run_id"])
    print(report)


@pytest.mark.parametrize(
    ("url", "env", "allow"),
    [
        ("postgresql+psycopg://user@127.0.0.1:5432/prod", "test", True),
        (
            "postgresql+psycopg://sw_b2b_outbound_demo_test@192.0.2.1:5432/sw_b2b_outbound_demo_test",
            "test",
            True,
        ),
        (
            "postgresql+psycopg://sw_b2b_outbound_demo_test@127.0.0.1:5432/sw_b2b_outbound_demo_test",
            "production",
            True,
        ),
        (
            "postgresql+psycopg://sw_b2b_outbound_demo_test@127.0.0.1:5432/sw_b2b_outbound_demo_test",
            "integration",
            False,
        ),
    ],
)
def test_database_guard_rejects_before_artifacts(tmp_path, url, env, allow):
    output = tmp_path / "must-not-exist"
    with pytest.raises(ValueError):
        prepare(output, url, app_env=env, allow_fixture=allow)
    assert not output.exists()
