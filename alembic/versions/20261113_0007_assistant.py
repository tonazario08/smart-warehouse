"""Approved document sections and normalized PostgreSQL full-text index."""

import sqlalchemy as sa

from alembic import op

revision = "20261113_0007"
down_revision = "20261110_0006"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "assistant_sections",
        sa.Column("section_id", sa.String(100), primary_key=True),
        sa.Column("title", sa.String(250), nullable=False),
        sa.Column("version", sa.String(100), nullable=False),
        sa.Column("source", sa.String(500), nullable=False),
        sa.Column("read_role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("normalized", sa.Text(), nullable=False),
        sa.CheckConstraint("read_role IN ('admin', 'warehouse')", name="ck_assistant_read_role"),
    )
    op.create_table(
        "assistant_section_versions",
        sa.Column("section_id", sa.String(100), primary_key=True),
        sa.Column("version", sa.String(100), primary_key=True),
        sa.Column("fingerprint", sa.String(64), nullable=False),
    )
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            "ALTER TABLE assistant_sections ADD COLUMN search_vector tsvector "
            "GENERATED ALWAYS AS (to_tsvector('simple', normalized)) STORED"
        )
        op.execute(
            "CREATE INDEX ix_assistant_sections_search ON assistant_sections "
            "USING gin (search_vector)"
        )


def downgrade():
    op.drop_table("assistant_section_versions")
    op.drop_table("assistant_sections")
