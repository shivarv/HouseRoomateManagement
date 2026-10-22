import uuid

from fastapi import APIRouter, status

from app.api.deps import CurrentUser, DbSession
from app.models import HouseholdMember
from app.schemas.help import HelpRequestCreate, HelpRequestOut, HelpRequestUpdate
from app.services import help as help_svc
from app.services import households as household_svc

router = APIRouter(tags=["help requests"])


@router.get("/me/help-requests", response_model=list[HelpRequestOut])
def my_help_requests(db: DbSession, user: CurrentUser):
    """Open requests in every house I'm in, ones done in the last two weeks, and all of mine."""
    memberships = household_svc.memberships(db, user)
    me_by_household = {m.household_id: m for m in memberships}
    return [
        help_svc.out(r, me_by_household[r.household_id]) for r in help_svc.visible(db, memberships)
    ]


@router.post(
    "/households/{household_id}/help-requests",
    response_model=HelpRequestOut,
    status_code=status.HTTP_201_CREATED,
)
def ask_for_help(
    household_id: uuid.UUID, body: HelpRequestCreate, db: DbSession, user: CurrentUser
):
    me = household_svc.require_membership(db, household_id, user)
    return help_svc.out(help_svc.create(db, me, body.title, body.details), me)


def _me(db, request_id: uuid.UUID, user) -> tuple[uuid.UUID, HouseholdMember]:
    """The request's id, and the caller's membership in its household (404 if not a member)."""
    req = help_svc.get(db, request_id)
    return req.id, household_svc.require_membership(db, req.household_id, user)


@router.patch("/help-requests/{request_id}", response_model=HelpRequestOut)
def edit_help_request(
    request_id: uuid.UUID, body: HelpRequestUpdate, db: DbSession, user: CurrentUser
):
    """The person who asked can edit while it's open; 409 once someone did it."""
    rid, me = _me(db, request_id, user)
    return help_svc.out(help_svc.update(db, rid, me, body.title, body.details), me)


@router.post("/help-requests/{request_id}/done", response_model=HelpRequestOut)
def mark_help_done(request_id: uuid.UUID, db: DbSession, user: CurrentUser):
    """Anyone in the house. The first person wins; everyone after gets 409."""
    rid, me = _me(db, request_id, user)
    return help_svc.out(help_svc.mark_done(db, rid, me), me)


@router.post("/help-requests/{request_id}/reopen", response_model=HelpRequestOut)
def reopen_help_request(request_id: uuid.UUID, db: DbSession, user: CurrentUser):
    rid, me = _me(db, request_id, user)
    return help_svc.out(help_svc.reopen(db, rid, me), me)


@router.delete("/help-requests/{request_id}", status_code=status.HTTP_204_NO_CONTENT)
def withdraw_help_request(request_id: uuid.UUID, db: DbSession, user: CurrentUser):
    rid, me = _me(db, request_id, user)
    help_svc.withdraw(db, rid, me)
