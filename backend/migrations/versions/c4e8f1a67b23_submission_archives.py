"""Per-user submission archive markers (DocuSign-style delete-is-hide).

A row means "this user archived this envelope out of their own views".
Nothing about the envelope itself changes; other participants are
unaffected. See docs/superpowers/specs/2026-08-09-void-archive-preview-design.md.
"""

import sqlalchemy as sa
from alembic import op

revision = "c4e8f1a67b23"
down_revision = "a1d7e93c50b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "submission_archives",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("submission_id", sa.Integer(), sa.ForeignKey("submissions.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("submission_id", "user_id", name="uq_submission_archives_submission_user"),
    )


def downgrade() -> None:
    op.drop_table("submission_archives")
