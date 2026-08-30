"""Shared templates: an owner-controlled flag that makes a template visible
and sendable (read-only) to every sender."""

import sqlalchemy as sa
from alembic import op

revision = "d8b4f6a2c9e3"
down_revision = "b5e9d2c7a3f1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "templates",
        sa.Column("shared", sa.Boolean(), nullable=False, server_default="false"),
    )


def downgrade() -> None:
    op.drop_column("templates", "shared")
