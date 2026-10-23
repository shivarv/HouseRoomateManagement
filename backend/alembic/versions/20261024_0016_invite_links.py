"""household_invites: a private link per emailed invite, which stops working when it's cancelled

Revision ID: 0016
Revises: 0015
Create Date: 2026-10-24 14:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0016'
down_revision: str | None = '0015'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('household_invites', sa.Column('token', sa.String(64), nullable=True))
    op.add_column('household_invites', sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True))
    # Invites already out: a random link each, good for another week (their old emails used the house code).
    op.execute(
        "UPDATE household_invites SET token = replace(gen_random_uuid()::text || gen_random_uuid()::text, '-', ''),"
        " expires_at = now() + interval '7 days'"
    )
    op.alter_column('household_invites', 'token', nullable=False)
    op.alter_column('household_invites', 'expires_at', nullable=False)
    op.create_unique_constraint('uq_household_invites_token', 'household_invites', ['token'])


def downgrade() -> None:
    op.drop_constraint('uq_household_invites_token', 'household_invites', type_='unique')
    op.drop_column('household_invites', 'expires_at')
    op.drop_column('household_invites', 'token')
