"""household members: optional email and phone

Revision ID: 0013
Revises: 0012
Create Date: 2026-10-23 21:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0013'
down_revision: str | None = '0012'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('household_members', sa.Column('email', sa.String(length=320), nullable=True))
    op.add_column('household_members', sa.Column('phone', sa.String(length=32), nullable=True))


def downgrade() -> None:
    op.drop_column('household_members', 'phone')
    op.drop_column('household_members', 'email')
