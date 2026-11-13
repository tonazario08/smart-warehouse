"""Revision writes are confined to the separately reserved M4 migration DB."""

import os

import pytest
from alembic.config import Config
from sqlalchemy import MetaData, create_engine, insert, inspect, text, update
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError, DataError, IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from alembic import command
from tests.test_purchase_request_models import (
    CHECKS,
    INVALID_WORKFLOWS,
    UNIQUES,
    WORKFLOW_COLUMNS,
    fulfilled_values,
    seed_workflow_rows,
    workflow_values,
)

pytestmark = pytest.mark.postgres
HEAD = "20261110_0006"
PARENT = "20261017_0003"


def validate_migration_pair(value: str, test_value: str) -> tuple[URL, URL]:
    try:
        url, test_url = make_url(value), make_url(test_value)
    except (ArgumentError, TypeError, ValueError):
        raise ValueError("A separate guarded migration database is required.") from None
    pair = (url.host, url.port, url.username, test_url.database, url.database)
    if (
        any(
            set(candidate.query) - {"connect_timeout"}
            or (candidate.query and candidate.query.get("connect_timeout") != "5")
            for candidate in (url, test_url)
        )
        or url.drivername != "postgresql+psycopg"
        or test_url.drivername != url.drivername
        or (test_url.host, test_url.port, test_url.username) != (url.host, url.port, url.username)
        or pair
        not in {
            (
                "127.0.0.1",
                18545,
                "sw_m4_requests_test",
                "sw_m4_requests_test",
                "sw_m4_requests_migration_test",
            ),
            (
                "127.0.0.1",
                18546,
                "sw_m5_demand_test",
                "sw_m5_demand_test",
                "sw_m5_demand_migration_test",
            ),
            (
                "127.0.0.1",
                18547,
                "sw_m7_replenishment_test",
                "sw_m7_replenishment_test",
                "sw_m7_replenishment_migration_test",
            ),
        }
    ):
        raise ValueError("A separate guarded migration database is required.")
    return url, test_url


@pytest.fixture
def purchase_migration_target(postgres_url):
    value = os.environ.get("TEST_MIGRATION_DATABASE_URL", "")
    try:
        url, test_url = validate_migration_pair(value, postgres_url)
    except ValueError:
        pytest.fail("A separate guarded M4 migration database is required.", pytrace=False)
    engine = create_engine(value, poolclass=NullPool)
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", value.replace("%", "%%"))
    try:
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT current_database()")) == url.database
            assert connection.scalar(text("SELECT current_user")) == url.username
            assert (
                connection.scalar(
                    text(
                        "SELECT pg_get_userbyid(datdba) FROM pg_database "
                        "WHERE datname=current_database()"
                    )
                )
                == url.username
            )
            assert (
                connection.scalar(
                    text(
                        "SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() "
                        "AND pid <> pg_backend_pid()"
                    )
                )
                == 0
            ), "Migration DB must be exclusively reserved."
        command.downgrade(config, "base")
        try:
            yield config, engine
        finally:
            # Only these fixture identities can contain M4 evidence. Remove it
            # deliberately before the guarded revision teardown, never bypass it.
            with engine.begin() as connection:
                if "purchase_request_workflows" in inspect(connection).get_table_names():
                    connection.execute(
                        text(
                            "DELETE FROM purchase_request_workflows "
                            "WHERE purchase_request_id IN (1,2,3,4)"
                        )
                    )
                    connection.execute(
                        text(
                            "DELETE FROM movement_provenance WHERE transaction_id IN (1,2) "
                            "AND purpose='purchase_request_fulfillment'"
                        )
                    )
            command.downgrade(config, "base")
            command.upgrade(config, "head")
    finally:
        engine.dispose()


def require_workflow(engine):
    assert "purchase_request_workflows" in inspect(engine).get_table_names()
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == HEAD


def reflected_workflow(engine):
    require_workflow(engine)
    metadata = MetaData()
    metadata.reflect(engine)
    return metadata.tables["purchase_request_workflows"]


