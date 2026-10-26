"""Reminders: the house's recurring bills (rent, wifi, electricity…) and who has paid them.

A bill comes up every month, week or day. Each occurrence (a *period*) starts on the 1st, on
Monday, or on the day itself, and that's when it shows up as a reminder. It's due on `due_day`.

Fixed bills repeat their amount; variable ones (gas, electricity) get each period's amount from an
admin when the bill arrives. Paying is "first click wins": the bill row is locked, and a later click
is told who paid.
"""

import calendar
import uuid
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Bill, BillAmount, BillPayment, HouseholdMember
from app.schemas.bill import BillList, BillOut, BillPaymentOut, BillPeriodOut
from app.schemas.household import MemberBrief
from app.services import activity
from app.services.errors import BadRequest, Conflict, Forbidden, NotFound

DUE_SOON_DAYS = 3
MAX_HISTORY = 24

# Every new house starts with these; admins edit or delete them. (name, icon, payer_mode, amount_type)
DEFAULT_BILLS = (
    ("Rent", "🏠", "everyone", "fixed"),
    ("Electricity", "⚡", "anyone", "variable"),
    ("WiFi", "📶", "anyone", "fixed"),
    ("Gas", "🔥", "anyone", "variable"),
)


# --- Periods ----------------------------------------------------------------------------------


def period_start(frequency: str, day: date) -> date:
    if frequency == "monthly":
        return day.replace(day=1)
    if frequency == "weekly":
        return day - timedelta(days=day.weekday())
    return day


