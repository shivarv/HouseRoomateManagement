import uuid

from fastapi import APIRouter, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.chore import SwapCreate, SwapOut
from app.services import chores as chore_svc
from app.services import clock
from app.services import households as household_svc
from app.services import swaps as swap_svc
from app.services import tasks as task_svc

router = APIRouter(tags=["swaps"])


@router.post(
    "/chores/{chore_id}/swaps", response_model=SwapOut, status_code=status.HTTP_201_CREATED
)
def ask_for_swap(chore_id: uuid.UUID, body: SwapCreate, db: DbSession, user: CurrentUser):
    """Ask the house to take one of my turns. Asking again returns the same request."""
    chore = chore_svc.get_chore(db, chore_id)
    me = household_svc.require_membership(db, chore.household_id, user)
    today = clock.today_in(me.household.timezone)
    swap = swap_svc.request(db, chore.id, me, body.due_date, body.note, today)
    return swap_svc.swap_out(db, swap, me)


@router.get("/households/{household_id}/swaps", response_model=list[SwapOut])
def household_swaps(household_id: uuid.UUID, db: DbSession, user: CurrentUser):
    """Open swap requests in this house."""
    me = household_svc.require_membership(db, household_id, user)
    task_svc.sync(db, me.household, clock.today_in(me.household.timezone))
    return [swap_svc.swap_out(db, s, me) for s in swap_svc.open_requests(db, household_id)]


@router.get("/me/swaps", response_model=list[SwapOut])
def my_swaps(db: DbSession, user: CurrentUser):
    """Open swap requests in every house I'm in, soonest turn first."""
    result: list[SwapOut] = []
    for me in household_svc.memberships(db, user):
        task_svc.sync(db, me.household, clock.today_in(me.household.timezone))
        open_swaps = swap_svc.open_requests(db, me.household_id)
        result += [swap_svc.swap_out(db, s, me) for s in open_swaps]
    result.sort(key=lambda s: (s.given_date, s.created_at))
    return result


@router.post("/swaps/{swap_id}/accept", response_model=SwapOut)
def accept_swap(swap_id: uuid.UUID, db: DbSession, user: CurrentUser):
    """Take the turn. The first person to accept wins; everyone after gets 409."""
    swap = swap_svc.get_swap(db, swap_id)
    me = household_svc.require_membership(db, swap.household_id, user)
    swap = swap_svc.accept(db, swap.id, me, clock.today_in(me.household.timezone))
    return swap_svc.swap_out(db, swap, me)


@router.post("/swaps/{swap_id}/cancel", response_model=SwapOut)
def cancel_swap(swap_id: uuid.UUID, db: DbSession, user: CurrentUser):
    swap = swap_svc.get_swap(db, swap_id)
    me = household_svc.require_membership(db, swap.household_id, user)
    swap = swap_svc.cancel(db, swap.id, me, clock.today_in(me.household.timezone))
    return swap_svc.swap_out(db, swap, me)