def snapshot(engine):
    with engine.connect() as connection:
        return {
            table: connection.execute(text(f"SELECT * FROM {table} ORDER BY 1")).all()
            for table in (
                "purchase_requests",
                "purchase_request_workflows",
                "stocks",
                "outbounds",
                "transactions",
                "movement_provenance",
                "alembic_version",
            )
        }


def test_legacy_requests_survive_upgrade_readonly(purchase_migration_target):
    config, engine = purchase_migration_target
    command.upgrade(config, PARENT)
    with Session(engine) as session:
        seed_workflow_rows(session)
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO stocks (warehouse_id,product_id,quantity) VALUES (1,1,10)")
        )
        connection.execute(text("UPDATE purchase_requests SET status='approved' WHERE id=2"))
        connection.execute(
            text(
                "INSERT INTO purchase_requests (id,request_number,warehouse_id,product_id,quantity,"
                "status,requested_by_id) VALUES (3,'PR-M4-3',1,1,3,'rejected',1),"
                "(4,'PR-M4-4',1,1,3,'fulfilled',1)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO movement_provenance (transaction_id,purpose,transfer_id) "
                "VALUES (1,'legacy_unknown',NULL),(2,'standard_outbound',NULL)"
            )
        )
        old_rows = {
            table: connection.execute(text(f"SELECT * FROM {table} ORDER BY 1")).all()
            for table in (
                "purchase_requests",
                "stocks",
                "outbounds",
                "transactions",
                "movement_provenance",
            )
        }
    command.upgrade(config, "head")
    require_workflow(engine)
    with engine.connect() as connection:
        for table, rows in old_rows.items():
            assert connection.execute(text(f"SELECT * FROM {table} ORDER BY 1")).all() == rows
        assert connection.scalar(text("SELECT count(*) FROM purchase_request_workflows")) == 0
        assert (
            connection.scalar(
                text(
                    "SELECT count(*) FROM movement_provenance "
                    "WHERE purpose='purchase_request_fulfillment'"
                )
            )
            == 0
        )
    # Read-only API enforcement is a later workstream, not inferred from this DDL test.


def test_empty_downgrade_reupgrade(purchase_migration_target):
    config, engine = purchase_migration_target
    command.upgrade(config, "head")
    require_workflow(engine)
    command.downgrade(config, PARENT)
    inspector = inspect(engine)
    assert "purchase_request_workflows" not in inspector.get_table_names()
    assert not any(
        index["name"].startswith("ix_purchase_requests_")
        for index in inspector.get_indexes("purchase_requests")
    )
    checks = {
        item["name"]: item["sqltext"]
        for item in inspector.get_check_constraints("movement_provenance")
    }
    assert set(checks) == {"ck_provenance_purpose", "ck_provenance_transfer_link"}
    assert all("purchase_request_fulfillment" not in check for check in checks.values())
    command.upgrade(config, "head")
    require_workflow(engine)


@pytest.mark.parametrize("evidence", ["pending_workflow", "fulfilled_workflow", "provenance_only"])
def test_populated_downgrade_preserves_all_evidence(purchase_migration_target, evidence):
    config, engine = purchase_migration_target
    command.upgrade(config, "head")
    table = reflected_workflow(engine)
    with Session(engine) as session:
        seed_workflow_rows(session)
        if evidence != "provenance_only":
            values = workflow_values() if evidence == "pending_workflow" else fulfilled_values()
            session.execute(insert(table), values)
        if evidence != "pending_workflow":
            session.execute(
                text(
                    "INSERT INTO movement_provenance (transaction_id,purpose,transfer_id) "
                    "VALUES (1,'purchase_request_fulfillment',NULL)"
                )
            )
        session.commit()
    before = snapshot(engine)
    checks = inspect(engine).get_check_constraints("movement_provenance")
    with pytest.raises(RuntimeError, match="Cannot downgrade.*purchase request"):
        command.downgrade(config, PARENT)
    assert snapshot(engine) == before
    assert inspect(engine).get_check_constraints("movement_provenance") == checks
    assert {item["name"] for item in inspect(engine).get_check_constraints(table.name)} == CHECKS


