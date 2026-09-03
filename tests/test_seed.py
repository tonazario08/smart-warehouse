from pathlib import Path

from alembic.config import Config
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session

from alembic import command
from app.models import Category, Product, Stock, Supplier, User, UserRole, Warehouse
from app.seed import SeedSettings, seed_database


def test_seed_is_idempotent_and_preserves_existing_user_credentials(tmp_path: Path) -> None:
    """Re-running the seed must not duplicate data or replace a user's password hash."""
    database_path = tmp_path / "seed.db"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", f"sqlite:///{database_path}")
    command.upgrade(config, "head")
    engine = create_engine(f"sqlite:///{database_path}")

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, _) -> None:
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    settings = SeedSettings(
        admin_email="admin@example.com",
        admin_password="admin-password",
        warehouse_email="warehouse@example.com",
        warehouse_password="warehouse-password",
        client_email="client@example.com",
        client_password="client-password",
    )

    with Session(engine) as session:
        seed_database(session, settings)
        admin = session.scalar(select(User).where(User.email == settings.admin_email))
        assert admin is not None
        original_password_hash = admin.password_hash

        seed_database(session, settings)

        assert session.scalar(select(func.count()).select_from(User)) == 3
        assert session.scalar(select(func.count()).select_from(Category)) == 1
        assert session.scalar(select(func.count()).select_from(Supplier)) == 1
        assert session.scalar(select(func.count()).select_from(Product)) == 1
        assert session.scalar(select(func.count()).select_from(Warehouse)) == 1
        assert session.scalar(select(func.count()).select_from(Stock)) == 1

        seeded_roles = set(session.scalars(select(User.role)))
        assert seeded_roles == {UserRole.ADMIN, UserRole.WAREHOUSE, UserRole.CLIENT}
        assert session.get(User, admin.id).password_hash == original_password_hash
