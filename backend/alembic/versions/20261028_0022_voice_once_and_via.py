"""voice: each command runs (and is undone) once; activity says when it came from the assistant

Revision ID: 0022
Revises: 0021
Create Date: 2026-10-28 18:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0022'
down_revision: str | None = '0021'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'voice_commands',
        sa.Column('input', sa.String(length=8), server_default='voice', nullable=False),
    )
    for column in ('executed_at', 'undone_at'):
        op.add_column('voice_commands', sa.Column(column, sa.DateTime(timezone=True), nullable=True))
    op.add_column('activity_events', sa.Column('via', sa.String(length=8), nullable=True))


def downgrade() -> None:
    op.drop_column('activity_events', 'via')
    op.drop_column('voice_commands', 'undone_at')
    op.drop_column('voice_commands', 'executed_at')
    op.drop_column('voice_commands', 'input')