def test_deployed_workflow_schema_and_indexes(purchase_migration_target):
    config, engine = purchase_migration_target
    command.upgrade(config, "head")
    table = reflected_workflow(engine)
    inspector = inspect(engine)
    assert set(table.columns.keys()) == WORKFLOW_COLUMNS
    assert [column.name for column in table.primary_key] == ["purchase_request_id"]
    assert {item["name"] for item in inspector.get_check_constraints(table.name)} == CHECKS
    assert {item["name"] for item in inspector.get_unique_constraints(table.name)} == UNIQUES
    keys = inspector.get_foreign_keys(table.name)
    assert len(keys) == 6
    assert all(key["options"].get("ondelete") == "RESTRICT" for key in keys)
    assert {
        item["name"]: item["column_names"]
        for item in inspector.get_indexes("purchase_requests")
        if not item.get("unique")
    } == {
        "ix_purchase_requests_owner_created_id": ["requested_by_id", "created_at", "id"],
        "ix_purchase_requests_created_id": ["created_at", "id"],
        "ix_purchase_requests_status_created_id": ["status", "created_at", "id"],
    }


def test_deployed_invalid_workflow_rows_are_rejected(purchase_migration_target):
    config, engine = purchase_migration_target
    command.upgrade(config, "head")
    table = reflected_workflow(engine)
    with Session(engine) as session:
        seed_workflow_rows(session)
        for values, constraint in INVALID_WORKFLOWS:
            with pytest.raises((IntegrityError, DataError)) as exc:
                with session.begin_nested():
                    session.execute(insert(table), values)
            # Partial balances also violate fulfillment. PostgreSQL checks the
            # alphabetically-first balance check; both guards must exist.
            expected = constraint
            if (values.get("quantity_before") is None) != (values.get("quantity_after") is None):
                expected = "ck_pr_workflow_balances"
            # varchar(64) rejects overlength even before the fingerprint CHECK.
            if (
                max(values.get("quantity_before") or 0, values.get("quantity_after") or 0)
                > 2147483647
            ):
                assert exc.value.orig.sqlstate == "22003"
            elif len(values["request_fingerprint"]) > 64:
                assert exc.value.orig.sqlstate == "22001"
            else:
                assert exc.value.orig.diag.constraint_name == expected


