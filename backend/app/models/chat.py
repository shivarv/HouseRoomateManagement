import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, UUIDPrimaryKey
from app.models.household import HouseholdMember


class ChatMessage(UUIDPrimaryKey, Base):
    """A message in a house's group chat. Deleting keeps the row (shown as "Message deleted")."""

    __tablename__ = "chat_messages"
    __table_args__ = (Index("ix_chat_messages_household_created", "household_id", "created_at"),)

    household_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"))
    author_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("household_members.id", ondelete="SET NULL")
    )
    body: Mapped[str] = mapped_column(String(2000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    author: Mapped[HouseholdMember | None] = relationship(lazy="joined")


class ChatRead(Base):
    """How far each person has read their house's chat, for the unread badge."""

    __tablename__ = "chat_reads"

    member_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("household_members.id", ondelete="CASCADE"), primary_key=True
    )
    last_read_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
