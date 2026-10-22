"""chore swaps

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-21 12:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0003'
down_revision: str | None = '0002'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('chore_swaps',
    sa.Column('household_id', sa.Uuid(), nullable=False),
    sa.Column('chore_id', sa.Uuid(), nullable=False),
    sa.Column('given_date', sa.Date(), nullable=False),
    sa.Column('requester_id', sa.Uuid(), nullable=False),
    sa.Column('acceptor_id', sa.Uuid(), nullable=True),
    sa.Column('payback_date', sa.Date(), nullable=True),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('note', sa.String(length=200), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['acceptor_id'], ['household_members.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['chore_id'], ['chores.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['household_id'], ['households.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['requester_id'], ['household_members.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_chore_swaps_household_status', 'chore_swaps', ['household_id', 'status'], unique=False)
    op.create_index('ix_chore_swaps_chore_given', 'chore_swaps', ['chore_id', 'given_date'], unique=False)
    op.create_index('ix_chore_swaps_chore_payback', 'chore_swaps', ['chore_id', 'payback_date'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_chore_swaps_chore_payback', table_name='chore_swaps')
    op.drop_index('ix_chore_swaps_chore_given', table_name='chore_swaps')
    op.drop_index('ix_chore_swaps_household_status', table_name='chore_swaps')
    op.drop_table('chore_swaps')
