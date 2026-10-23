"""users: email verified; everyone who already has an account counts as verified

Revision ID: 0015
Revises: 0014
Create Date: 2026-10-24 12:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0015'
down_revision: str | None = '0014'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('users', sa.Column('email_verified_at', sa.DateTime(timezone=True), nullable=True))
    # Accounts that exist now were set up by hand or by people we know: mark them verified.
    op.execute("UPDATE users SET email_verified_at = now()")


def downgrade() -> None:
    op.drop_column('users', 'email_verified_at')
