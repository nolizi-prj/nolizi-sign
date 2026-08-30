"""Envelope expiration: optional deadline, warning bookkeeping, "expired" status.

expires_at is the sender-chosen deadline (NULL = never expires, the previous
behavior for every existing envelope). expiry_warned_at records that the
"expiring soon" warning went out so the daily sweep sends it exactly once.
The submissions status CHECK and audit-event CHECK are recreated to admit
the new "expired" value.
"""

import sqlalchemy as sa
from alembic import op

revision = "f2a6b8c1d4e0"
down_revision = "e1c5b7a94d20"
branch_labels = None
depends_on = None

_OLD_STATUSES = "('pending', 'completed', 'cancelled', 'declined')"
_NEW_STATUSES = "('pending', 'completed', 'cancelled', 'declined', 'expired')"
_OLD_EVENTS = "('created', 'sent', 'opened', 'signed', 'reminded', 'completed', 'cancelled', 'declined', 'corrected')"
_NEW_EVENTS = (
    "('created', 'sent', 'opened', 'signed', 'reminded', 'completed', 'cancelled', 'declined', 'corrected', 'expired')"
)


def upgrade() -> None:
    op.add_column("submissions", sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("submissions", sa.Column("expiry_warned_at", sa.DateTime(timezone=True), nullable=True))
    op.drop_constraint("ck_submissions_status", "submissions", type_="check")
    op.create_check_constraint("ck_submissions_status", "submissions", f"status IN {_NEW_STATUSES}")
    op.drop_constraint("ck_audit_events_event", "audit_events", type_="check")
    op.create_check_constraint("ck_audit_events_event", "audit_events", f"event IN {_NEW_EVENTS}")


def downgrade() -> None:
    op.drop_constraint("ck_audit_events_event", "audit_events", type_="check")
    op.create_check_constraint("ck_audit_events_event", "audit_events", f"event IN {_OLD_EVENTS}")
    op.drop_constraint("ck_submissions_status", "submissions", type_="check")
    op.create_check_constraint("ck_submissions_status", "submissions", f"status IN {_OLD_STATUSES}")
    op.drop_column("submissions", "expiry_warned_at")
    op.drop_column("submissions", "expires_at")
