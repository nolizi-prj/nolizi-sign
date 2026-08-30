"""submissions.archived_at + archive_url: SharePoint archive mirror state.

NULL archived_at on a completed submission means "not yet archived" — the
daily job's sweep predicate. See
docs/superpowers/specs/2026-08-01-sharepoint-archive-design.md.

Revision ID: f3a8c1d97e42
Revises: d4f8c2e6a9b1
Create Date: 2026-08-01
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f3a8c1d97e42"
down_revision: str | Sequence[str] | None = "d4f8c2e6a9b1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("submissions", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("submissions", sa.Column("archive_url", sa.String(length=1024), nullable=True))


def downgrade() -> None:
    op.drop_column("submissions", "archive_url")
    op.drop_column("submissions", "archived_at")
