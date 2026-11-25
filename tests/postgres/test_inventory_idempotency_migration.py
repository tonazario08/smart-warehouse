"""Run destructive revision cycles only in the separately reserved migration database."""

import os
from uuid import uuid4

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text, update
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from alembic import command

pytestmark = pytest.mark.postgres


@pytest.fixture
def migration_target(postgres_url):
    value = os.environ.get("TEST_MIGRATION_DATABASE_URL", "")
    url = make_url(value)
    assert url.drivername == "postgresql+psycopg"
    assert (url.database or "").endswith("_test")
    assert url.database != make_url(postgres_url).database
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", value.replace("%", "%%"))
    engine = create_engine(value)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT current_database()")) == url.database
    command.downgrade(config, "base")
    try:
        yield config, engine
    finally:
        command.downgrade(config, "base")
        command.upgrade(config, "head")
        engine.dispose()


def test_fresh_inventory_idempotency_upgrade_and_controlled_downgrade(migration_target):
    config, engine = migration_target
    command.upgrade(config, "20261122_0012")
    inspector = inspect(engine)
    assert "idempotency_key" not in {
        column["name"] for column in inspector.get_columns("inbounds")
    }
    command.upgrade(config, "head")
    inspector = inspect(engine)
    for table in ("inbounds", "outbounds"):
        assert {"idempotency_key", "request_fingerprint"} <= {
            column["name"] for column in inspector.get_columns(table)
        }
        assert {item["name"] for item in inspector.get_unique_constraints(table)} == {
            f"uq_{table}_actor_key"
        }
    command.downgrade(config, "20261122_0012")
    inspector = inspect(engine)
    for table in ("inbounds", "outbounds"):
        assert {"idempotency_key", "request_fingerprint"}.isdisjoint(
            {column["name"] for column in inspector.get_columns(table)}
        )
        assert inspector.get_unique_constraints(table) == []
    command.upgrade(config, "head")
    inspector = inspect(engine)
    for table in ("inbounds", "outbounds"):
        assert {item["name"] for item in inspector.get_unique_constraints(table)} == {
            f"uq_{table}_actor_key"
        }


def test_historical_movements_survive_upgrade_with_null_keys(migration_target):
    config, engine = migration_target
    command.upgrade(config, "20261122_0012")
    statements = [
        "INSERT INTO users (id,email,password_hash,role,is_active) "
        "VALUES (1,'migration@example.test','fixture','warehouse',true)",
        "INSERT INTO categories (id,name) VALUES (1,'Historical')",
        "INSERT INTO products (id,sku,name,category_id,unit) "
        "VALUES (1,'HISTORY','Historical',1,'each')",
        "INSERT INTO warehouses (id,code,name,address) VALUES (1,'HIST-A','History A','Fixture')",
        "INSERT INTO stocks (warehouse_id,product_id,quantity) VALUES (1,1,10)",
        "INSERT INTO inbounds (id,warehouse_id,product_id,quantity,created_by_id,note) "
        "VALUES (1,1,1,12,1,'legacy inbound')",
        "INSERT INTO outbounds (id,warehouse_id,product_id,quantity,created_by_id,note) "
        "VALUES (1,1,1,2,1,'legacy outbound')",
    ]
    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))
        before = {
            table: connection.execute(text(f"SELECT * FROM {table} ORDER BY id")).all()
            for table in ["inbounds", "outbounds"]
        }
    command.upgrade(config, "head")
    with engine.connect() as connection:
        for table, rows in before.items():
            after = [
                tuple(row)
                for row in connection.execute(
                    text(f"SELECT * FROM {table} ORDER BY id")
                ).all()
            ]
            assert after == [(*tuple(row), None, None) for row in rows]
        assert connection.scalar(text("SELECT count(*) FROM inbounds")) == 1
        assert connection.scalar(text("SELECT count(*) FROM outbounds")) == 1


def test_deployed_inventory_idempotency_constraints_match_portable_metadata(
    migration_target,
):
    from app.models import Inbound, Outbound

    config, engine = migration_target
    command.upgrade(config, "head")
    with Session(engine) as session:
        session.execute(
            text(
                "INSERT INTO users (id,email,password_hash,role,is_active) "
                "VALUES (1,'migration@example.test','fixture','warehouse',true)"
            )
        )
        session.execute(text("INSERT INTO categories (id,name) VALUES (1,'Historical')"))
        session.execute(
            text(
                "INSERT INTO products (id,sku,name,category_id,unit) "
                "VALUES (1,'HISTORY','Historical',1,'each')"
            )
        )
        session.execute(
            text(
                "INSERT INTO warehouses (id,code,name,address) "
                "VALUES (1,'HIST-A','History A','Fixture')"
            )
        )
        session.commit()
        first_key, second_key = uuid4(), uuid4()
        session.add_all([
            Inbound(
                warehouse_id=1,
                product_id=1,
                quantity=2,
                created_by_id=1,
                idempotency_key=first_key,
                request_fingerprint="a" * 64,
            ),
            Inbound(
                warehouse_id=1,
                product_id=1,
                quantity=3,
                created_by_id=1,
                idempotency_key=second_key,
                request_fingerprint="b" * 64,
            ),
            Outbound(
                warehouse_id=1,
                product_id=1,
                quantity=1,
                created_by_id=1,
                idempotency_key=first_key,
                request_fingerprint="c" * 64,
            ),
            Outbound(
                warehouse_id=1,
                product_id=1,
                quantity=1,
                created_by_id=1,
                idempotency_key=second_key,
                request_fingerprint="e" * 64,
            ),
        ])
        session.commit()
        # The same key on the other table is independent (both rows above
        # already share first_key across tables).
        # The same key for a different actor is independent too.
        session.execute(
            text(
                "INSERT INTO users (id,email,password_hash,role,is_active) "
                "VALUES (2,'other-migration@example.test','fixture','warehouse',true)"
            )
        )
        session.add(
            Inbound(
                warehouse_id=1,
                product_id=1,
                quantity=4,
                created_by_id=2,
                idempotency_key=first_key,
                request_fingerprint="d" * 64,
            )
        )
        session.commit()
        # Rows without a key never conflict with each other (legacy data).
        session.add_all([
            Inbound(warehouse_id=1, product_id=1, quantity=5, created_by_id=1),
            Inbound(warehouse_id=1, product_id=1, quantity=6, created_by_id=1),
        ])
        session.commit()
        # Same actor + same key on the same table violates the constraint.
        with pytest.raises(IntegrityError) as exc:
            with session.begin_nested():
                session.execute(
                    update(Inbound)
                    .where(Inbound.idempotency_key == second_key)
                    .values(idempotency_key=first_key)
                )
        assert exc.value.orig.diag.constraint_name == "uq_inbounds_actor_key"
        with pytest.raises(IntegrityError) as exc:
            with session.begin_nested():
                session.execute(
                    update(Outbound)
                    .where(Outbound.idempotency_key == second_key)
                    .values(idempotency_key=first_key)
                )
        assert exc.value.orig.diag.constraint_name == "uq_outbounds_actor_key"
