"""Add users.email_login_min_iat for magic-link single-use enforcement.

Email-login tokens issued at or before this timestamp are rejected; the
column is set to the token's issue time on every successful email login.
"""

import sqlalchemy as sa
from alembic import op

revision = "b7e1a9c4d2f0"
down_revision = "cbfd8b9b5c8d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("email_login_min_iat", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "email_login_min_iat")
