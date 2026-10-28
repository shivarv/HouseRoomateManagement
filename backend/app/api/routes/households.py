import uuid

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, DbSession
from app.schemas.household import (
    HouseholdCreate,
    HouseholdDetail,
    HouseholdOut,
    HouseholdUpdate,
    InviteAccept,
    InvitePreview,
    InvitePublic,
    MemberAdded,
    MemberBrief,
    MemberCreate,
    MemberOut,
    MemberUpdate,
)
from app.schemas.invite import EmailInviteOut, EmailInviteResults, InviteEmails, InviteLinkPublic, MyInvite
from app.schemas.setup import HouseholdSetup, SetupTemplate
from app.services import email
from app.services import households as svc
from app.services import invites as invite_svc
from app.services import setup as setup_svc

router = APIRouter(tags=["households"])


@router.get("/households", response_model=list[HouseholdOut])
def list_households(db: DbSession, user: CurrentUser):
    return [svc.household_out(m) for m in svc.memberships(db, user)]


@router.post("/households", response_model=HouseholdOut, status_code=status.HTTP_201_CREATED)
def create_household(body: HouseholdCreate, db: DbSession, user: CurrentUser):
    return svc.household_out(
        svc.create_household(db, user, body.name, body.address, body.timezone)
    )


@router.get("/households/setup/template", response_model=SetupTemplate)
def setup_template(user: CurrentUser):
    """Defaults to prefill the guided set-up with (up to `max_items` of each list)."""
    return setup_svc.template()


@router.post("/households/setup", response_model=HouseholdOut, status_code=status.HTTP_201_CREATED)
def setup_household(body: HouseholdSetup, db: DbSession, user: CurrentUser):
    """A new house with its people, chores, quick-add groceries and bills, all in one go.

    Anyone signed in can do this; they become the new house's admin.
    """
    return svc.household_out(setup_svc.create(db, user, body))


@router.get("/households/{household_id}", response_model=HouseholdDetail)
def get_household(household_id: uuid.UUID, db: DbSession, user: CurrentUser):
    me = svc.require_membership(db, household_id, user)
    invited = svc.invited_emails(db, household_id)
    members = [svc.member_out(m, invited) for m in me.household.members if m.is_active]
    return HouseholdDetail(**svc.household_out(me).model_dump(), members=members)


@router.patch("/households/{household_id}", response_model=HouseholdOut)
def update_household(
    household_id: uuid.UUID, body: HouseholdUpdate, db: DbSession, user: CurrentUser
):
    me = svc.require_membership(db, household_id, user, admin=True)
    svc.update_household(db, me.household, body.name, body.address, body.timezone)
    return svc.household_out(me)


@router.delete("/households/{household_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_household(household_id: uuid.UUID, db: DbSession, user: CurrentUser):
    """Admins only, for everyone in it. Not the last home you're an admin of (409)."""
    me = svc.require_membership(db, household_id, user, admin=True)
    svc.delete_household(db, me, user)


@router.get("/households/{household_id}/members", response_model=list[MemberOut])
def list_members(household_id: uuid.UUID, db: DbSession, user: CurrentUser):
    me = svc.require_membership(db, household_id, user)
    invited = svc.invited_emails(db, household_id)
    return [svc.member_out(m, invited) for m in me.household.members if m.is_active]


@router.post(
    "/households/{household_id}/members",
    response_model=MemberAdded,
    status_code=status.HTTP_201_CREATED,
)
def add_member(household_id: uuid.UUID, body: MemberCreate, db: DbSession, user: CurrentUser):
    """Add someone who hasn't signed up, with an email or phone. An email gets the invite right away;
    for a phone, the app offers their personal link on WhatsApp."""
    me = svc.require_membership(db, household_id, user, admin=True)
    address = body.email.lower() if body.email else None
    if address and svc.email_in_house(me.household, address):
        raise HTTPException(status.HTTP_409_CONFLICT, "Someone in the house already has that email")
    member = svc.add_member(
        db, me.household, body.display_name.strip(), actor=me, email=address, phone=body.phone
    )
    emailed = False
    if address:
        results = invite_svc.invite(db, me, [address]).results
        emailed = results[0].status == "sent"
    db.refresh(member)
    return MemberAdded(
        member=svc.member_out(member, svc.invited_emails(db, household_id)),
        emailed=emailed,
        email_enabled=email.enabled(),
        link=svc.personal_link(member),
    )


@router.patch("/members/{member_id}", response_model=MemberOut)
def update_member(member_id: uuid.UUID, body: MemberUpdate, db: DbSession, user: CurrentUser):
    member = svc.get_member(db, member_id)
    me = svc.require_membership(db, member.household_id, user, admin=True)
    if body.display_name is not None:
        member.display_name = body.display_name.strip()
    if body.role is not None and member.id != me.id:
        if body.role == "admin" and member.role != "admin" and not (member.user and member.user.is_confirmed):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "Only people with a confirmed email (or who signed up with Google, Apple or Facebook) can be admins",
            )
        member.role = body.role
    if body.email and member.user_id is not None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Their email comes from their account")
    if body.email is not None and member.user_id is None:
        member.email = body.email.lower() or None
    if body.phone is not None:
        member.phone = body.phone.strip() or None
    if member.user_id is None and (body.email is not None or body.phone is not None):
        if not member.email and not member.phone:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "Keep an email or phone number so they can be invited"
            )
    db.commit()
    return svc.member_out(member, svc.invited_emails(db, member.household_id))


