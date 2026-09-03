from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.auth.security import create_access_token, hash_password
from app.db.base import Base
from app.db.session import get_session
from app.main import create_app
from app.models import Category, Product, Stock, User, Warehouse


def test_dashboard_is_admin_only_and_reports_stock_metrics() -> None:
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = Session(engine)
    admin = User(email="admin@example.com", password_hash=hash_password("password"), role="admin")
    client_user = User(
        email="client@example.com", password_hash=hash_password("password"), role="client"
    )
    category = Category(name="Hardware")
    warehouse = Warehouse(code="HCM-01", name="Central", address="1 Nguyen Hue")
    product = Product(sku="SKU-001", name="Bolt", category=category, unit="each", reorder_level=10)
    session.add_all([admin, client_user, warehouse, product])
    session.flush()
    session.add(Stock(warehouse_id=warehouse.id, product_id=product.id, quantity=4))
    session.commit()
    application = create_app()
    application.dependency_overrides[get_session] = lambda: session
    with TestClient(application) as test_client:
        client_token = create_access_token(client_user.id, client_user.role)
        response = test_client.get(
            "/api/v1/dashboard/stats", headers={"Authorization": f"Bearer {client_token}"}
        )
        assert response.status_code == 403
        admin_token = create_access_token(admin.id, admin.role)
        response = test_client.get(
            "/api/v1/dashboard/stats", headers={"Authorization": f"Bearer {admin_token}"}
        )
    assert response.status_code == 200
    assert response.json() == {"product_count": 1, "total_stock": 4, "low_stock_count": 1}
    session.close()
    engine.dispose()
