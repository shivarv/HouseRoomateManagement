"""user last household

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-22 20:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0006'
down_revision: str | None = '0005'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('users', sa.Column('last_household_id', sa.Uuid(), nullable=True))
    op.create_foreign_key(
        'fk_users_last_household_id', 'users', 'households',
        ['last_household_id'], ['id'], ondelete='SET NULL',
    )


def downgrade() -> None:
    op.drop_constraint('fk_users_last_household_id', 'users', type_='foreignkey')
    op.drop_column('users', 'last_household_id')
