"""household creator and address; names unique per creator

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-22 21:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0007'
down_revision: str | None = '0006'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('households', sa.Column('address', sa.String(length=300), nullable=True))
    op.add_column('households', sa.Column('created_by_id', sa.Uuid(), nullable=True))
    op.create_foreign_key(
        'fk_households_created_by_id', 'households', 'users',
        ['created_by_id'], ['id'], ondelete='SET NULL',
    )
    op.create_index('ix_households_created_by_id', 'households', ['created_by_id'], unique=False)

    # Existing houses: the creator is the earliest admin who has an account.
    op.execute("""
        UPDATE households h SET created_by_id = (
            SELECT m.user_id FROM household_members m
            WHERE m.household_id = h.id AND m.role = 'admin' AND m.user_id IS NOT NULL
            ORDER BY m.created_at LIMIT 1
        )
    """)

    # Never rename people's houses silently: stop and say which ones clash.
    clashes = op.get_bind().execute(sa.text("""
        SELECT created_by_id, lower(name) FROM households
        WHERE created_by_id IS NOT NULL
        GROUP BY created_by_id, lower(name) HAVING count(*) > 1
    """)).fetchall()
    if clashes:
        raise RuntimeError(
            f"Rename these houses first, each creator has two with the same name: {clashes}"
        )

    op.create_index(
        'uq_households_creator_name', 'households',
        ['created_by_id', sa.text('lower(name)')], unique=True,
    )


def downgrade() -> None:
    op.drop_index('uq_households_creator_name', table_name='households')
    op.drop_index('ix_households_created_by_id', table_name='households')
    op.drop_constraint('fk_households_created_by_id', 'households', type_='foreignkey')
    op.drop_column('households', 'created_by_id')
    op.drop_column('households', 'address')
