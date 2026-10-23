import uuid
from datetime import date

from fastapi import APIRouter, Query, status

from app.api.deps import CurrentUser, DbSession
from app.models import HouseholdMember
from app.schemas.bill import (
    BillAmountSet,
    BillCreate,
    BillList,
    BillOut,
    BillPay,
    BillPaymentOut,
    BillPeriodOut,
    BillUpdate,
)
from app.services import bills as svc
from app.services import clock
from app.services import households as household_svc

router = APIRouter(tags=["reminders (bills)"])


def _today(member: HouseholdMember) -> date:
    return clock.today_in(member.household.timezone)


def _me(db, bill_id: uuid.UUID, user, admin: bool = False):
    bill = svc.get(db, bill_id)
    return bill, household_svc.require_membership(db, bill.household_id, user, admin=admin)


@router.get("/households/{household_id}/bills", response_model=BillList)
def list_bills(
    household_id: uuid.UUID, db: DbSession, user: CurrentUser, include_paused: bool = False
):
    """Each bill with its current period: this month, this week or today.

    `include_paused` (admins) also returns paused bills, for the settings screen.
    """
    me = household_svc.require_membership(db, household_id, user)
    return svc.bill_list(db, me, _today(me), include_paused and me.role == "admin")


@router.get("/bills/{bill_id}/history", response_model=list[BillPeriodOut])
def bill_history(
    bill_id: uuid.UUID, db: DbSession, user: CurrentUser, limit: int = Query(6, ge=1, le=24)
):
    """The periods before the current one, newest first."""
    bill, me = _me(db, bill_id, user)
    return svc.history(db, bill, me, _today(me), limit)


@router.post(
    "/households/{household_id}/bills", response_model=BillOut, status_code=status.HTTP_201_CREATED
)
def create_bill(household_id: uuid.UUID, body: BillCreate, db: DbSession, user: CurrentUser):
    me = household_svc.require_membership(db, household_id, user, admin=True)
    return svc.bill_out(db, svc.create(db, me, body.model_dump()), me, _today(me))


@router.patch("/bills/{bill_id}", response_model=BillOut)
def update_bill(bill_id: uuid.UUID, body: BillUpdate, db: DbSession, user: CurrentUser):
    bill, me = _me(db, bill_id, user, admin=True)
    bill = svc.update(db, bill, me, body.model_dump(exclude_unset=True))
    return svc.bill_out(db, bill, me, _today(me))


@router.delete("/bills/{bill_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_bill(bill_id: uuid.UUID, db: DbSession, user: CurrentUser):
    bill, me = _me(db, bill_id, user, admin=True)
    svc.delete(db, bill, me)


@router.put("/bills/{bill_id}/amount", response_model=BillOut)
def set_amount(bill_id: uuid.UUID, body: BillAmountSet, db: DbSession, user: CurrentUser):
    """Admins: this period's amount of a variable bill (gas, electricity). `null` clears it."""
    bill, me = _me(db, bill_id, user, admin=True)
    svc.set_amount(db, bill, me, body.amount_cents, body.period, _today(me))
    return svc.bill_out(db, bill, me, _today(me))


@router.post("/bills/{bill_id}/pay", response_model=BillPaymentOut, status_code=201)
def pay_bill(bill_id: uuid.UUID, body: BillPay, db: DbSession, user: CurrentUser):
    """Anyone in the house, for themselves or someone else. Already paid → 409 saying who."""
    bill, me = _me(db, bill_id, user)
    payment = svc.pay(db, bill.id, me, body.member_id, body.period, _today(me))
    return BillPaymentOut(
        id=payment.id,
        member=svc.brief(payment.member),
        recorded_by=svc.brief(payment.recorded_by),
        paid_at=payment.paid_at,
        can_undo=True,
    )


@router.delete("/bill-payments/{payment_id}", status_code=status.HTTP_204_NO_CONTENT)
def undo_payment(payment_id: uuid.UUID, db: DbSession, user: CurrentUser):
    payment = svc.get_payment(db, payment_id)
    _, me = _me(db, payment.bill_id, user)
    svc.undo(db, payment, me)
