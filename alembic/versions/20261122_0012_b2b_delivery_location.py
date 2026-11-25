"""Preserve an optional confirmed B2B delivery snapshot with no backfill."""

import sqlalchemy as sa

from alembic import op

revision = "20261122_0012"
down_revision = "20261122_0011"
branch_labels = None
depends_on = None

TABLE = "purchase_request_workflows"
CHECK = "ck_pr_workflow_delivery_location"


PRESENT_TOGETHER = (
    "(delivery_address IS NULL AND delivery_latitude IS NULL AND "
    "delivery_longitude IS NULL) OR "
    "(delivery_address IS NOT NULL AND delivery_latitude IS NOT NULL AND "
    "delivery_longitude IS NOT NULL AND length(trim(delivery_address)) BETWEEN 1 AND 300 "
    "AND delivery_latitude BETWEEN -90 AND 90 AND delivery_longitude BETWEEN -180 AND 180)"
)


def _columns():
    return (
        sa.Column("delivery_address", sa.String(300), nullable=True),
        sa.Column("delivery_latitude", sa.Float(53), nullable=True),
        sa.Column("delivery_longitude", sa.Float(53), nullable=True),
    )


def _sqlite_write_lock(connection):
    if not connection.connection.driver_connection.in_transaction:
        connection.exec_driver_sql("BEGIN IMMEDIATE")
    else:
        # Escalate an existing deferred transaction before checking data or rebuilding.
        # This statement touches no rows.
        connection.exec_driver_sql(
            "UPDATE purchase_request_workflows SET purchase_request_id = purchase_request_id "
            "WHERE 0"
        )


def upgrade() -> None:
    connection = op.get_bind()
    if connection.dialect.name == "sqlite":
        _sqlite_write_lock(connection)
        with op.batch_alter_table(TABLE, reflect_kwargs={"resolve_fks": False}) as batch:
            for column in _columns():
                batch.add_column(column)
            batch.create_check_constraint(CHECK, PRESENT_TOGETHER)
        return
    for column in _columns():
        op.add_column(TABLE, column)
    op.create_check_constraint(CHECK, TABLE, PRESENT_TOGETHER)


def downgrade() -> None:
    connection = op.get_bind()
    sqlite = connection.dialect.name == "sqlite"
    if sqlite:
        _sqlite_write_lock(connection)
    else:
        connection.execute(sa.text(
            "LOCK TABLE purchase_request_workflows IN ACCESS EXCLUSIVE MODE"
        ))
    if connection.scalar(sa.text(
        "SELECT 1 FROM purchase_request_workflows WHERE delivery_address IS NOT NULL LIMIT 1"
    )):
        raise RuntimeError("Cannot downgrade with persisted B2B delivery snapshots.")
    names = ("delivery_longitude", "delivery_latitude", "delivery_address")
    if sqlite:
        with op.batch_alter_table(TABLE, reflect_kwargs={"resolve_fks": False}) as batch:
            batch.drop_constraint(CHECK, type_="check")
            for name in names:
                batch.drop_column(name)
        return
    op.drop_constraint(CHECK, TABLE, type_="check")
    for name in names:
        op.drop_column(TABLE, name)
