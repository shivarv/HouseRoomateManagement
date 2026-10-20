import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, Timestamps, UUIDPrimaryKey
from app.models.household import HouseholdMember


class Chore(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "chores"

    household_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(100))
    position: Mapped[int] = mapped_column(default=0)  # display order within the household
    frequency: Mapped[str] = mapped_column(String(16), default="daily")
    rotation_start_date: Mapped[date] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Read-only view of the ordered rotation; writes go through services.chores.set_rotation.
    rotation: Mapped[list["ChoreRotationMember"]] = relationship(
        order_by="ChoreRotationMember.position", viewonly=True, lazy="selectin"
    )


class ChoreRotationMember(Base):
    __tablename__ = "chore_rotation_members"
    __table_args__ = (UniqueConstraint("chore_id", "member_id"),)

    chore_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("chores.id", ondelete="CASCADE"), primary_key=True
    )
    position: Mapped[int] = mapped_column(primary_key=True)
    member_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("household_members.id", ondelete="CASCADE")
    )

    member: Mapped[HouseholdMember] = relationship(lazy="joined")


class ChoreTask(UUIDPrimaryKey, Timestamps, Base):
    """The persisted assignment of one chore on one day."""

    __tablename__ = "chore_tasks"
    __table_args__ = (
        UniqueConstraint("chore_id", "due_date"),
        Index("ix_chore_tasks_member_due", "member_id", "due_date"),
    )

    chore_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chores.id", ondelete="CASCADE"))
    member_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("household_members.id", ondelete="CASCADE")
    )
    due_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending | done
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    chore: Mapped[Chore] = relationship(lazy="joined")
    member: Mapped[HouseholdMember] = relationship(lazy="joined")
