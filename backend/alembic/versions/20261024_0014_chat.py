"""house group chat

Revision ID: 0014
Revises: 0013
Create Date: 2026-10-24 10:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0014'
down_revision: str | None = '0013'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('chat_messages',
        sa.Column('household_id', sa.Uuid(), nullable=False),
        sa.Column('author_id', sa.Uuid(), nullable=True),
        sa.Column('body', sa.String(length=2000), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('edited_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(['household_id'], ['households.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['author_id'], ['household_members.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_chat_messages_household_created', 'chat_messages', ['household_id', 'created_at'], unique=False)
    op.create_table('chat_reads',
        sa.Column('member_id', sa.Uuid(), nullable=False),
        sa.Column('last_read_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['member_id'], ['household_members.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('member_id'),
    )


def downgrade() -> None:
    op.drop_table('chat_reads')
    op.drop_index('ix_chat_messages_household_created', table_name='chat_messages')
    op.drop_table('chat_messages')
