"""users: sign in with Google, Apple or Facebook (user_identities), an optional phone, and email /
password made optional (a social sign-up may come with only a phone, and has no password)

Revision ID: 0020
Revises: 0019
Create Date: 2026-10-26 15:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0020'
down_revision: str | None = '0019'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('users', sa.Column('phone', sa.String(length=32), nullable=True))
    op.create_unique_constraint('uq_users_phone', 'users', ['phone'])
    op.alter_column('users', 'email', existing_type=sa.String(length=320), nullable=True)
    op.alter_column('users', 'password_hash', existing_type=sa.String(length=255), nullable=True)
    op.create_table(
        'user_identities',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('provider', sa.String(length=16), nullable=False),
        sa.Column('subject', sa.String(length=255), nullable=False),
        sa.Column('email', sa.String(length=320), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('provider', 'subject'),
    )
    op.create_index('ix_user_identities_user_id', 'user_identities', ['user_id'])


def downgrade() -> None:
    op.drop_index('ix_user_identities_user_id', table_name='user_identities')
    op.drop_table('user_identities')
    # Social-only accounts have no email or password: they can't survive the stricter columns.
    op.execute("DELETE FROM users WHERE email IS NULL OR password_hash IS NULL")
    op.alter_column('users', 'password_hash', existing_type=sa.String(length=255), nullable=False)
    op.alter_column('users', 'email', existing_type=sa.String(length=320), nullable=False)
    op.drop_constraint('uq_users_phone', 'users', type_='unique')
    op.drop_column('users', 'phone')