@router.delete("/members/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(member_id: uuid.UUID, db: DbSession, user: CurrentUser):
    member = svc.get_member(db, member_id)
    me = svc.require_membership(db, member.household_id, user, admin=True)
    svc.deactivate_member(db, member, acting=me)


@router.post("/households/{household_id}/email-invites", response_model=EmailInviteResults)
def invite_by_email(household_id: uuid.UUID, body: InviteEmails, db: DbSession, user: CurrentUser):
    """Anyone in the house. Each address is saved as pending and emailed when email is set up."""
    me = svc.require_membership(db, household_id, user)
    return invite_svc.invite(db, me, [str(e) for e in body.emails])


@router.get("/households/{household_id}/email-invites", response_model=list[EmailInviteOut])
def pending_invites(household_id: uuid.UUID, db: DbSession, user: CurrentUser):
    me = svc.require_membership(db, household_id, user)
    return invite_svc.pending(db, me)


@router.delete("/email-invites/{invite_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancel_invite(invite_id: uuid.UUID, db: DbSession, user: CurrentUser):
    row = invite_svc.get(db, invite_id)
    me = svc.require_membership(db, row.household_id, user)
    invite_svc.cancel(db, row, me)


@router.get("/me/invites", response_model=list[MyInvite])
def my_invites(db: DbSession, user: CurrentUser):
    """Houses that invited my email and I haven't joined: shown on the welcome screen."""
    return invite_svc.mine(db, user)


@router.get("/invite-links/{token}", response_model=InviteLinkPublic)
def invite_link_public(token: str, db: DbSession):
    """No sign-in needed: the page a private invite link opens. Anything but a pending, unexpired
    invite (cancelled, used, expired, made up) gets the same 404."""
    row = invite_svc.find_open(db, token)
    household = row.household
    return InviteLinkPublic(
        household_name=household.name,
        people=sum(1 for m in household.members if m.is_active),
        email=row.email,
        invited_by=row.invited_by.display_name if row.invited_by else None,
    )


@router.post("/invite-links/{token}/accept", response_model=HouseholdOut)
def accept_invite_link(token: str, db: DbSession, user: CurrentUser):
    """Join with a private invite link: only while it's pending, and only as the invited email."""
    member = svc.accept_invite_link(db, token, user)
    return svc.household_out(member)


@router.post("/households/{household_id}/invite-code", response_model=HouseholdOut)
def reset_invite_code(household_id: uuid.UUID, db: DbSession, user: CurrentUser):
    """Admins: a new shared code. Every old shared link and code stops working."""
    me = svc.require_membership(db, household_id, user, admin=True)
    svc.reset_invite_code(db, me)
    return svc.household_out(me)


@router.get("/invites/{code}/public", response_model=InvitePublic)
def public_invite(code: str, db: DbSession):
    """No sign-in needed: an invite link's landing page shows the house name and how many live there.

    Names stay private until signed in (see GET /invites/{code}).
    """
    household = svc.find_by_invite(db, code)
    return InvitePublic(
        household_name=household.name, people=sum(1 for m in household.members if m.is_active)
    )


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
