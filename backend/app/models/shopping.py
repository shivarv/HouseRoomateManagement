import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, UniqueConstraint, func, text
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
    category: Mapped[str] = mapped_column(String(40), default="other")  # a GroceryCategory.key
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


class GroceryCategory(UUIDPrimaryKey, Timestamps, Base):
    """A section of the house's shopping list (Groceries, Toiletries…). Admins configure them.

    Items refer to a category by `key`, which never changes, so renaming is free. "other" always
    exists: deleting a category moves its items and quick-add items there.
    """

    __tablename__ = "grocery_categories"
    __table_args__ = (
        UniqueConstraint("household_id", "key"),
        Index("uq_grocery_categories_label", "household_id", func.lower(text("label")), unique=True),
    )

    household_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"))
    key: Mapped[str] = mapped_column(String(40))
    label: Mapped[str] = mapped_column(String(40))
    icon: Mapped[str] = mapped_column(String(16), default="🛍️")
    position: Mapped[int] = mapped_column(default=0)


class GroceryPreset(UUIDPrimaryKey, Timestamps, Base):
    """A quick-add item on the house's shopping list ("Eggs"), chosen by the admin.

    `dismissed` rows are names the admin chose not to add, so they stop being suggested.
    """

    __tablename__ = "grocery_presets"
    __table_args__ = (
        Index("uq_grocery_presets_name", "household_id", func.lower(text("name")), unique=True),
    )

    household_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(80))
    category_key: Mapped[str] = mapped_column(String(40), default="other")
    position: Mapped[int] = mapped_column(default=0)
    status: Mapped[str] = mapped_column(String(16), default="active")  # active | dismissed
