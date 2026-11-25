"""PostgreSQL-backed dashboard consistency and authorization tests."""

import pytest
from sqlalchemy import event
from sqlalchemy.orm import Session

from app.auth.security import create_access_token
from app.dashboard.repository import DashboardRepository
from app.dashboard.service import DashboardService
from app.models import Category, Product, Stock, User, UserRole, Warehouse


@pytest.fixture
def dashboard_dataset(postgres_session: Session, unit_settings):
    admin = User(email="dashboard-admin@example.com", password_hash="test", role=UserRole.ADMIN)
    client = User(email="dashboard-client@example.com", password_hash="test", role=UserRole.CLIENT)
    category = Category(name="Dashboard category")
    warehouse = Warehouse(code="DASH-01", name="Dashboard warehouse", address="Warehouse road")
    products = [
        Product(sku="DASH-001", name="Low one", category=category, unit="each", reorder_level=5),
        Product(sku="DASH-002", name="Low two", category=category, unit="each", reorder_level=8),
        Product(sku="DASH-003", name="Healthy", category=category, unit="each", reorder_level=2),
    ]
    postgres_session.add_all([admin, client, warehouse, *products])
    postgres_session.flush()
    postgres_session.add_all(
        [
            Stock(warehouse_id=warehouse.id, product_id=products[0].id, quantity=5),
            Stock(warehouse_id=warehouse.id, product_id=products[1].id, quantity=8),
            Stock(warehouse_id=warehouse.id, product_id=products[2].id, quantity=16),
        ]
    )
    postgres_session.commit()
    return {
        "admin": {"Authorization": f"Bearer {create_access_token(admin.id, unit_settings)}"},
        "client": {"Authorization": f"Bearer {create_access_token(client.id, unit_settings)}"},
        "products": products,
    }


def test_dashboard_is_admin_only_and_uses_database_aggregates(postgres_client, dashboard_dataset):
    data = dashboard_dataset
    assert postgres_client.get("/api/v1/dashboard/stats", headers=data["client"]).status_code == 403
    response = postgres_client.get("/api/v1/dashboard/stats", headers=data["admin"])

    assert response.status_code == 200
    assert response.json() == {"product_count": 3, "total_stock": 29, "low_stock_count": 2}


def test_dashboard_aggregates_execute_in_one_database_statement(
    postgres_session: Session, dashboard_dataset
) -> None:
    statements: list[str] = []

    def record_statement(_connection, _cursor, statement, _parameters, _context, _many) -> None:
        statements.append(statement)

    event.listen(postgres_session.bind, "before_cursor_execute", record_statement)
    try:
        stats = DashboardService(DashboardRepository(postgres_session)).get_stats()
    finally:
        event.remove(postgres_session.bind, "before_cursor_execute", record_statement)

    assert stats.model_dump() == {"product_count": 3, "total_stock": 29, "low_stock_count": 2}
    assert len(statements) == 1
    assert "SELECT" in statements[0].upper()


def test_dashboard_uses_zero_for_empty_stock(postgres_session: Session, unit_settings):
    user = User(email="empty-dashboard@example.com", password_hash="test", role=UserRole.ADMIN)
    postgres_session.add(user)
    postgres_session.commit()
    stats = DashboardService(DashboardRepository(postgres_session)).get_stats()

    assert stats.model_dump() == {"product_count": 0, "total_stock": 0, "low_stock_count": 0}
