"""error_logs: errors the backend hit, with the request, user, house and stack (kept 30 days)

Revision ID: 0017
Revises: 0016
Create Date: 2026-10-24 16:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = '0017'
down_revision: str | None = '0016'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'error_logs',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('level', sa.String(16), nullable=False),
        sa.Column('logger', sa.String(200), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('request_id', sa.String(32), nullable=True),
        sa.Column('method', sa.String(10), nullable=True),
        sa.Column('path', sa.String(500), nullable=True),
        sa.Column('status', sa.Integer(), nullable=True),
        sa.Column('user_id', sa.Uuid(), nullable=True),
        sa.Column('household_id', sa.Uuid(), nullable=True),
        sa.Column('household_name', sa.String(100), nullable=True),
        sa.Column('error_type', sa.String(200), nullable=True),
        sa.Column('stack', sa.Text(), nullable=True),
        sa.Column('context', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('app_version', sa.String(64), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_error_logs_created_at', 'error_logs', ['created_at'])
    op.create_index('ix_error_logs_household_id', 'error_logs', ['household_id'])
    op.create_index('ix_error_logs_request_id', 'error_logs', ['request_id'])


def downgrade() -> None:
    op.drop_table('error_logs')
