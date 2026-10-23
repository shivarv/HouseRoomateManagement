"""bills repeat monthly/weekly/daily; variable bills get per-period amounts; default bills

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-23 12:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0010'
down_revision: str | None = '0009'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Frozen copy of app.services.bills.DEFAULT_BILLS at this revision.
DEFAULTS = (
    ('Rent', '🏠', 'everyone', 'fixed'),
    ('Electricity', '⚡', 'anyone', 'variable'),
    ('WiFi', '📶', 'anyone', 'fixed'),
    ('Gas', '🔥', 'anyone', 'variable'),
)


def upgrade() -> None:
    op.add_column('bills', sa.Column('frequency', sa.String(length=16), server_default='monthly', nullable=False))
    op.add_column('bills', sa.Column('amount_type', sa.String(length=16), server_default='fixed', nullable=False))
    op.create_table('bill_amounts',
        sa.Column('bill_id', sa.Uuid(), nullable=False),
        sa.Column('period', sa.Date(), nullable=False),
        sa.Column('amount_cents', sa.Integer(), nullable=False),
        sa.Column('set_by_id', sa.Uuid(), nullable=True),
        sa.Column('set_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(['bill_id'], ['bills.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['set_by_id'], ['household_members.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('bill_id', 'period'),
    )
    # Houses without any bills yet get the defaults (monthly, due on the 1st), same as new houses.
    conn = op.get_bind()
    empty = [row[0] for row in conn.execute(sa.text(
        "SELECT id FROM households h WHERE NOT EXISTS (SELECT 1 FROM bills b WHERE b.household_id = h.id)"
    ))]
    for household_id in empty:
        for position, (name, icon, payer_mode, amount_type) in enumerate(DEFAULTS):
            conn.execute(sa.text("""
                INSERT INTO bills (id, household_id, name, icon, payer_mode, frequency, due_day,
                                   amount_type, currency, position, is_active)
                VALUES (gen_random_uuid(), :household_id, :name, :icon, :payer_mode, 'monthly', 1,
                        :amount_type, 'USD', :position, true)
            """), {'household_id': household_id, 'name': name, 'icon': icon,
                   'payer_mode': payer_mode, 'amount_type': amount_type, 'position': position})


def downgrade() -> None:
    op.drop_table('bill_amounts')
    op.drop_column('bills', 'amount_type')
    op.drop_column('bills', 'frequency')
