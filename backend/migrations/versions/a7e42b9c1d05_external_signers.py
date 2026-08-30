"""External signers: users.is_external, submitter token/verification/decline
columns, and 'declined' added to the status/event CHECK constraints."""

import sqlalchemy as sa
from alembic import op

revision = "a7e42b9c1d05"
down_revision = "f3a8c1d97e42"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("is_external", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("submitters", sa.Column("access_uid", sa.String(32), nullable=True))
    op.create_unique_constraint("uq_submitters_access_uid", "submitters", ["access_uid"])
    op.add_column("submitters", sa.Column("verification_code_hash", sa.String(64), nullable=True))
    op.add_column("submitters", sa.Column("verification_code_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("submitters", sa.Column("verification_attempts", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("submitters", sa.Column("declined_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("submitters", sa.Column("decline_reason", sa.String(500), nullable=True))

    op.drop_constraint("ck_submissions_status", "submissions", type_="check")
    op.create_check_constraint(
        "ck_submissions_status",
        "submissions",
        "status IN ('pending', 'completed', 'cancelled', 'declined')",
    )
    op.drop_constraint("ck_submitters_status", "submitters", type_="check")
    op.create_check_constraint(
        "ck_submitters_status",
        "submitters",
        "status IN ('pending', 'opened', 'completed', 'declined')",
    )
    op.drop_constraint("ck_audit_events_event", "audit_events", type_="check")
    op.create_check_constraint(
        "ck_audit_events_event",
        "audit_events",
        "event IN ('created', 'sent', 'opened', 'signed', 'reminded', 'completed', 'cancelled', 'declined')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_audit_events_event", "audit_events", type_="check")
    op.create_check_constraint(
        "ck_audit_events_event",
        "audit_events",
        "event IN ('created', 'sent', 'opened', 'signed', 'reminded', 'completed', 'cancelled')",
    )
    op.drop_constraint("ck_submitters_status", "submitters", type_="check")
    op.create_check_constraint("ck_submitters_status", "submitters", "status IN ('pending', 'opened', 'completed')")
    op.drop_constraint("ck_submissions_status", "submissions", type_="check")
    op.create_check_constraint("ck_submissions_status", "submissions", "status IN ('pending', 'completed', 'cancelled')")
    op.drop_column("submitters", "decline_reason")
    op.drop_column("submitters", "declined_at")
    op.drop_column("submitters", "verification_attempts")
    op.drop_column("submitters", "verification_code_expires_at")
    op.drop_column("submitters", "verification_code_hash")
    op.drop_constraint("uq_submitters_access_uid", "submitters", type_="unique")
    op.drop_column("submitters", "access_uid")
    op.drop_column("users", "is_external")
