"""Run destructive revision cycles only in the separately reserved migration database."""

import os

import pytest
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

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


def test_fresh_transfer_upgrade_and_controlled_downgrade(migration_target):
    config, engine = migration_target
    command.upgrade(config, "head")
    assert {"stock_transfers", "movement_provenance"} <= set(inspect(engine).get_table_names())
    command.downgrade(config, "20260904_0002")
    assert {"stock_transfers", "movement_provenance"}.isdisjoint(inspect(engine).get_table_names())
    command.upgrade(config, "head")
    assert {"stock_transfers", "movement_provenance"} <= set(inspect(engine).get_table_names())


def test_historical_balances_and_movements_survive_with_honest_unknown_provenance(migration_target):
    config, engine = migration_target
    command.upgrade(config, "20260904_0002")
    statements = [
        "INSERT INTO users (id,email,password_hash,role,is_active) "
        "VALUES (1,'migration@example.test','fixture','warehouse',true)",
        "INSERT INTO categories (id,name) VALUES (1,'Historical')",
        "INSERT INTO products (id,sku,name,category_id,unit) "
        "VALUES (1,'HISTORY','Historical',1,'each')",
        "INSERT INTO warehouses (id,code,name,address) VALUES (1,'HIST-A','History A','Fixture'),"
        "(2,'HIST-B','History B','Fixture')",
        "INSERT INTO stocks (warehouse_id,product_id,quantity) VALUES (1,1,10),(2,1,2)",
        "INSERT INTO inbounds (id,warehouse_id,product_id,quantity,created_by_id,note) "
        "VALUES (1,1,1,12,1,'transfer? never infer from note')",
        "INSERT INTO outbounds (id,warehouse_id,product_id,quantity,created_by_id,note) "
        "VALUES (1,1,1,2,1,'sale? unknown')",
        "INSERT INTO transactions (id,transaction_type,warehouse_id,product_id,quantity,"
        "created_by_id,inbound_id,outbound_id) VALUES (1,'inbound',1,1,12,1,1,NULL),"
        "(2,'outbound',1,1,2,1,NULL,1)",
    ]
    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))
        before = {
            table: connection.execute(text(f"SELECT * FROM {table} ORDER BY id")).all()
            for table in ["stocks", "inbounds", "outbounds", "transactions"]
        }
    command.upgrade(config, "head")
    assert "movement_provenance" in inspect(engine).get_table_names()
    with engine.connect() as connection:
        for table, rows in before.items():
            assert connection.execute(text(f"SELECT * FROM {table} ORDER BY id")).all() == rows
        assert connection.execute(
            text(
                "SELECT transaction_id,purpose,transfer_id FROM movement_provenance "
                "ORDER BY transaction_id"
            )
        ).all() == [(1, "legacy_unknown", None), (2, "legacy_unknown", None)]
        assert connection.scalar(text("SELECT count(*) FROM stock_transfers")) == 0


def test_deployed_transfer_constraints_match_portable_metadata(migration_target):
    from uuid import uuid4

    from sqlalchemy import delete, update
    from sqlalchemy.exc import IntegrityError
    from sqlalchemy.orm import Session

    from app.models import Inbound, MovementProvenance, StockTransfer
    from app.transfers.repository import TransferRepository
    from app.transfers.service import TransferService

    from .test_transfer_atomicity import request_for, seed_transfer

    config, engine = migration_target
    command.upgrade(config, "head")
    inspector = inspect(engine)
    assert {item["name"] for item in inspector.get_check_constraints("stock_transfers")} == {
        "ck_transfers_distinct_warehouses",
        "ck_transfers_quantity_bounds",
        "ck_transfers_balance_bounds",
    }
    assert {item["name"] for item in inspector.get_unique_constraints("stock_transfers")} == {
        "uq_transfers_actor_key",
        "uq_transfers_outbound",
        "uq_transfers_inbound",
        "uq_transfers_outbound_transaction",
        "uq_transfers_inbound_transaction",
    }
    for table, count in [("stock_transfers", 8), ("movement_provenance", 2)]:
        keys = inspector.get_foreign_keys(table)
        assert len(keys) == count
        assert all(key["options"].get("ondelete") == "RESTRICT" for key in keys)
    with Session(engine) as session:
        ids = seed_transfer(session)
        service = TransferService(TransferRepository(session))
        first, _ = service.create(ids[0], uuid4(), request_for(ids))
        first_id, first_key = first.id, first.idempotency_key
        links = {
            name: getattr(first, name)
            for name in [
                "outbound_id",
                "inbound_id",
                "outbound_transaction_id",
                "inbound_transaction_id",
            ]
        }
        second, _ = service.create(ids[0], uuid4(), request_for(ids, 1))
        for changes, constraint in [
            ({"quantity": 0}, "ck_transfers_quantity_bounds"),
            ({"source_quantity_after": -1}, "ck_transfers_balance_bounds"),
            ({"destination_warehouse_id": ids[1]}, "ck_transfers_distinct_warehouses"),
            ({"idempotency_key": first_key}, "uq_transfers_actor_key"),
            *[
                ({field: value}, "uq_transfers_" + field.removesuffix("_id"))
                for field, value in links.items()
            ],
        ]:
            with pytest.raises(IntegrityError) as exc:
                with session.begin_nested():
                    session.execute(
                        update(StockTransfer).where(StockTransfer.id == second.id).values(**changes)
                    )
            assert exc.value.orig.diag.constraint_name == constraint
        for changes, constraint in [
            ({"purpose": "sales"}, "ck_provenance_purpose"),
            ({"transfer_id": None}, "ck_provenance_transfer_link"),
            ({"purpose": "standard_outbound"}, "ck_provenance_transfer_link"),
        ]:
            with pytest.raises(IntegrityError) as exc:
                with session.begin_nested():
                    session.execute(
                        update(MovementProvenance)
                        .where(MovementProvenance.transfer_id == first_id)
                        .values(**changes)
                    )
            assert exc.value.orig.diag.constraint_name == constraint
        with pytest.raises(IntegrityError) as exc:
            with session.begin_nested():
                session.execute(delete(Inbound).where(Inbound.id == links["inbound_id"]))
        assert exc.value.orig.sqlstate == "23503"
