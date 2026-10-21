import uuid

from fastapi import APIRouter, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.household import (
    HouseholdCreate,
    HouseholdDetail,
    HouseholdOut,
    HouseholdUpdate,
    InviteAccept,
    InvitePreview,
    MemberBrief,
    MemberCreate,
    MemberOut,
    MemberUpdate,
)
from app.services import households as svc

router = APIRouter(tags=["households"])


@router.get("/households", response_model=list[HouseholdOut])
def list_households(db: DbSession, user: CurrentUser):
    return [svc.household_out(m) for m in svc.memberships(db, user)]


@router.post("/households", response_model=HouseholdOut, status_code=status.HTTP_201_CREATED)
def create_household(body: HouseholdCreate, db: DbSession, user: CurrentUser):
    return svc.household_out(svc.create_household(db, user, body.name.strip(), body.timezone))


@router.get("/households/{household_id}", response_model=HouseholdDetail)
def get_household(household_id: uuid.UUID, db: DbSession, user: CurrentUser):
    me = svc.require_membership(db, household_id, user)
    members = [svc.member_out(m) for m in me.household.members if m.is_active]
    return HouseholdDetail(**svc.household_out(me).model_dump(), members=members)


@router.patch("/households/{household_id}", response_model=HouseholdOut)
def update_household(
    household_id: uuid.UUID, body: HouseholdUpdate, db: DbSession, user: CurrentUser
):
    me = svc.require_membership(db, household_id, user, admin=True)
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(me.household, field, value)
    db.commit()
    return svc.household_out(me)


@router.get("/households/{household_id}/members", response_model=list[MemberOut])
def list_members(household_id: uuid.UUID, db: DbSession, user: CurrentUser):
    me = svc.require_membership(db, household_id, user)
    return [svc.member_out(m) for m in me.household.members if m.is_active]


@router.post(
    "/households/{household_id}/members",
    response_model=MemberOut,
    status_code=status.HTTP_201_CREATED,
)
def add_member(household_id: uuid.UUID, body: MemberCreate, db: DbSession, user: CurrentUser):
    me = svc.require_membership(db, household_id, user, admin=True)
    return svc.member_out(svc.add_member(db, me.household, body.display_name.strip(), actor=me))


@router.patch("/members/{member_id}", response_model=MemberOut)
def update_member(member_id: uuid.UUID, body: MemberUpdate, db: DbSession, user: CurrentUser):
    member = svc.get_member(db, member_id)
    me = svc.require_membership(db, member.household_id, user, admin=True)
    if body.display_name is not None:
        member.display_name = body.display_name.strip()
    if body.role is not None and member.id != me.id:
        member.role = body.role
    db.commit()
    return svc.member_out(member)


@router.delete("/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(member_id: uuid.UUID, db: DbSession, user: CurrentUser):
    member = svc.get_member(db, member_id)
    me = svc.require_membership(db, member.household_id, user, admin=True)
    svc.deactivate_member(db, member, acting=me)


@router.get("/invites/{code}", response_model=InvitePreview)
def preview_invite(code: str, db: DbSession, user: CurrentUser):
    household = svc.find_by_invite(db, code)
    return InvitePreview(
        household_id=household.id,
        household_name=household.name,
        unclaimed_members=[MemberBrief.model_validate(m) for m in svc.unclaimed_members(household)],
    )


@router.post("/invites/{code}/accept", response_model=HouseholdOut)
def accept_invite(code: str, body: InviteAccept, db: DbSession, user: CurrentUser):
    household = svc.find_by_invite(db, code)
    member = svc.accept_invite(db, household, user, body.member_id, body.display_name)
    return svc.household_out(member)
