from sqlalchemy import func, select

from app.auth.security import hash_password
from app.models import Stock, StockTransaction, User, UserRole


def test_forecast_reads_follow_current_role_and_do_not_change_stock(
    postgres_client, postgres_session
):
    user = User(
        email="forecast-user@example.com",
        password_hash=hash_password("strong-password"),
        role=UserRole.WAREHOUSE,
        is_active=True,
    )
    postgres_session.add(user)
    postgres_session.commit()
    login = postgres_client.post(
        "/api/v1/auth/login", json={"email": user.email, "password": "strong-password"}
    )
    assert login.status_code == 200
    headers = {"Authorization": "Bearer " + login.json()["access_token"]}
    assert postgres_client.get("/api/v1/forecasts/status?mode=operational").status_code == 401
    assert (
        postgres_client.get(
            "/api/v1/forecasts/status?mode=operational", headers={"Authorization": "Bearer invalid"}
        ).status_code
        == 401
    )
    before = (
        postgres_session.scalar(select(func.count()).select_from(Stock)),
        postgres_session.scalar(select(func.count()).select_from(StockTransaction)),
    )
    assert postgres_client.get("/api/v1/auth/me", headers=headers).json()["role"] == "warehouse"
    assert (
        postgres_client.get(
            "/api/v1/forecasts/status?mode=operational", headers=headers
        ).status_code
        == 200
    )
    assert (
        postgres_client.get("/api/v1/forecasts/status?mode=research", headers=headers).status_code
        == 403
    )
    user.role = UserRole.ADMIN
    postgres_session.commit()
    assert (
        postgres_client.get("/api/v1/forecasts/status?mode=research", headers=headers).status_code
        == 200
    )
    user.role = UserRole.CLIENT
    postgres_session.commit()
    assert (
        postgres_client.get(
            "/api/v1/forecasts/status?mode=operational", headers=headers
        ).status_code
        == 403
    )
    user.is_active = False
    postgres_session.commit()
    assert (
        postgres_client.get(
            "/api/v1/forecasts/status?mode=operational", headers=headers
        ).status_code
        == 401
    )
    after = (
        postgres_session.scalar(select(func.count()).select_from(Stock)),
        postgres_session.scalar(select(func.count()).select_from(StockTransaction)),
    )
    assert after == before
