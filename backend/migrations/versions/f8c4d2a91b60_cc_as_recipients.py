"""CC recipients become ordered submitter rows (is_cc), replacing cc_emails.

DocuSign-style routing: a CC is a recipient row with an order_index like any
signer — emailed a copy when routing reaches their group, never blocking
completion. The flat submissions.cc_emails list (added in e5b3a8d0f172
earlier the same week, unused in production data) is dropped in favor of it.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "f8c4d2a91b60"
down_revision = "e5b3a8d0f172"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("submitters", sa.Column("is_cc", sa.Boolean(), nullable=False, server_default="false"))
    op.drop_column("submissions", "cc_emails")


def downgrade() -> None:
    op.add_column("submissions", sa.Column("cc_emails", JSONB(), nullable=False, server_default="[]"))
    op.drop_column("submitters", "is_cc")
