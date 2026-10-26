"""bills: only "anyone" (one payment settles it) or "everyone" (split) — no more "one person pays"

Bills that named one person who pays become "anyone" and lose that person. Their payments stay.
The payer_id column stays.

Revision ID: 0019
Revises: 0018
Create Date: 2026-10-25 21:45:00.000000
"""
from collections.abc import Sequence

from alembic import op


revision: str = '0019'
down_revision: str | None = '0018'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("UPDATE bills SET payer_mode = 'anyone', payer_id = NULL WHERE payer_mode = 'one'")


def downgrade() -> None:
    pass  # who used to pay each bill isn't kept
