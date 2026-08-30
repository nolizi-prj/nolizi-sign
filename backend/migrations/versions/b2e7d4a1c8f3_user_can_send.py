"""User can_send flag: admin-revocable send permission (defaults true)."""

import sqlalchemy as sa
from alembic import op

revision = "b2e7d4a1c8f3"
down_revision = "a7e42b9c1d05"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("can_send", sa.Boolean(), nullable=False, server_default="true"))


def downgrade() -> None:
    op.drop_column("users", "can_send")
