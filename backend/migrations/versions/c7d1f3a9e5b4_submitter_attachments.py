"""Signer attachment uploads: files collected by "attachment" fields,
scoped to one submitter row and appended to the signed PDF at completion."""

import sqlalchemy as sa
from alembic import op

revision = "c7d1f3a9e5b4"
down_revision = "a9c3e5f7b1d2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "attachments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "submitter_id",
            sa.Integer(),
            sa.ForeignKey("submitters.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("file_key", sa.String(length=1024), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("size", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_attachments_submitter_id", "attachments", ["submitter_id"])


def downgrade() -> None:
    op.drop_index("ix_attachments_submitter_id", table_name="attachments")
    op.drop_table("attachments")
