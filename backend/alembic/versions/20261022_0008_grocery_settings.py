"""grocery categories and quick-add items, configurable per house

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-22 23:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0008'
down_revision: str | None = '0007'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Frozen copies of the standard lists in app/services/grocery_settings.py at this revision.
CATEGORIES = (
    ('groceries', 'Groceries', '🥚'),
    ('toiletries', 'Toiletries', '🧴'),
    ('cleaning', 'Cleaning', '🧼'),
    ('household', 'Household', '🧻'),
    ('other', 'Other', '🛍️'),
)
PRESETS = (
    ('Eggs', 'groceries'), ('Milk', 'groceries'), ('Rice', 'groceries'), ('Oil', 'groceries'),
    ('Bread', 'groceries'), ('Onions', 'groceries'), ('Shampoo', 'toiletries'),
    ('Toothpaste', 'toiletries'), ('Hand wash', 'toiletries'), ('Washing soap', 'cleaning'),
    ('Dish soap', 'cleaning'), ('Garbage bags', 'cleaning'), ('Tissues', 'household'),
    ('Toilet paper', 'household'), ('Paper towels', 'household'),
)


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    ]


def upgrade() -> None:
    op.alter_column('shopping_items', 'category', type_=sa.String(length=40), existing_nullable=False)

    op.create_table('grocery_categories',
        sa.Column('household_id', sa.Uuid(), nullable=False),
        sa.Column('key', sa.String(length=40), nullable=False),
        sa.Column('label', sa.String(length=40), nullable=False),
        sa.Column('icon', sa.String(length=16), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(['household_id'], ['households.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('household_id', 'key'),
    )
    op.create_index('uq_grocery_categories_label', 'grocery_categories',
                    ['household_id', sa.text('lower(label)')], unique=True)

    op.create_table('grocery_presets',
        sa.Column('household_id', sa.Uuid(), nullable=False),
        sa.Column('name', sa.String(length=80), nullable=False),
        sa.Column('category_key', sa.String(length=40), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=16), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(['household_id'], ['households.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('uq_grocery_presets_name', 'grocery_presets',
                    ['household_id', sa.text('lower(name)')], unique=True)

    # Every existing house gets the standard lists, same as a new one.
    conn = op.get_bind()
    for position, (key, label, icon) in enumerate(CATEGORIES):
        conn.execute(sa.text("""
            INSERT INTO grocery_categories (id, household_id, key, label, icon, position)
            SELECT gen_random_uuid(), id, :key, :label, :icon, :position FROM households
        """), {'key': key, 'label': label, 'icon': icon, 'position': position})
    for position, (name, key) in enumerate(PRESETS):
        conn.execute(sa.text("""
            INSERT INTO grocery_presets (id, household_id, name, category_key, position, status)
            SELECT gen_random_uuid(), id, :name, :key, :position, 'active' FROM households
        """), {'name': name, 'key': key, 'position': position})


def downgrade() -> None:
    op.drop_index('uq_grocery_presets_name', table_name='grocery_presets')
    op.drop_table('grocery_presets')
    op.drop_index('uq_grocery_categories_label', table_name='grocery_categories')
    op.drop_table('grocery_categories')
    # Items filed under a custom category fall back to "other" so they fit the old column.
    op.execute("UPDATE shopping_items SET category = 'other' WHERE length(category) > 16")
    op.alter_column('shopping_items', 'category', type_=sa.String(length=16), existing_nullable=False)