def test_deployed_uniques_and_foreign_keys(purchase_migration_target):
    config, engine = purchase_migration_target
    command.upgrade(config, "head")
    table = reflected_workflow(engine)
    with Session(engine) as session:
        seed_workflow_rows(session)
        first, second = (
            fulfilled_values(),
            {
                **fulfilled_values(),
                "purchase_request_id": 2,
                "outbound_id": 2,
                "outbound_transaction_id": 2,
            },
        )
        session.execute(insert(table), first)
        session.execute(insert(table), second)
        session.commit()
        for changes, constraint in (
            (
                {"idempotency_key": first["idempotency_key"]},
                "uq_purchase_request_workflows_actor_key",
            ),
            ({"outbound_id": 1}, "uq_purchase_request_workflows_outbound"),
            ({"outbound_transaction_id": 1}, "uq_purchase_request_workflows_transaction"),
        ):
            with pytest.raises(IntegrityError) as exc:
                with session.begin_nested():
                    session.execute(
                        update(table).where(table.c.purchase_request_id == 2).values(**changes)
                    )
            assert exc.value.orig.diag.constraint_name == constraint
        # Same key under another actor is legal at the DB layer; service checks ownership.
        session.execute(
            update(table)
            .where(table.c.purchase_request_id == 2)
            .values(created_by_id=2, idempotency_key=first["idempotency_key"])
        )
        session.commit()
        for field in (
            "purchase_request_id",
            "created_by_id",
            "decided_by_id",
            "fulfilled_by_id",
            "outbound_id",
            "outbound_transaction_id",
        ):
            with pytest.raises(IntegrityError) as exc:
                with session.begin_nested():
                    session.execute(
                        update(table).where(table.c.purchase_request_id == 2).values(**{field: 999})
                    )
            assert exc.value.orig.sqlstate == "23503"
            assert exc.value.orig.diag.constraint_name == f"purchase_request_workflows_{field}_fkey"
        # Isolate workflow RESTRICT from old base-owner/outbound-actor and
        # transaction-outbound FKs. Cross-table parity intentionally belongs to
        # the service, not these deployed referential-integrity tests.
        for actor in (3, 4, 5):
            session.execute(
                text(
                    "INSERT INTO users (id,email,password_hash,role,is_active) "
                    "VALUES (:id,:email,'fixture','admin',true)"
                ),
                {"id": actor, "email": f"m4-fk-{actor}@example.test"},
            )
        session.execute(
            update(table)
            .where(table.c.purchase_request_id == 1)
            .values(created_by_id=3, decided_by_id=4, fulfilled_by_id=5)
        )
        session.execute(text("UPDATE transactions SET outbound_id=2 WHERE id=1"))
        session.commit()
        for target, row_id, field in (
            ("purchase_requests", 1, "purchase_request_id"),
            ("users", 3, "created_by_id"),
            ("users", 4, "decided_by_id"),
            ("users", 5, "fulfilled_by_id"),
            ("outbounds", 1, "outbound_id"),
            ("transactions", 1, "outbound_transaction_id"),
        ):
            with pytest.raises(IntegrityError) as exc:
                with session.begin_nested():
                    session.execute(text(f"DELETE FROM {target} WHERE id=:id"), {"id": row_id})
            assert exc.value.orig.sqlstate == "23503"
            assert exc.value.orig.diag.constraint_name == f"purchase_request_workflows_{field}_fkey"


def test_deployed_new_purpose_requires_null_transfer_link(purchase_migration_target):
    config, engine = purchase_migration_target
    command.upgrade(config, "head")
    reflected_workflow(engine)
    with Session(engine) as session:
        seed_workflow_rows(session)
        session.execute(
            text(
                "INSERT INTO movement_provenance (transaction_id,purpose,transfer_id) "
                "VALUES (1,'purchase_request_fulfillment',NULL)"
            )
        )
        session.commit()
        with pytest.raises(IntegrityError) as exc:
            with session.begin_nested():
                session.execute(
                    text("UPDATE movement_provenance SET transfer_id=999 WHERE transaction_id=1")
                )
        assert exc.value.orig.diag.constraint_name == "ck_provenance_transfer_link"


@pytest.mark.parametrize(
    ("port", "user", "main_db", "migration_db"),
    [
        (18545, "sw_m4_requests_test", "sw_m4_requests_test", "sw_m4_requests_migration_test"),
        (18546, "sw_m5_demand_test", "sw_m5_demand_test", "sw_m5_demand_migration_test"),
        (
            18547,
            "sw_m7_replenishment_test",
            "sw_m7_replenishment_test",
            "sw_m7_replenishment_migration_test",
        ),
    ],
)
def test_migration_pair_keeps_exact_owned_test_targets(port, user, main_db, migration_db):
    prefix = f"postgresql+psycopg://{user}:synthetic@127.0.0.1:{port}/"
    migration, main = validate_migration_pair(prefix + migration_db, prefix + main_db)
    assert migration.database == migration_db and main.database == main_db
    with pytest.raises(ValueError):
        validate_migration_pair(prefix + main_db, prefix + migration_db)
    with pytest.raises(ValueError):
        validate_migration_pair(prefix + migration_db + "?options=unsafe", prefix + main_db)
    with pytest.raises(ValueError):
        validate_migration_pair(
            prefix.replace("127.0.0.1", "localhost") + migration_db, prefix + main_db
        )
