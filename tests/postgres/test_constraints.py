from __future__ import annotations

import pytest
from alembic.config import Config
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from alembic import command
from app.models import (
    Category,
    Inbound,
    Outbound,
    Product,
    StockTransaction,
    TransactionType,
    User,
    UserRole,
    Warehouse,
)

pytestmark = pytest.mark.postgres


@pytest.fixture(scope="module", autouse=True)
def migrate_to_head(postgres_url: str) -> None:
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", postgres_url)
    command.upgrade(config, "head")


def make_user(email: str = "operator@example.com") -> User:
    return User(email=email, password_hash="test-hash", role=UserRole.WAREHOUSE)


def test_normalized_email_is_unique_case_insensitively(postgres_session: Session) -> None:
    postgres_session.add_all(
        [make_user("client@example.com"), make_user("CLIENT@example.com")]
    )
    with pytest.raises(IntegrityError):
        postgres_session.commit()


def test_sku_is_unique_case_insensitively(postgres_session: Session) -> None:
    category = Category(name="Fasteners")
    postgres_session.add(category)
    postgres_session.flush()
    postgres_session.add_all(
        [
            Product(
                sku="sku-001",
                name="Bolt",
                category_id=category.id,
                unit="piece",
            ),
            Product(
                sku="SKU-001",
                name="Nut",
                category_id=category.id,
                unit="piece",
            ),
        ]
    )
    with pytest.raises(IntegrityError):
        postgres_session.commit()


def test_warehouse_code_is_stored_in_normalized_form(postgres_session: Session) -> None:
    postgres_session.add(Warehouse(code="hcm-01", name="Central", address="1 Nguyen Hue"))
    with pytest.raises(IntegrityError):
        postgres_session.commit()


@pytest.mark.parametrize(
    ("latitude", "longitude"),
    [(91, 10), (-91, 10), (10, 181), (10, -181), (91, None), (None, 10)],
)
def test_warehouse_rejects_unpaired_or_out_of_range_coordinates(
    postgres_session: Session, latitude: float | None, longitude: float | None
) -> None:
    postgres_session.add(
        Warehouse(
            code="HCM-01",
            name="Central",
            address="1 Nguyen Hue",
            latitude=latitude,
            longitude=longitude,
        )
    )
    with pytest.raises(IntegrityError):
        postgres_session.commit()


@pytest.fixture
def movement_rows(postgres_session: Session) -> tuple[User, Warehouse, Product, Inbound, Outbound]:
    user = make_user()
    category = Category(name="Fasteners")
    warehouse = Warehouse(code="HCM-01", name="Central", address="1 Nguyen Hue")
    postgres_session.add_all([user, category, warehouse])
    postgres_session.flush()
    product = Product(
        sku="SKU-001",
        name="Bolt",
        category_id=category.id,
        unit="piece",
    )
    postgres_session.add(product)
    postgres_session.flush()
    inbound = Inbound(
        warehouse_id=warehouse.id,
        product_id=product.id,
        quantity=5,
        created_by_id=user.id,
    )
    outbound = Outbound(
        warehouse_id=warehouse.id,
        product_id=product.id,
        quantity=2,
        created_by_id=user.id,
    )
    postgres_session.add_all([inbound, outbound])
    postgres_session.flush()
    return user, warehouse, product, inbound, outbound


@pytest.mark.parametrize(
    ("transaction_type", "inbound_id", "outbound_id"),
    [
        (TransactionType.INBOUND, None, None),
        (TransactionType.INBOUND, 1, 1),
        (TransactionType.OUTBOUND, 1, None),
        (TransactionType.INBOUND, None, 1),
    ],
)
def test_stock_transaction_requires_exactly_one_matching_movement(
    postgres_session: Session,
    movement_rows: tuple[User, Warehouse, Product, Inbound, Outbound],
    transaction_type: TransactionType,
    inbound_id: int | None,
    outbound_id: int | None,
) -> None:
    user, warehouse, product, inbound, outbound = movement_rows
    postgres_session.add(
        StockTransaction(
            transaction_type=transaction_type,
            warehouse_id=warehouse.id,
            product_id=product.id,
            quantity=1,
            inbound_id=inbound.id if inbound_id is not None else None,
            outbound_id=outbound.id if outbound_id is not None else None,
            created_by_id=user.id,
        )
    )
    with pytest.raises(IntegrityError):
        postgres_session.commit()
