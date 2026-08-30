"""templates.roles: persisted signer-role list

Revision ID: 4e9a2b71c5d3
Revises: b7e1a9c4d2f0
Create Date: 2026-07-31

"""

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "4e9a2b71c5d3"
down_revision: str | Sequence[str] | None = "b7e1a9c4d2f0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add templates.roles and backfill it from the roles already on each template's fields."""
    op.add_column(
        "templates",
        sa.Column("roles", postgresql.JSONB(astext_type=sa.Text()), server_default="[]", nullable=False),
    )

    connection = op.get_bind()
    rows = connection.execute(sa.text("SELECT id, fields FROM templates")).mappings()
    for row in rows:
        roles: list[str] = []
        for field in row["fields"] or []:
            role = field.get("role")
            if role and role not in roles:
                roles.append(role)
        if roles:
            connection.execute(
                sa.text("UPDATE templates SET roles = CAST(:roles AS jsonb) WHERE id = :id"),
                {"roles": json.dumps(roles), "id": row["id"]},
            )


def downgrade() -> None:
    """Drop templates.roles."""
    op.drop_column("templates", "roles")
