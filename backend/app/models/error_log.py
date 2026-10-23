import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKey


class ErrorLog(UUIDPrimaryKey, Base):
    """An error the backend hit, with who and which house it was for. Kept 30 days (see app.core.logs).

    No foreign keys on purpose: the record must survive the user or house being deleted, and
    writing it must never fail because of them.
    """

    __tablename__ = "error_logs"
    __table_args__ = (
        Index("ix_error_logs_created_at", "created_at"),
        Index("ix_error_logs_household_id", "household_id"),
        Index("ix_error_logs_request_id", "request_id"),
    )

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    level: Mapped[str] = mapped_column(String(16))  # ERROR / CRITICAL
    logger: Mapped[str] = mapped_column(String(200))
    message: Mapped[str] = mapped_column(Text)
    request_id: Mapped[str | None] = mapped_column(String(32))  # the "ref" shown to the user
    method: Mapped[str | None] = mapped_column(String(10))
    path: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[int | None] = mapped_column(Integer)
    user_id: Mapped[uuid.UUID | None] = mapped_column()
    household_id: Mapped[uuid.UUID | None] = mapped_column()
    household_name: Mapped[str | None] = mapped_column(String(100))
    error_type: Mapped[str | None] = mapped_column(String(200))
    stack: Mapped[str | None] = mapped_column(Text)
    context: Mapped[dict | None] = mapped_column(JSONB)  # query string, route ids… secrets removed
    app_version: Mapped[str | None] = mapped_column(String(64))  # Render's git commit
