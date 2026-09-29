from sqlalchemy import event, func, select
from sqlalchemy.orm import Session

from app.models import Category, Product, Stock, Supplier, User, UserRole, Warehouse
from app.seed import SeedSettings, seed_database


def seed_settings() -> SeedSettings:
    return SeedSettings(
        admin_email="admin@example.com",
        admin_password="admin-password-long",
        warehouse_email="warehouse@example.com",
        warehouse_password="warehouse-password-long",
        client_email="client@example.com",
        client_password="client-password-long",
    )


def test_seed_is_idempotent_and_preserves_users_and_relationships(
    postgres_session: Session,
) -> None:
    settings = seed_settings()
    seed_database(postgres_session, settings)
    first_hashes = {
        user.email: user.password_hash
        for user in postgres_session.scalars(select(User)).all()
    }
    first_counts = tuple(
        postgres_session.scalar(select(func.count()).select_from(model))
        for model in (User, Category, Supplier, Warehouse, Product, Stock)
    )
    assert first_counts == (3, 1, 1, 1, 1, 1)
    admin = postgres_session.scalar(select(User).where(User.email == settings.admin_email))
    assert admin is not None
    admin.role = UserRole.CLIENT
    admin.is_active = False
    postgres_session.flush()
    preserved_admin_hash = admin.password_hash

    seed_database(
        postgres_session,
        SeedSettings(
            admin_email=settings.admin_email,
            admin_password="different-admin-password",
            warehouse_email=settings.warehouse_email,
            warehouse_password="different-warehouse-password",
            client_email=settings.client_email,
            client_password="different-client-password",
        ),
    )

    second_hashes = {
        user.email: user.password_hash
        for user in postgres_session.scalars(select(User)).all()
    }
    second_counts = tuple(
        postgres_session.scalar(select(func.count()).select_from(model))
        for model in (User, Category, Supplier, Warehouse, Product, Stock)
    )
    product = postgres_session.scalar(select(Product))
    stock = postgres_session.scalar(select(Stock))
    preserved_admin = postgres_session.scalar(
        select(User).where(User.email == settings.admin_email)
    )
    assert second_counts == first_counts
    assert second_hashes == first_hashes | {settings.admin_email: preserved_admin_hash}
    assert preserved_admin is not None
    assert preserved_admin.role is UserRole.CLIENT
    assert preserved_admin.is_active is False
    assert product is not None
    assert product.category_id is not None
    assert product.supplier_id is not None
    assert stock is not None and stock.product_id == product.id and stock.warehouse_id is not None


def test_seed_failure_rolls_back_all_inserted_rows(postgres_session: Session) -> None:
    def fail_when_product_is_flushed(session, _flush_context, _instances) -> None:
        if any(isinstance(item, Product) for item in session.new):
            raise RuntimeError("simulated seed failure")

    event.listen(postgres_session, "before_flush", fail_when_product_is_flushed)
    try:
        try:
            seed_database(postgres_session, seed_settings())
        except RuntimeError as error:
            assert str(error) == "simulated seed failure"
        else:
            raise AssertionError("seed failure injection did not run")
    finally:
        event.remove(postgres_session, "before_flush", fail_when_product_is_flushed)

    for model in (User, Category, Supplier, Warehouse, Product, Stock):
        assert postgres_session.scalar(select(func.count()).select_from(model)) == 0
