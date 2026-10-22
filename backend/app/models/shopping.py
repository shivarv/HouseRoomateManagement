import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, Timestamps, UUIDPrimaryKey
from app.models.household import HouseholdMember


class ShoppingItem(UUIDPrimaryKey, Timestamps, Base):
    """Something the house needs to buy (eggs, shampoo, garbage bags). Anyone can mark it bought."""

    __tablename__ = "shopping_items"
    __table_args__ = (
        Index("ix_shopping_items_household_status", "household_id", "status"),
        # One "needed" row per item name: adding "eggs" twice returns the first one.
        Index(
            "uq_shopping_items_needed_name",
            "household_id",
            func.lower(text("name")),
            unique=True,
            postgresql_where=text("status = 'needed'"),
        ),
    )

    household_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(80))
    quantity: Mapped[str | None] = mapped_column(String(40))  # free text: "2 dozen", "1 L"
    category: Mapped[str] = mapped_column(String(16), default="other")  # see ShoppingCategory
    note: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(16), default="needed")  # needed | bought
    added_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("household_members.id", ondelete="SET NULL")
    )
    bought_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("household_members.id", ondelete="SET NULL")
    )
    bought_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    added_by: Mapped[HouseholdMember | None] = relationship(
        foreign_keys=[added_by_id], lazy="joined"
    )
    bought_by: Mapped[HouseholdMember | None] = relationship(
        foreign_keys=[bought_by_id], lazy="joined"
    )
