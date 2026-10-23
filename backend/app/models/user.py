import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, Timestamps, UUIDPrimaryKey


class User(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    first_name: Mapped[str] = mapped_column(String(50), default="")
    last_name: Mapped[str] = mapped_column(String(50), default="")
    # "First Last": what houses call me by default. Kept in step with the two parts.
    name: Mapped[str] = mapped_column(String(100))
    password_hash: Mapped[str] = mapped_column(String(255))
    # When their email was confirmed. Accounts that existed before checks were added count as
    # verified (migration 0015); new sign-ups stay unverified until there's an email check.
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # The house the apps open on: the one picked or joined last, on any device.
    last_household_id: Mapped[uuid.UUID | None] = mapped_column(
        # households.created_by_id points back here; use_alter breaks the cycle for create/drop.
        ForeignKey(
            "households.id",
            ondelete="SET NULL",
            use_alter=True,
            name="fk_users_last_household_id",
        )
    )
