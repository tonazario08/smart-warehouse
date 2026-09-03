import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError, StatementError
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models import Category, Inbound, Outbound, Product, Stock, User, UserRole, Warehouse


@pytest.fixture
def session() -> Session:
    engine = create_engine("sqlite://")

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, _) -> None:
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    with Session(engine) as database_session:
        yield database_session


def test_user_rejects_guest_as_a_persisted_role(session: Session) -> None:
    """Persisted users must never acquire the anonymous guest role."""
    session.add(User(email="guest@example.com", password_hash="hash", role="guest"))

    with pytest.raises(StatementError):
        session.commit()


def test_category_requires_an_existing_parent(session: Session) -> None:
    """A category hierarchy cannot point to a missing parent row."""
    session.add(Category(name="Orphan", parent_id=999))

    with pytest.raises(IntegrityError):
        session.commit()


def test_stock_rejects_duplicate_product_and_warehouse_pair(session: Session) -> None:
    """Only one stock balance exists for a product at each warehouse."""
    category = Category(name="Tools")
    warehouse = Warehouse(code="HCM-01", name="Ho Chi Minh", address="1 Nguyen Hue")
    product = Product(sku="TOOL-001", name="Tool", category=category, unit="each")
    session.add_all([category, warehouse, product])
    session.flush()
    session.add_all(
        [
            Stock(warehouse=warehouse, product=product, quantity=1),
            Stock(warehouse=warehouse, product=product, quantity=2),
        ]
    )

    with pytest.raises(IntegrityError):
        session.commit()


def test_stock_rejects_negative_quantity(session: Session) -> None:
    """The database must prevent a stock balance below zero."""
    category = Category(name="Hardware")
    warehouse = Warehouse(code="HCM-02", name="District 7", address="2 Nguyen Van Linh")
    product = Product(sku="HARD-001", name="Bolt", category=category, unit="each")
    session.add_all([category, warehouse, product])
    session.flush()
    session.add(Stock(warehouse=warehouse, product=product, quantity=-1))

    with pytest.raises(IntegrityError):
        session.commit()


def test_inbound_rejects_nonpositive_quantity(session: Session) -> None:
    """Inbound inventory events must record a positive quantity."""
    category = Category(name="Inbound category")
    warehouse = Warehouse(code="HCM-03", name="Thu Duc", address="3 Vo Van Ngan")
    product = Product(sku="IN-001", name="Inbound item", category=category, unit="each")
    user = User(email="admin@example.com", password_hash="hash", role=UserRole.ADMIN)
    session.add_all([category, warehouse, product, user])
    session.flush()
    session.add(
        Inbound(warehouse_id=warehouse.id, product_id=product.id, quantity=0, created_by_id=user.id)
    )

    with pytest.raises(IntegrityError):
        session.commit()


def test_outbound_rejects_nonpositive_quantity(session: Session) -> None:
    """Outbound inventory events must record a positive quantity."""
    category = Category(name="Outbound category")
    warehouse = Warehouse(code="HCM-04", name="Binh Thanh", address="4 Dien Bien Phu")
    product = Product(sku="OUT-001", name="Outbound item", category=category, unit="each")
    user = User(email="operator@example.com", password_hash="hash", role=UserRole.WAREHOUSE)
    session.add_all([category, warehouse, product, user])
    session.flush()
    session.add(
        Outbound(
            warehouse_id=warehouse.id, product_id=product.id, quantity=-1, created_by_id=user.id
        )
    )

    with pytest.raises(IntegrityError):
        session.commit()
