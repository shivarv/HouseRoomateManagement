"""grocery_categories: a more general Groceries icon (🛒 instead of 🥚)

Only rows still on the old standard icon change, so an icon an admin picked stays.

Revision ID: 0018
Revises: 0017
Create Date: 2026-10-24 18:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '0018'
down_revision: str | None = '0017'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (key, old standard icon, new standard icon)
CHANGES = (('groceries', '🥚', '🛒'),)


def _swap(pairs) -> None:
    for key, old, new in pairs:
        op.execute(
            sa.text("UPDATE grocery_categories SET icon = :new WHERE key = :key AND icon = :old").bindparams(
                key=key, old=old, new=new
            )
        )


def upgrade() -> None:
    _swap(CHANGES)


def downgrade() -> None:
    _swap([(key, new, old) for key, old, new in reversed(CHANGES)])
