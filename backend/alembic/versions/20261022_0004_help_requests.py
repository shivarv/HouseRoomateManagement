"""help requests

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-22 12:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0004'
down_revision: str | None = '0003'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('help_requests',
    sa.Column('household_id', sa.Uuid(), nullable=False),
    sa.Column('requester_id', sa.Uuid(), nullable=False),
    sa.Column('title', sa.String(length=120), nullable=False),
    sa.Column('details', sa.String(length=500), nullable=True),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('done_by_id', sa.Uuid(), nullable=True),
    sa.Column('done_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['done_by_id'], ['household_members.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['household_id'], ['households.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['requester_id'], ['household_members.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_help_requests_household_status', 'help_requests', ['household_id', 'status'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_help_requests_household_status', table_name='help_requests')
    op.drop_table('help_requests')
