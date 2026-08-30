"""Draft envelopes: a "draft" submission status for envelopes saved from the
send wizard but not yet dispatched — no recipient has been emailed and the
signing routes 404 for them until POST /send flips them to pending."""

from alembic import op

revision = "b5e9d2c7a3f1"
down_revision = "c7d1f3a9e5b4"
branch_labels = None
depends_on = None

_OLD_STATUSES = "('pending', 'completed', 'cancelled', 'declined', 'expired')"
_NEW_STATUSES = "('draft', 'pending', 'completed', 'cancelled', 'declined', 'expired')"


def upgrade() -> None:
    op.drop_constraint("ck_submissions_status", "submissions", type_="check")
    op.create_check_constraint("ck_submissions_status", "submissions", f"status IN {_NEW_STATUSES}")


def downgrade() -> None:
    op.drop_constraint("ck_submissions_status", "submissions", type_="check")
    op.create_check_constraint("ck_submissions_status", "submissions", f"status IN {_OLD_STATUSES}")
