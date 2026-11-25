"""Add durable customer request workflow without inventing legacy history.

Revision ID: 20261019_0004
Revises: 20261017_0003
"""

import sqlalchemy as sa

from alembic import op

revision = "20261019_0004"
down_revision = "20261017_0003"
branch_labels = None
depends_on = None

OLD_PURPOSE = (
    "purpose IN ('legacy_unknown', 'standard_inbound', 'standard_outbound', "
    "'transfer_in', 'transfer_out')"
)
OLD_LINK = (
    "(purpose IN ('transfer_in', 'transfer_out') AND transfer_id IS NOT NULL) OR "
    "(purpose IN ('legacy_unknown', 'standard_inbound', 'standard_outbound') "
    "AND transfer_id IS NULL)"
)
NEW_PURPOSE = (
    "purpose IN ('legacy_unknown', 'standard_inbound', 'standard_outbound', "
    "'transfer_in', 'transfer_out', 'purchase_request_fulfillment')"
)
NEW_LINK = (
    "(purpose IN ('transfer_in', 'transfer_out') AND transfer_id IS NOT NULL) OR "
    "(purpose IN ('legacy_unknown', 'standard_inbound', 'standard_outbound', "
    "'purchase_request_fulfillment') AND transfer_id IS NULL)"
)


def replace_provenance_checks(purpose: str, link: str) -> None:
    # Batch mode recreates only this sidecar on SQLite; PostgreSQL uses ALTER.
    with op.batch_alter_table(
        "movement_provenance", reflect_kwargs={"resolve_fks": False}
    ) as batch:
        batch.drop_constraint("ck_provenance_purpose", type_="check")
        batch.drop_constraint("ck_provenance_transfer_link", type_="check")
        batch.create_check_constraint("ck_provenance_purpose", purpose)
        batch.create_check_constraint("ck_provenance_transfer_link", link)


def upgrade() -> None:
    op.create_table(
        "purchase_request_workflows",
        sa.Column(
            "purchase_request_id",
            sa.Integer(),
            sa.ForeignKey("purchase_requests.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column(
            "created_by_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("idempotency_key", sa.Uuid(), nullable=False),
        sa.Column("request_fingerprint", sa.String(64), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("decision_kind", sa.String(8), nullable=True),
        sa.Column(
            "decided_by_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column(
            "fulfilled_by_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("fulfilled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "outbound_id",
            sa.Integer(),
            sa.ForeignKey("outbounds.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "outbound_transaction_id",
            sa.Integer(),
            sa.ForeignKey("transactions.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("quantity_before", sa.Integer(), nullable=True),
        sa.Column("quantity_after", sa.Integer(), nullable=True),
        sa.UniqueConstraint(
            "created_by_id", "idempotency_key", name="uq_purchase_request_workflows_actor_key"
        ),
        sa.UniqueConstraint("outbound_id", name="uq_purchase_request_workflows_outbound"),
        sa.UniqueConstraint(
            "outbound_transaction_id", name="uq_purchase_request_workflows_transaction"
        ),
        sa.CheckConstraint(
            "length(request_fingerprint) = 64 AND "
            "length(replace(replace(replace(replace(replace(replace(replace(replace("
            "replace(replace(replace(replace(replace(replace(replace(replace("
            "request_fingerprint,'0',''),'1',''),'2',''),'3',''),'4',''),'5',''),'6',''),"
            "'7',''),'8',''),'9',''),'a',''),'b',''),'c',''),'d',''),'e',''),'f','')) = 0",
            name="ck_pr_workflow_fingerprint",
        ),
        sa.CheckConstraint("note IS NULL OR length(note) <= 2000", name="ck_pr_workflow_note"),
        sa.CheckConstraint(
            "(decision_kind IS NULL AND decided_by_id IS NULL AND decided_at IS NULL "
            "AND rejection_reason IS NULL) OR "
            "(decision_kind IS NOT NULL AND decision_kind = 'approved' "
            "AND decided_by_id IS NOT NULL AND decided_at IS NOT NULL "
            "AND rejection_reason IS NULL) OR "
            "(decision_kind IS NOT NULL AND decision_kind = 'rejected' "
            "AND decided_by_id IS NOT NULL AND decided_at IS NOT NULL "
            "AND rejection_reason IS NOT NULL AND rejection_reason = trim(rejection_reason, "
            "'\t\n\v\f\r\x1c\x1d\x1e\x1f \x85\xa0\u1680\u2000\u2001\u2002\u2003\u2004\u2005"
            "\u2006\u2007\u2008\u2009\u200a\u2028\u2029\u202f\u205f\u3000') "
            "AND length(rejection_reason) BETWEEN 1 AND 1000)",
            name="ck_pr_workflow_decision",
        ),
        sa.CheckConstraint(
            "(fulfilled_by_id IS NULL AND fulfilled_at IS NULL AND outbound_id IS NULL "
            "AND outbound_transaction_id IS NULL "
            "AND quantity_before IS NULL AND quantity_after IS NULL) OR "
            "(fulfilled_by_id IS NOT NULL AND fulfilled_at IS NOT NULL AND outbound_id IS NOT NULL "
            "AND outbound_transaction_id IS NOT NULL AND quantity_before IS NOT NULL "
            "AND quantity_after IS NOT NULL AND decision_kind IS NOT NULL "
            "AND decision_kind = 'approved')",
            name="ck_pr_workflow_fulfillment",
        ),
        sa.CheckConstraint(
            "(quantity_before IS NULL AND quantity_after IS NULL) OR "
            "(quantity_before IS NOT NULL AND quantity_after IS NOT NULL "
            "AND quantity_after >= 0 AND quantity_after < quantity_before "
            "AND quantity_before <= 2147483647)",
            name="ck_pr_workflow_balances",
        ),
    )
    op.create_index(
        "ix_purchase_requests_owner_created_id",
        "purchase_requests",
        ["requested_by_id", "created_at", "id"],
    )
    op.create_index("ix_purchase_requests_created_id", "purchase_requests", ["created_at", "id"])
    op.create_index(
        "ix_purchase_requests_status_created_id",
        "purchase_requests",
        ["status", "created_at", "id"],
    )
    replace_provenance_checks(NEW_PURPOSE, NEW_LINK)


def downgrade() -> None:
    connection = op.get_bind()
    if connection.dialect.name == "postgresql":
        # Held through both evidence checks and destructive DDL in the same
        # transaction: no concurrent insert can slip between check and drop.
        connection.execute(
            sa.text(
                "LOCK TABLE purchase_request_workflows, movement_provenance "
                "IN ACCESS EXCLUSIVE MODE"
            )
        )
    workflows = connection.scalar(
        sa.text("SELECT EXISTS (SELECT 1 FROM purchase_request_workflows)")
    )
    provenance = connection.scalar(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM movement_provenance "
            "WHERE purpose='purchase_request_fulfillment')"
        )
    )
    if workflows or provenance:
        raise RuntimeError("Cannot downgrade: managed purchase request evidence must be preserved.")
    replace_provenance_checks(OLD_PURPOSE, OLD_LINK)
    op.drop_index("ix_purchase_requests_status_created_id", table_name="purchase_requests")
    op.drop_index("ix_purchase_requests_created_id", table_name="purchase_requests")
    op.drop_index("ix_purchase_requests_owner_created_id", table_name="purchase_requests")
    op.drop_table("purchase_request_workflows")
