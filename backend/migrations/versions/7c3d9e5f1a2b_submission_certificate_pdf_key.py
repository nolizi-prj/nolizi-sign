"""submissions.certificate_pdf_key: standalone signature-certificate PDF.

NULL for envelopes completed before the certificate became its own artifact
(issue #15) — those keep the certificate page merged inside the signed PDF.

Revision ID: 7c3d9e5f1a2b
Revises: 4e9a2b71c5d3
Create Date: 2026-07-31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7c3d9e5f1a2b"
down_revision: str | Sequence[str] | None = "4e9a2b71c5d3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("submissions", sa.Column("certificate_pdf_key", sa.String(length=1024), nullable=True))


def downgrade() -> None:
    op.drop_column("submissions", "certificate_pdf_key")
