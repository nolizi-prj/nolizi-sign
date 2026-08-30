"""Per-envelope reminder settings: an on/off switch and a sender-chosen
interval. Defaults reproduce the previous hard-coded policy (on, every 3
days), so existing envelopes behave exactly as before."""

import sqlalchemy as sa
from alembic import op

revision = "a9c3e5f7b1d2"
down_revision = "f2a6b8c1d4e0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "submissions",
        sa.Column("reminders_enabled", sa.Boolean(), nullable=False, server_default="true"),
    )
    op.add_column(
        "submissions",
        sa.Column("reminder_interval_days", sa.Integer(), nullable=False, server_default="3"),
    )


def downgrade() -> None:
    op.drop_column("submissions", "reminder_interval_days")
    op.drop_column("submissions", "reminders_enabled")
