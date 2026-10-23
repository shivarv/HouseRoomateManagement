"""invites by email

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-23 18:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0011'
down_revision: str | None = '0010'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('household_invites',
        sa.Column('household_id', sa.Uuid(), nullable=False),
        sa.Column('email', sa.String(length=320), nullable=False),
        sa.Column('invited_by_id', sa.Uuid(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('last_sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('accepted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(['household_id'], ['households.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['invited_by_id'], ['household_members.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('uq_household_invites_open', 'household_invites', ['household_id', 'email'],
                    unique=True, postgresql_where=sa.text('accepted_at IS NULL'))
    op.create_index('ix_household_invites_email', 'household_invites', ['email'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_household_invites_email', table_name='household_invites')
    op.drop_index('uq_household_invites_open', table_name='household_invites')
    op.drop_table('household_invites')
