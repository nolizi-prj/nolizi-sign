"""Persist each envelope's claimed SharePoint archive folder.

Archive names no longer carry the internal id, so collisions (same owner,
same title, same UTC date) get a "_2" suffix chosen at first attempt —
and the chosen path must be remembered so retries of a partially-failed
archive reuse their own folder instead of suffixing against their own
leftovers.
"""

import sqlalchemy as sa
from alembic import op

revision = "d8f2a9c41e57"
down_revision = "c4e8f1a67b23"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("submissions", sa.Column("archive_path", sa.String(1024), nullable=True))


def downgrade() -> None:
    op.drop_column("submissions", "archive_path")