def shift(frequency: str, period: date, steps: int) -> date:
    if frequency == "monthly":
        months = period.year * 12 + period.month - 1 + steps
        return date(months // 12, months % 12 + 1, 1)
    return period + timedelta(days=steps * (7 if frequency == "weekly" else 1))


def period_end(frequency: str, period: date) -> date:
    return shift(frequency, period, 1) - timedelta(days=1)


def due_date(bill: Bill, period: date) -> date:
    if bill.frequency == "monthly":
        last = calendar.monthrange(period.year, period.month)[1]
        return period.replace(day=min(bill.due_day, last))
    if bill.frequency == "weekly":
        return period + timedelta(days=min(bill.due_day, 7) - 1)
    return period


def label(frequency: str, period: date) -> str:
    if frequency == "monthly":
        return period.strftime("%b %Y")
    if frequency == "weekly":
        return f"Week of {period.strftime('%b')} {period.day}"
    return f"{period.strftime('%a, %b')} {period.day}"


def _status(paid: bool, due: date, period: date, current: date, today: date) -> str:
    if paid:
        return "paid"
    if period > current:
        return "upcoming"
    if today > due:
        return "overdue"
    return "due" if (due - today).days <= DUE_SOON_DAYS else "upcoming"


# --- Reading ----------------------------------------------------------------------------------


def get(db: Session, bill_id: uuid.UUID) -> Bill:
    bill = db.get(Bill, bill_id)
    if bill is None:
        raise NotFound("Bill not found")
    return bill


def _people(db: Session, household_id: uuid.UUID) -> int:
    return db.scalar(
        select(func.count()).where(
            HouseholdMember.household_id == household_id, HouseholdMember.is_active
        )
    ) or 0


def brief(member: HouseholdMember | None) -> MemberBrief | None:
    return MemberBrief(id=member.id, display_name=member.display_name) if member else None


def _payments(db: Session, bill_ids: list[uuid.UUID], periods: set[date]) -> dict:
    found: dict[tuple[uuid.UUID, date], list[BillPayment]] = {}
    if not bill_ids or not periods:
        return found
    for p in db.scalars(
        select(BillPayment)
        .where(BillPayment.bill_id.in_(bill_ids), BillPayment.period.in_(periods))
        .order_by(BillPayment.paid_at)
    ).unique():
        found.setdefault((p.bill_id, p.period), []).append(p)
    return found


def _amounts(db: Session, bill_ids: list[uuid.UUID], periods: set[date]) -> dict:
    if not bill_ids or not periods:
        return {}
    rows = db.scalars(
        select(BillAmount).where(BillAmount.bill_id.in_(bill_ids), BillAmount.period.in_(periods))
    )
    return {(a.bill_id, a.period): a.amount_cents for a in rows}


def _last_amount(db: Session, bill: Bill, before: date) -> int | None:
    return db.scalar(
        select(BillAmount.amount_cents)
        .where(BillAmount.bill_id == bill.id, BillAmount.period < before)
        .order_by(BillAmount.period.desc())
        .limit(1)
    )


def _period_out(
    bill: Bill,
    period: date,
    payments: list[BillPayment],
    period_amount: int | None,
    me: HouseholdMember,
    today: date,
    people: int,
) -> BillPeriodOut:
    current = period_start(bill.frequency, today)
    expected = people if bill.payer_mode == "everyone" else 1
    paid = len(payments) >= expected if bill.payer_mode == "everyone" else bool(payments)
    amount = bill.amount_cents if bill.amount_type == "fixed" else period_amount
    share = (
        round(amount / expected)
        if amount is not None and bill.payer_mode == "everyone" and expected
        else None
    )
    due = due_date(bill, period)
    return BillPeriodOut(
        period=period,
        period_end=period_end(bill.frequency, period),
        label=label(bill.frequency, period),
        due_date=due,
        status=_status(paid, due, period, current, today),
        amount_cents=amount,
        share_cents=share,
        payments=[
            BillPaymentOut(
                id=p.id,
                member=brief(p.member),
                recorded_by=brief(p.recorded_by),
                paid_at=p.paid_at,
                can_undo=me.role == "admin" or me.id in (p.member_id, p.recorded_by_id),
            )
            for p in payments
        ],
        paid_count=len(payments),
        expected_count=expected,
        i_paid=any(p.member_id == me.id for p in payments),
        is_current=period <= current,
    )


def list_bills(
    db: Session,
    me: HouseholdMember,
    today: date,
    *,
    include_paused: bool = False,
    only: list[Bill] | None = None,
) -> list[BillOut]:
    """Each bill with its current period (the month, week or day containing `today`)."""
    if only is None:
        query = select(Bill).where(Bill.household_id == me.household_id)
        if not include_paused:
            query = query.where(Bill.is_active)
        bills = list(db.scalars(query.order_by(Bill.position, Bill.created_at)).unique())
    else:
        bills = only
    periods = {b.id: period_start(b.frequency, today) for b in bills}
    ids = list(periods)
    payments = _payments(db, ids, set(periods.values()))
    amounts = _amounts(db, ids, set(periods.values()))
    people = _people(db, me.household_id)
    result = []
    for b in bills:
        period = periods[b.id]
        result.append(
            BillOut(
                id=b.id,
                name=b.name,
                icon=b.icon,
                payer_mode=b.payer_mode,
                frequency=b.frequency,
                due_day=b.due_day,
                amount_type=b.amount_type,
                amount_cents=b.amount_cents,
                last_amount_cents=(
                    _last_amount(db, b, period) if b.amount_type == "variable" else None
                ),
                currency=b.currency,
                note=b.note,
                position=b.position,
                is_active=b.is_active,
                current=_period_out(
                    b,
                    period,
                    payments.get((b.id, period), []),
                    amounts.get((b.id, period)),
                    me,
                    today,
                    people,
                ),
            )
        )
    return result


def bill_out(db: Session, bill: Bill, me: HouseholdMember, today: date) -> BillOut:
    return list_bills(db, me, today, only=[bill])[0]


def bill_list(db: Session, me: HouseholdMember, today: date, include_paused: bool) -> BillList:
    return BillList(today=today, bills=list_bills(db, me, today, include_paused=include_paused))


def history(
    db: Session, bill: Bill, me: HouseholdMember, today: date, limit: int
) -> list[BillPeriodOut]:
    """The periods before the current one, newest first."""
    current = period_start(bill.frequency, today)
    periods = [shift(bill.frequency, current, -i) for i in range(1, min(limit, MAX_HISTORY) + 1)]
    payments = _payments(db, [bill.id], set(periods))
    amounts = _amounts(db, [bill.id], set(periods))
    people = _people(db, bill.household_id)
    return [
        _period_out(
            bill, p, payments.get((bill.id, p), []), amounts.get((bill.id, p)), me, today, people
        )
        for p in periods
    ]


# --- Admin: setting bills up ------------------------------------------------------------------


def seed(db: Session, household_id: uuid.UUID) -> None:
    """A new house's default bills: monthly, due on the 1st. The caller commits."""
    for position, (name, icon, payer_mode, amount_type) in enumerate(DEFAULT_BILLS):
        db.add(
            Bill(
                household_id=household_id,
                name=name,
                icon=icon,
                payer_mode=payer_mode,
                frequency="monthly",
                due_day=1,
                amount_type=amount_type,
                currency="USD",
                position=position,
                is_active=True,
            )
        )


def _check_due(frequency: str, due_day: int) -> None:
    if frequency == "weekly" and not 1 <= due_day <= 7:
        raise BadRequest("For weekly bills, pick a weekday (1 = Monday … 7 = Sunday)")


def create(db: Session, me: HouseholdMember, fields: dict) -> Bill:
    count = db.scalar(select(func.count()).where(Bill.household_id == me.household_id)) or 0
    bill = Bill(
        household_id=me.household_id,
        name=fields["name"],
        icon=fields["icon"],
        payer_mode=fields["payer_mode"],
        frequency=fields["frequency"],
        due_day=fields["due_day"],
        amount_type=fields["amount_type"],
        amount_cents=fields.get("amount_cents") if fields["amount_type"] == "fixed" else None,
        currency=fields["currency"],
        note=fields.get("note") or None,
        position=count,
        is_active=True,
    )
    db.add(bill)
    activity.record(db, me.household_id, "bill_created", me, detail=bill.name)
    db.commit()
    db.refresh(bill)
    return bill


def update(db: Session, bill: Bill, me: HouseholdMember, fields: dict) -> Bill:
    """`fields` holds only what the client sent, so `null` can clear the amount."""
    frequency = fields.get("frequency") or bill.frequency
    due_day = fields.get("due_day") or bill.due_day
    if frequency == "weekly" and "due_day" not in fields and due_day > 7:
        due_day = 1  # switching to weekly from e.g. "the 15th": start with Monday
    _check_due(frequency, due_day)
    bill.frequency, bill.due_day = frequency, due_day
    for key in ("name", "icon", "currency", "is_active", "amount_type"):
        if fields.get(key) is not None:
            setattr(bill, key, fields[key])
    if "amount_cents" in fields:
        bill.amount_cents = fields["amount_cents"]
    if bill.amount_type == "variable":
        bill.amount_cents = None  # each period has its own amount
    if "note" in fields:
        bill.note = fields["note"] or None
    if fields.get("payer_mode") is not None:
        bill.payer_mode = fields["payer_mode"]
    activity.record(db, bill.household_id, "bill_updated", me, detail=bill.name)
    db.commit()
    db.refresh(bill)
    return bill


def delete(db: Session, bill: Bill, me: HouseholdMember) -> None:
    """Deletes the bill and its history. Pausing (is_active=false) keeps the history."""
    activity.record(db, bill.household_id, "bill_deleted", me, detail=bill.name)
    db.delete(bill)
    db.commit()


def _period(bill: Bill, on: date | None, today: date) -> date:
    period = period_start(bill.frequency, on or today)
    if period > period_start(bill.frequency, today):
        raise BadRequest("That hasn't come up yet")
    return period


def set_amount(
    db: Session,
    bill: Bill,
    me: HouseholdMember,
    amount_cents: int | None,
    on: date | None,
    today: date,
) -> None:
    """This period's amount of a variable bill, e.g. when the electricity bill arrives."""
    if bill.amount_type != "variable":
        raise BadRequest("This bill has a fixed amount; change it in the bill's settings")
    period = _period(bill, on, today)
    existing = db.scalar(
        select(BillAmount).where(BillAmount.bill_id == bill.id, BillAmount.period == period)
    )
    if amount_cents is None:
        if existing is not None:
            db.delete(existing)
    elif existing is None:
        db.add(
            BillAmount(bill_id=bill.id, period=period, amount_cents=amount_cents, set_by_id=me.id)
        )
    else:
        existing.amount_cents = amount_cents
        existing.set_by_id = me.id
    activity.record(
        db,
        bill.household_id,
        "bill_amount_set",
        me,
        detail=f"{bill.name} · {label(bill.frequency, period)}",
    )
    db.commit()


# --- Paying -----------------------------------------------------------------------------------


def pay(
    db: Session,
    bill_id: uuid.UUID,
    me: HouseholdMember,
    member_id: uuid.UUID | None,
    on: date | None,
    today: date,
) -> BillPayment:
    # Lock the bill so two people paying at once are handled one after another.
    if db.scalar(select(Bill.id).where(Bill.id == bill_id).with_for_update()) is None:
        raise NotFound("Bill not found")
    bill = db.get(Bill, bill_id, populate_existing=True)
    if not bill.is_active:
        raise BadRequest("This bill is paused")
    period = _period(bill, on, today)

    payer = me if member_id is None else db.get(HouseholdMember, member_id)
    if payer is None or payer.household_id != bill.household_id or not payer.is_active:
        raise BadRequest("That person isn't in this house")

    existing = list(
        db.scalars(
            select(BillPayment).where(BillPayment.bill_id == bill.id, BillPayment.period == period)
        ).unique()
    )
    if bill.payer_mode == "everyone":
        if any(p.member_id == payer.id for p in existing):
            if payer.id == me.id:
                raise Conflict("You already paid your share")
            raise Conflict(f"{payer.display_name} already paid their share")
    elif existing:
        raise Conflict(f"{existing[0].member.display_name} already paid it")

    payment = BillPayment(bill_id=bill.id, period=period, member_id=payer.id, recorded_by_id=me.id)
    db.add(payment)
    activity.record(
        db,
        bill.household_id,
        "bill_paid",
        me,
        subject_id=payer.id,
        detail=f"{bill.name} · {label(bill.frequency, period)}",
    )
    db.commit()
    db.refresh(payment)
    return payment


def get_payment(db: Session, payment_id: uuid.UUID) -> BillPayment:
    payment = db.get(BillPayment, payment_id)
    if payment is None:
        raise NotFound("Payment not found")
    return payment


def undo(db: Session, payment: BillPayment, me: HouseholdMember) -> None:
    if me.role != "admin" and me.id not in (payment.member_id, payment.recorded_by_id):
        raise Forbidden("Only the person who paid, whoever marked it, or an admin can undo this")
    bill = db.get(Bill, payment.bill_id)
    activity.record(
        db,
        bill.household_id,
        "bill_unpaid",
        me,
        subject_id=payment.member_id,
        detail=f"{bill.name} · {label(bill.frequency, payment.period)}",
    )
    db.delete(payment)
    db.commit()
