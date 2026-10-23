import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, Timestamps, UUIDPrimaryKey
from app.models.household import HouseholdMember


class Bill(UUIDPrimaryKey, Timestamps, Base):
    """A recurring house payment (rent, wifi, electricity). Admins set them up.

    It comes up every `frequency` period (month, week or day) and is due on `due_day`:
    the day of the month (monthly), the weekday 1=Mon…7=Sun (weekly), or ignored (daily).

    amount_type:
      fixed     `amount_cents` repeats every period (rent, wifi)
      variable  each period's amount is entered when the bill comes (BillAmount: gas, electricity)

    payer_mode:
      one       one person pays it (payer_id); anyone can still mark it paid for them
      anyone    whoever pays first marks it paid for the period
      everyone  each person pays their share; each one who has paid is counted
    """

    __tablename__ = "bills"
    __table_args__ = (Index("ix_bills_household", "household_id"),)

    household_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("households.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(80))
    icon: Mapped[str] = mapped_column(String(16), default="🧾")
    payer_mode: Mapped[str] = mapped_column(String(16), default="anyone")  # one | anyone | everyone
    payer_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("household_members.id", ondelete="SET NULL")
    )
    frequency: Mapped[str] = mapped_column(String(16), default="monthly")  # monthly | weekly | daily
    due_day: Mapped[int] = mapped_column(default=1)  # see above; short months use their last day
    amount_type: Mapped[str] = mapped_column(String(16), default="fixed")  # fixed | variable
    amount_cents: Mapped[int | None] = mapped_column()  # fixed bills; display only, integer cents
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    note: Mapped[str | None] = mapped_column(String(200))  # e.g. "pay at the landlord's portal"
    position: Mapped[int] = mapped_column(default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    payer: Mapped[HouseholdMember | None] = relationship(lazy="joined")


class BillAmount(UUIDPrimaryKey, Base):
    """This period's amount of a variable bill (e.g. October's electricity), set by an admin."""

    __tablename__ = "bill_amounts"
    __table_args__ = (UniqueConstraint("bill_id", "period"),)

    bill_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bills.id", ondelete="CASCADE"))
    period: Mapped[date] = mapped_column(Date)  # start of the period it's for
    amount_cents: Mapped[int] = mapped_column()
    set_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("household_members.id", ondelete="SET NULL")
    )
    set_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class BillPayment(UUIDPrimaryKey, Base):
    """Someone paid a bill (or their share of it) for one period."""

    __tablename__ = "bill_payments"
    __table_args__ = (
        # Everyone mode: each person once per period. One/anyone: the service allows one row.
        UniqueConstraint("bill_id", "period", "member_id"),
        Index("ix_bill_payments_bill_period", "bill_id", "period"),
    )

    bill_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("bills.id", ondelete="CASCADE"))
    period: Mapped[date] = mapped_column(Date)  # start of the period: month start, Monday, or the day
    member_id: Mapped[uuid.UUID] = mapped_column(  # who paid
        ForeignKey("household_members.id", ondelete="CASCADE")
    )
    recorded_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("household_members.id", ondelete="SET NULL")
    )
    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    member: Mapped[HouseholdMember] = relationship(foreign_keys=[member_id], lazy="joined")
    recorded_by: Mapped[HouseholdMember | None] = relationship(
        foreign_keys=[recorded_by_id], lazy="joined"
    )
