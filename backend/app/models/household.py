import uuid

from sqlalchemy import Boolean, ForeignKey, Index, String, UniqueConstraint, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, Timestamps, UUIDPrimaryKey


class Household(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "households"
    # A house belongs to whoever created it: one person can't have two with the same name
    # (case-insensitive), but different people can.
    __table_args__ = (
        Index("uq_households_creator_name", "created_by_id", func.lower(text("name")), unique=True),
    )

    name: Mapped[str] = mapped_column(String(100))
    # Required for new houses; NULL only on houses created before addresses existed.
    address: Mapped[str | None] = mapped_column(String(300))
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")
    invite_code: Mapped[str] = mapped_column(String(12), unique=True, index=True)

    members: Mapped[list["HouseholdMember"]] = relationship(
        back_populates="household",
        order_by="HouseholdMember.created_at",
        cascade="all, delete-orphan",
    )


class HouseholdMember(UUIDPrimaryKey, Timestamps, Base):
    """A person living in a household. May exist before they have an account (user_id NULL)."""

    __tablename__ = "household_members"
    __table_args__ = (UniqueConstraint("household_id", "user_id"),)

    household_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), index=True
    )
    display_name: Mapped[str] = mapped_column(String(100))
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    role: Mapped[str] = mapped_column(String(16), default="member")  # 'admin' | 'member'
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Optional contact details an admin can add for someone who hasn't joined yet (to invite them,
    # and later for notifications). Once they join, their account's email is used.
    email: Mapped[str | None] = mapped_column(String(320))  # lowercased
    phone: Mapped[str | None] = mapped_column(String(32))

    household: Mapped[Household] = relationship(back_populates="members")
    # The account, once they've joined: their first and last name show in people lists.
    user: Mapped["User | None"] = relationship("User", lazy="joined")  # noqa: F821
