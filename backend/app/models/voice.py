import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, Timestamps, UUIDPrimaryKey


class VoiceCommand(UUIDPrimaryKey, Timestamps, Base):
    """One thing someone said to the mic button, and what Claude made of it. Counts towards the
    daily limit, shows what voice costs (tokens), and gives real phrases to test against."""

    __tablename__ = "voice_commands"
    __table_args__ = (Index("ix_voice_commands_user_created", "user_id", "created_at"),)

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    household_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), index=True
    )
    text: Mapped[str] = mapped_column(String(500))
    tab: Mapped[str | None] = mapped_column(String(32))
    input: Mapped[str] = mapped_column(String(8), default="voice")  # "voice" (spoken) or "typed"
    # What came back: the proposed action types, or why there were none.
    outcome: Mapped[dict] = mapped_column(JSON, default=dict)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    # Set once each: a second Confirm (double tap, retry, another tab) or Undo finds them taken.
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    undone_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
