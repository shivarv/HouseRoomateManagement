import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDPrimaryKey
from app.models.household import Household, HouseholdMember


class HouseholdInvite(UUIDPrimaryKey, Base):
    """Someone invited to a house by email. Pending until they join; shown to them once signed in.

    The email carries a private link (`token`) that works only while the invite is pending and not
    expired, and only for this email. Cancelling deletes the row, which kills the link.
    """

    __tablename__ = "household_invites"
    __table_args__ = (
        # One open invite per email per house; inviting again just re-sends it.
        Index(
            "uq_household_invites_open",
            "household_id",
            "email",
            unique=True,
            postgresql_where=text("accepted_at IS NULL"),
        ),
        Index("ix_household_invites_email", "email"),
    )

    household_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"))
    email: Mapped[str] = mapped_column(String(320))  # lowercased
    invited_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("household_members.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))  # None: not emailed
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    token: Mapped[str] = mapped_column(String(64), unique=True)  # the private link; new on each re-send
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    household: Mapped[Household] = relationship(lazy="joined")
    invited_by: Mapped[HouseholdMember | None] = relationship(lazy="joined")
