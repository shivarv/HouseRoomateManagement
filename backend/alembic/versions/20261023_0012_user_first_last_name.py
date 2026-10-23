"""users: first and last name

Revision ID: 0012
Revises: 0011
Create Date: 2026-10-23 20:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0012'
down_revision: str | None = '0011'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('users', sa.Column('first_name', sa.String(length=50), server_default='', nullable=False))
    op.add_column('users', sa.Column('last_name', sa.String(length=50), server_default='', nullable=False))
    # Existing accounts keep their whole name as the first name; no last name (they can add one).
    op.execute("UPDATE users SET first_name = left(btrim(name), 50), last_name = ''")


def downgrade() -> None:
    op.drop_column('users', 'last_name')
    op.drop_column('users', 'first_name')
