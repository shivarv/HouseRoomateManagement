"""reminders: recurring bills and who paid them

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-23 10:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0009'
down_revision: str | None = '0008'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('bills',
        sa.Column('household_id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=80), nullable=False),
        sa.Column('icon', sa.String(length=16), nullable=False),
        sa.Column('payer_mode', sa.String(length=16), nullable=False),
        sa.Column('payer_id', sa.Uuid(), nullable=True),
        sa.Column('due_day', sa.Integer(), nullable=False),
        sa.Column('amount_cents', sa.Integer(), nullable=True),
        sa.Column('currency', sa.String(length=3), nullable=False),
        sa.Column('note', sa.String(length=200), nullable=True),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['household_id'], ['households.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['payer_id'], ['household_members.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_bills_household', 'bills', ['household_id'], unique=False)

    op.create_table('bill_payments',
        sa.Column('bill_id', sa.Uuid(), nullable=False),
        sa.Column('period', sa.Date(), nullable=False),
        sa.Column('member_id', sa.Uuid(), nullable=False),
        sa.Column('recorded_by_id', sa.Uuid(), nullable=True),
        sa.Column('paid_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(['bill_id'], ['bills.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['member_id'], ['household_members.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['recorded_by_id'], ['household_members.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('bill_id', 'period', 'member_id'),
    )
    op.create_index('ix_bill_payments_bill_period', 'bill_payments', ['bill_id', 'period'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_bill_payments_bill_period', table_name='bill_payments')
    op.drop_table('bill_payments')
    op.drop_index('ix_bills_household', table_name='bills')
    op.drop_table('bills')
