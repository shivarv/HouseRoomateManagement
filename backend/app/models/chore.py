import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    func,
)
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
    frequency: Mapped[str] = mapped_column(String(16), default="daily")  # daily | weekly
    assignment_mode: Mapped[str] = mapped_column(
        String(16), default="rotation", server_default="rotation"
    )  # rotation | open
    target_per_week: Mapped[int | None] = mapped_column()  # open chores, display only
    rotation_start_date: Mapped[date] = mapped_column(Date)  # always a period start
    # Missed periods are only back-filled from this date (creation, resume or settings change).
    tracked_from: Mapped[date] = mapped_column(Date, server_default=func.current_date())
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Read-only view of the ordered rotation; writes go through services.chores.set_rotation.
    rotation: Mapped[list["ChoreRotationMember"]] = relationship(
        order_by="ChoreRotationMember.position", viewonly=True, lazy="selectin"
    )

    @property
    def is_open(self) -> bool:
        return self.assignment_mode == "open"


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
    """One turn of a rotation chore: who it was assigned to and who actually did it."""

    __tablename__ = "chore_tasks"
    __table_args__ = (
        UniqueConstraint("chore_id", "due_date"),
        Index("ix_chore_tasks_member_due", "member_id", "due_date"),
    )

    chore_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chores.id", ondelete="CASCADE"))
    member_id: Mapped[uuid.UUID] = mapped_column(  # whose turn it is
        ForeignKey("household_members.id", ondelete="CASCADE")
    )
    due_date: Mapped[date] = mapped_column(Date)  # period start: the day, or Monday for weekly
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending | done
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("household_members.id", ondelete="SET NULL")
    )

    chore: Mapped[Chore] = relationship(lazy="joined")
    member: Mapped[HouseholdMember] = relationship(foreign_keys=[member_id], lazy="joined")
    completed_by: Mapped[HouseholdMember | None] = relationship(
        foreign_keys=[completed_by_id], lazy="joined"
    )


class ChoreLog(UUIDPrimaryKey, Base):
    """One time someone did an open chore (e.g. took out the garbage)."""

    __tablename__ = "chore_logs"
    __table_args__ = (Index("ix_chore_logs_chore_done", "chore_id", "done_on"),)

    chore_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chores.id", ondelete="CASCADE"))
    member_id: Mapped[uuid.UUID] = mapped_column(  # who did it
        ForeignKey("household_members.id", ondelete="CASCADE")
    )
    logged_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("household_members.id", ondelete="SET NULL")
    )
    done_on: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    chore: Mapped[Chore] = relationship(lazy="joined")
    member: Mapped[HouseholdMember] = relationship(foreign_keys=[member_id], lazy="joined")
    logged_by: Mapped[HouseholdMember | None] = relationship(
        foreign_keys=[logged_by_id], lazy="joined"
    )


class ChoreSwap(UUIDPrimaryKey, Base):
    """A request to hand one rotation turn to someone else, paid back with their next turn.

    Only these two dates change; the rotation itself is untouched. A turn can be swapped again
    later: the most recently accepted swap on a date wins.
    """

    __tablename__ = "chore_swaps"
    __table_args__ = (
        Index("ix_chore_swaps_household_status", "household_id", "status"),
        Index("ix_chore_swaps_chore_given", "chore_id", "given_date"),
        Index("ix_chore_swaps_chore_payback", "chore_id", "payback_date"),
    )

    household_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"))
    chore_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("chores.id", ondelete="CASCADE"))
    given_date: Mapped[date] = mapped_column(Date)  # period start of the turn being given away
    requester_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("household_members.id", ondelete="CASCADE")
    )
    acceptor_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("household_members.id", ondelete="CASCADE")
    )
    # The acceptor's next turn after given_date, which becomes the requester's.
    payback_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(16), default="open")  # see SwapStatus
    note: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    chore: Mapped[Chore] = relationship(lazy="joined")
    requester: Mapped[HouseholdMember] = relationship(foreign_keys=[requester_id], lazy="joined")
    acceptor: Mapped[HouseholdMember | None] = relationship(
        foreign_keys=[acceptor_id], lazy="joined"
    )


class HelpRequest(UUIDPrimaryKey, Timestamps, Base):
    """Someone asks the house for a hand. Anyone in the house can mark it done."""

    __tablename__ = "help_requests"
    __table_args__ = (Index("ix_help_requests_household_status", "household_id", "status"),)

    household_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"))
    requester_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("household_members.id", ondelete="CASCADE")
    )
    title: Mapped[str] = mapped_column(String(120))  # a preset ("Buy groceries") or custom text
    details: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(16), default="open")  # open | done
    done_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("household_members.id", ondelete="SET NULL")
    )
    done_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    requester: Mapped[HouseholdMember] = relationship(foreign_keys=[requester_id], lazy="joined")
    done_by: Mapped[HouseholdMember | None] = relationship(foreign_keys=[done_by_id], lazy="joined")


class ActivityEvent(UUIDPrimaryKey, Base):
    """Append-only record of every change in a household, shown in the activity feed."""

    __tablename__ = "activity_events"
    __table_args__ = (Index("ix_activity_household_created", "household_id", "created_at"),)

    household_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"))
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("household_members.id", ondelete="SET NULL")
    )
    action: Mapped[str] = mapped_column(String(32))
    chore_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("chores.id", ondelete="SET NULL"))
    chore_name: Mapped[str | None] = mapped_column(String(100))  # survives chore deletion
    subject_id: Mapped[uuid.UUID | None] = mapped_column(  # who did it / who was affected
        ForeignKey("household_members.id", ondelete="SET NULL")
    )
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(  # whose turn it was
        ForeignKey("household_members.id", ondelete="SET NULL")
    )
    due_date: Mapped[date | None] = mapped_column(Date)
    detail: Mapped[str | None] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    actor: Mapped[HouseholdMember | None] = relationship(foreign_keys=[actor_id], lazy="joined")
    subject: Mapped[HouseholdMember | None] = relationship(foreign_keys=[subject_id], lazy="joined")
    assignee: Mapped[HouseholdMember | None] = relationship(
        foreign_keys=[assignee_id], lazy="joined"
    )
