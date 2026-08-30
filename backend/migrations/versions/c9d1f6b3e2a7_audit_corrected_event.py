"""Audit events: add 'corrected' (senders correcting a pending envelope's title/message)."""

from alembic import op

revision = "c9d1f6b3e2a7"
down_revision = "b2e7d4a1c8f3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_audit_events_event", "audit_events", type_="check")
    op.create_check_constraint(
        "ck_audit_events_event",
        "audit_events",
        "event IN ('created', 'sent', 'opened', 'signed', 'reminded', 'completed', 'cancelled', 'declined', "
        "'corrected')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_audit_events_event", "audit_events", type_="check")
    op.create_check_constraint(
        "ck_audit_events_event",
        "audit_events",
        "event IN ('created', 'sent', 'opened', 'signed', 'reminded', 'completed', 'cancelled', 'declined')",
    )
