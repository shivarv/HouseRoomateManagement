"""voice_commands: what someone said to the mic button and what came of it (daily limit, cost)

Revision ID: 0021
Revises: 0020
Create Date: 2026-10-28 12:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0021'
down_revision: str | None = '0020'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'voice_commands',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('household_id', sa.Uuid(), nullable=False),
        sa.Column('text', sa.String(length=500), nullable=False),
        sa.Column('tab', sa.String(length=32), nullable=True),
        sa.Column('outcome', sa.JSON(), nullable=False),
        sa.Column('input_tokens', sa.Integer(), nullable=False),
        sa.Column('output_tokens', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['household_id'], ['households.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_voice_commands_user_created', 'voice_commands', ['user_id', 'created_at'])
    op.create_index('ix_voice_commands_household_id', 'voice_commands', ['household_id'])


def downgrade() -> None:
    op.drop_table('voice_commands')
