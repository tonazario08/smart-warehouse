from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session


def test_liveness_and_readiness_are_healthy_with_database(postgres_client) -> None:
    assert postgres_client.get("/api/v1/health/live").status_code == 200
    assert postgres_client.get("/api/v1/health/ready").status_code == 200


def test_readiness_degrades_when_database_check_fails_but_liveness_stays_up(
    postgres_client, postgres_session: Session, monkeypatch
) -> None:
    def fail_database_check(*_args, **_kwargs):
        raise OperationalError("SELECT 1", {}, RuntimeError("simulated connection failure"))

    monkeypatch.setattr(postgres_session, "execute", fail_database_check)

    readiness = postgres_client.get("/api/v1/health/ready")
    liveness = postgres_client.get("/api/v1/health/live")

    assert readiness.status_code == 503
    assert readiness.json()["detail"]["code"] == "DATABASE_UNAVAILABLE"
    assert liveness.status_code == 200
