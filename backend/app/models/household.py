import uuid

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, Timestamps, UUIDPrimaryKey


class Household(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "households"

    name: Mapped[str] = mapped_column(String(100))
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

    household: Mapped[Household] = relationship(back_populates="members")
