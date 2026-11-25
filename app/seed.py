from __future__ import annotations

import os
import sys
from dataclasses import dataclass

from argon2 import PasswordHasher
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.engine import Engine, create_engine, make_url
from sqlalchemy.exc import ArgumentError
from sqlalchemy.orm import Session

from app.auth.schemas import RegisterRequest
from app.models import Category, Product, Stock, Supplier, User, UserRole, Warehouse


@dataclass(frozen=True)
class SeedSettings:
    """Credentials used only when a seeded user is first created."""

    admin_email: str
    admin_password: str
    warehouse_email: str
    warehouse_password: str
    client_email: str
    client_password: str


def load_seed_settings(environment: dict[str, str] | None = None) -> SeedSettings:
    """Read the required seed credentials without providing unsafe defaults."""
    values = os.environ if environment is None else environment
    database_url = values.get("DATABASE_URL", "")
    if not database_url.strip():
        raise ValueError("Missing required seed environment variable: DATABASE_URL")
    try:
        make_url(database_url)
    except ArgumentError as error:
        raise ValueError("DATABASE_URL must be a valid SQLAlchemy URL") from error

    required_names = (
        "SEED_ADMIN_EMAIL",
        "SEED_ADMIN_PASSWORD",
        "SEED_WAREHOUSE_EMAIL",
        "SEED_WAREHOUSE_PASSWORD",
        "SEED_CLIENT_EMAIL",
        "SEED_CLIENT_PASSWORD",
    )
    missing = [name for name in required_names if not values.get(name, "").strip()]
    if missing:
        raise ValueError(f"Missing required seed environment variables: {', '.join(missing)}")

    normalized = _validated_credentials(values)
    return SeedSettings(
        admin_email=normalized["SEED_ADMIN_EMAIL"],
        admin_password=values["SEED_ADMIN_PASSWORD"],
        warehouse_email=normalized["SEED_WAREHOUSE_EMAIL"],
        warehouse_password=values["SEED_WAREHOUSE_PASSWORD"],
        client_email=normalized["SEED_CLIENT_EMAIL"],
        client_password=values["SEED_CLIENT_PASSWORD"],
    )


def _validated_credentials(values: dict[str, str]) -> dict[str, str]:
    """Normalize emails and apply the registration password policy without echoing values."""
    normalized: dict[str, str] = {}
    for email_name, password_name in (
        ("SEED_ADMIN_EMAIL", "SEED_ADMIN_PASSWORD"),
        ("SEED_WAREHOUSE_EMAIL", "SEED_WAREHOUSE_PASSWORD"),
        ("SEED_CLIENT_EMAIL", "SEED_CLIENT_PASSWORD"),
    ):
        try:
            request = RegisterRequest.model_validate(
                {"email": values[email_name], "password": values[password_name]}
            )
        except ValidationError as error:
            fields = {item["loc"][0] for item in error.errors()}
            if "email" in fields:
                raise ValueError(f"{email_name} must be a valid email address") from None
            raise ValueError(f"{password_name} must contain 12 to 128 characters") from None
        normalized[email_name] = request.email
    if len(set(normalized.values())) != len(normalized):
        raise ValueError("Seed role email addresses must be distinct")
    return normalized


def _get_or_create_user(
    session: Session, password_hasher: PasswordHasher, email: str, password: str, role: UserRole
) -> User:
    user = session.scalar(select(User).where(User.email == email))
    if user is not None:
        if user.role is not role:
            raise ValueError(
                f"Existing seed user has role {user.role.value}; expected role {role.value}"
            )
        return user

    user = User(email=email, password_hash=password_hasher.hash(password), role=role)
    session.add(user)
    session.flush()
    return user


