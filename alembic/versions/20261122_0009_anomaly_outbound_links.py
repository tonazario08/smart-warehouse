"""Private provenance links for isolated outbound anomaly demos."""

import sqlalchemy as sa

from alembic import op

revision = "20261122_0009"
down_revision = "20261122_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "anomaly_outbound_links",
        sa.Column(
            "alert_id",
            sa.String(69),
            sa.ForeignKey("anomaly_alerts.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column(
            "transaction_id",
            sa.Integer(),
            sa.ForeignKey("transactions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "outbound_id",
            sa.Integer(),
            sa.ForeignKey("outbounds.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("demo_id", sa.Uuid(), nullable=False),
        sa.Column("bundle_id", sa.String(69), nullable=False),
        sa.Column("source_checksum", sa.String(64), nullable=False),
        sa.Column("source_fingerprint", sa.String(64), nullable=False),
        sa.Column("unit", sa.String(40), nullable=False),
        sa.CheckConstraint(
            "length(bundle_id) = 69 AND substr(bundle_id, 1, 5) = 'ddv1-'",
            name="ck_anomaly_outbound_link_bundle_id",
        ),
        sa.CheckConstraint(
            "length(source_checksum) = 64", name="ck_anomaly_outbound_link_source_checksum"
        ),
        sa.CheckConstraint(
            "length(source_fingerprint) = 64", name="ck_anomaly_outbound_link_source_fingerprint"
        ),
        sa.CheckConstraint("length(trim(unit)) > 0", name="ck_anomaly_outbound_link_unit"),
    )
    for column in ("transaction_id", "outbound_id"):
        op.create_index(f"ix_anomaly_outbound_links_{column}", "anomaly_outbound_links", [column])


def downgrade() -> None:
    op.drop_table("anomaly_outbound_links")
