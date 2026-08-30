"""submissions.public_uid: random non-enumerable ID for external artifacts.

Stamped into the signed-PDF watermark and signature certificate instead of
the sequential PK so recipients can't infer envelope volume. Backfills
existing rows with fresh uuid4 hex via gen_random_uuid() (Postgres 13+).

Revision ID: d4f8c2e6a9b1
Revises: 7c3d9e5f1a2b
Create Date: 2026-07-31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4f8c2e6a9b1"
down_revision: str | Sequence[str] | None = "7c3d9e5f1a2b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("submissions", sa.Column("public_uid", sa.String(length=32), nullable=True))
    op.execute("UPDATE submissions SET public_uid = replace(gen_random_uuid()::text, '-', '')")
    op.alter_column("submissions", "public_uid", nullable=False)
    op.create_unique_constraint("uq_submissions_public_uid", "submissions", ["public_uid"])


def downgrade() -> None:
    op.drop_constraint("uq_submissions_public_uid", "submissions", type_="unique")
    op.drop_column("submissions", "public_uid")
