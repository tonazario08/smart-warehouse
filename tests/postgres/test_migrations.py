import pytest
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from alembic import command

pytestmark = pytest.mark.postgres


def test_migrations_build_expected_schema(
    postgres_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Upgrade from base and from the original revision both reach production head."""
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", postgres_url)
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://wrong:wrong@localhost:55432/not_the_test_database",
    )
    engine = create_engine(postgres_url)
    try:
        command.downgrade(config, "base")
        command.upgrade(config, "head")
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())
        assert "audit_logs" in tables
        assert {
            "ck_warehouses_coordinates_paired_and_ranged",
            "ck_warehouses_code_normalized",
            "ck_transactions_exactly_one_movement",
        } <= {
            constraint["name"]
            for table in ("warehouses", "transactions")
            for constraint in inspector.get_check_constraints(table)
        }
        assert {
            "uq_users_email_lower",
            "uq_products_sku_upper",
            "uq_warehouses_code_upper",
        } <= {
            index["name"]
            for table in ("users", "products", "warehouses")
            for index in inspector.get_indexes(table)
        }
        assert {
            "ix_audit_logs_actor_user_id",
            "ix_audit_logs_action",
            "ix_audit_logs_target_id",
            "ix_audit_logs_created_at",
        } <= {index["name"] for index in inspector.get_indexes("audit_logs")}

        command.downgrade(config, "20260829_0001")
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO users (email, password_hash, role, is_active) "
                    "VALUES ('  Mixed@Example.COM  ', 'test-hash', 'client', true)"
                )
            )
            connection.execute(text("INSERT INTO categories (name) VALUES ('Fasteners')"))
            connection.execute(
                text(
                    "INSERT INTO products (sku, name, category_id, unit) "
                    "VALUES (' bolt-001 ', 'Bolt', "
                    "(SELECT id FROM categories WHERE name = 'Fasteners'), 'piece')"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO warehouses (code, name, address) "
                    "VALUES (' hcm-01 ', 'Central', '1 Nguyen Hue')"
                )
            )
        command.upgrade(config, "head")
        with engine.connect() as connection:
            revision = connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one()
            normalized_values = (
                connection.execute(text("SELECT email FROM users")).scalar_one(),
                connection.execute(text("SELECT sku FROM products")).scalar_one(),
                connection.execute(text("SELECT code FROM warehouses")).scalar_one(),
            )
        assert revision == "20260904_0002"
        assert normalized_values == ("mixed@example.com", "BOLT-001", "HCM-01")
    finally:
        engine.dispose()

    assert tables == {
        "alembic_version",
        "categories",
        "inbounds",
        "outbounds",
        "products",
        "purchase_requests",
        "regions",
        "route_logs",
        "stocks",
        "suppliers",
        "transactions",
        "users",
        "warehouses",
        "audit_logs",
    }