def seed_database(session: Session, settings: SeedSettings) -> None:
    """Create the fixed development dataset once, preserving existing records."""
    settings = _validate_seed_settings(settings)
    password_hasher = PasswordHasher()

    with session.begin_nested():
        _get_or_create_user(
            session,
            password_hasher,
            settings.admin_email,
            settings.admin_password,
            UserRole.ADMIN,
        )
        _get_or_create_user(
            session,
            password_hasher,
            settings.warehouse_email,
            settings.warehouse_password,
            UserRole.WAREHOUSE,
        )
        _get_or_create_user(
            session,
            password_hasher,
            settings.client_email,
            settings.client_password,
            UserRole.CLIENT,
        )

        category = session.scalar(select(Category).where(Category.name == "General Merchandise"))
        if category is None:
            category = Category(name="General Merchandise")
            session.add(category)
            session.flush()

        supplier = session.scalar(select(Supplier).where(Supplier.name == "Smart Warehouse Supply"))
        if supplier is None:
            supplier = Supplier(
                name="Smart Warehouse Supply",
                email="supply@example.com",
                phone="+84-28-0000-0000",
            )
            session.add(supplier)
            session.flush()

        warehouse = session.scalar(select(Warehouse).where(Warehouse.code == "HCM-01"))
        if warehouse is None:
            warehouse = Warehouse(
                code="HCM-01",
                name="Ho Chi Minh Central Warehouse",
                address="1 Nguyen Hue, Ho Chi Minh City",
            )
            session.add(warehouse)
            session.flush()

        product = session.scalar(select(Product).where(Product.sku == "DEMO-001"))
        if product is None:
            product = Product(
                sku="DEMO-001",
                name="Demo Inventory Item",
                category=category,
                supplier=supplier,
                unit="each",
                reorder_level=10,
            )
            session.add(product)
            session.flush()

        stock = session.scalar(
            select(Stock).where(Stock.warehouse_id == warehouse.id, Stock.product_id == product.id)
        )
        if stock is None:
            session.add(Stock(warehouse=warehouse, product=product, quantity=25))


def _validate_seed_settings(settings: SeedSettings) -> SeedSettings:
    """Apply the same email and password contract used by registration before database work."""
    values = {
        "SEED_ADMIN_EMAIL": settings.admin_email,
        "SEED_ADMIN_PASSWORD": settings.admin_password,
        "SEED_WAREHOUSE_EMAIL": settings.warehouse_email,
        "SEED_WAREHOUSE_PASSWORD": settings.warehouse_password,
        "SEED_CLIENT_EMAIL": settings.client_email,
        "SEED_CLIENT_PASSWORD": settings.client_password,
    }
    required_names = tuple(values)
    missing = [name for name in required_names if not values[name].strip()]
    if missing:
        raise ValueError(f"Missing required seed environment variables: {', '.join(missing)}")
    normalized = _validated_credentials(values)
    return SeedSettings(
        admin_email=normalized["SEED_ADMIN_EMAIL"],
        admin_password=values["SEED_ADMIN_PASSWORD"],
        warehouse_email=normalized["SEED_WAREHOUSE_EMAIL"],
        warehouse_password=values["SEED_WAREHOUSE_PASSWORD"],
        client_email=normalized["SEED_CLIENT_EMAIL"],
        client_password=values["SEED_CLIENT_PASSWORD"],
    )


def create_engine_from_environment(environment: dict[str, str] | None = None) -> Engine:
    """Create the seed command's database engine from its required URL."""
    values = os.environ if environment is None else environment
    database_url = values.get("DATABASE_URL")
    if not database_url or not database_url.strip():
        raise ValueError("Missing required seed environment variable: DATABASE_URL")
    try:
        make_url(database_url)
    except ArgumentError as error:
        raise ValueError("DATABASE_URL must be a valid SQLAlchemy URL") from error
    return create_engine(database_url)


def main() -> int:
    """Run an idempotent seed against the configured database."""
    engine: Engine | None = None
    try:
        settings = load_seed_settings()
        engine = create_engine_from_environment()
        with Session(engine) as session:
            seed_database(session, settings)
            session.commit()
    except ValueError as error:
        print(f"Seed failed: {error}", file=sys.stderr)
        return 1
    except Exception:
        print("Seed failed because the database operation could not be completed.", file=sys.stderr)
        return 1
    finally:
        if engine is not None:
            engine.dispose()

    print("Seed completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
