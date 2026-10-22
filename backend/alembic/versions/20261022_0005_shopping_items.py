"""shopping items

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-22 18:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0005'
down_revision: str | None = '0004'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('shopping_items',
    sa.Column('household_id', sa.Uuid(), nullable=False),
    sa.Column('name', sa.String(length=80), nullable=False),
    sa.Column('quantity', sa.String(length=40), nullable=True),
    sa.Column('category', sa.String(length=16), nullable=False),
    sa.Column('note', sa.String(length=200), nullable=True),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('added_by_id', sa.Uuid(), nullable=True),
    sa.Column('bought_by_id', sa.Uuid(), nullable=True),
    sa.Column('bought_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['added_by_id'], ['household_members.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['bought_by_id'], ['household_members.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['household_id'], ['households.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_shopping_items_household_status', 'shopping_items', ['household_id', 'status'], unique=False)
    op.create_index('uq_shopping_items_needed_name', 'shopping_items', ['household_id', sa.text('lower(name)')], unique=True, postgresql_where=sa.text("status = 'needed'"))


def downgrade() -> None:
    op.drop_index('uq_shopping_items_needed_name', table_name='shopping_items', postgresql_where=sa.text("status = 'needed'"))
    op.drop_index('ix_shopping_items_household_status', table_name='shopping_items')
    op.drop_table('shopping_items')
