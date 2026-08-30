"""Track when each submitter was first contacted.

The reminder overdue-clock used submission.created_at for every submitter,
which punishes later order groups: a group-2 signer first emailed on day 8
looked "8 days overdue" the next morning and burned the whole reminder
budget in three days. first_notified_at records the first send attempt;
existing contacted rows are backfilled to their submission's created_at
(the best available approximation — for group-1 rows it's exact).
"""

import sqlalchemy as sa
from alembic import op

revision = "e1c5b7a94d20"
down_revision = "d8f2a9c41e57"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("submitters", sa.Column("first_notified_at", sa.DateTime(timezone=True), nullable=True))
    op.execute(
        """
        UPDATE submitters
        SET first_notified_at = submissions.created_at
        FROM submissions
        WHERE submissions.id = submitters.submission_id
          AND submitters.email_status IS NOT NULL
        """,
    )


def downgrade() -> None:
    op.drop_column("submitters", "first_notified_at")
