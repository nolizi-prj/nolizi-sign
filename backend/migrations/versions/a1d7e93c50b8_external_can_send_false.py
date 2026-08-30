"""Set can_send=false for external users.

can_send server-defaults to true, so externally provisioned signers were
stored with a flag they can never use (require_sender excludes externals
regardless) — rendering a misleadingly "on" disabled toggle in the admin
user list. The users router now stores false at creation and rejects
enabling it for externals; this backfills the existing rows. Downgrade is
a no-op: the old rows' true values were meaningless.
"""

from alembic import op

revision = "a1d7e93c50b8"
down_revision = "f8c4d2a91b60"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE users SET can_send = false WHERE is_external")


def downgrade() -> None:
    pass
