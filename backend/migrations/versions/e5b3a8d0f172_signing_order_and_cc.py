"""Signing order (submitters.order_index) and CC recipients (submissions.cc_emails).

Both defaults reproduce pre-feature behavior: every existing submitter sits
in the single parallel group 0, and existing submissions have no CCs.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "e5b3a8d0f172"
down_revision = "c9d1f6b3e2a7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("submitters", sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("submissions", sa.Column("cc_emails", JSONB(), nullable=False, server_default="[]"))


def downgrade() -> None:
    op.drop_column("submissions", "cc_emails")
    op.drop_column("submitters", "order_index")
