import secrets
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Household, HouseholdMember, User
from app.schemas.household import HouseholdOut, MemberOut
from app.services import activity, bills, chores, clock, grocery_settings
from app.services.errors import BadRequest, Conflict, Forbidden, NotFound

# No 0/O/1/I so codes are easy to read out loud.
INVITE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def _new_invite_code(db: Session) -> str:
    while True:
        code = "".join(secrets.choice(INVITE_ALPHABET) for _ in range(8))
        if db.scalar(select(Household.id).where(Household.invite_code == code)) is None:
            return code


def _ensure_name_free(
    db: Session, creator_id: uuid.UUID | None, name: str, exclude: uuid.UUID | None = None
) -> None:
    """Names are unique per creator (backed by uq_households_creator_name)."""
    if creator_id is None:
        return
    query = select(Household.id).where(
        Household.created_by_id == creator_id, func.lower(Household.name) == name.lower()
    )
    if exclude is not None:
        query = query.where(Household.id != exclude)
    if db.scalar(query) is not None:
        raise Conflict(f"You already have a house called “{name}”")


def create_household(
    db: Session, user: User, name: str, address: str, timezone: str
) -> HouseholdMember:
    name, address = name.strip(), address.strip()
    if not name or not address:
        raise BadRequest("A house needs a name and an address")
    _ensure_name_free(db, user.id, name)
    household = Household(
        name=name,
        address=address,
        timezone=timezone,
        invite_code=_new_invite_code(db),
        created_by_id=user.id,
    )
    db.add(household)
    db.flush()
    admin = HouseholdMember(
        household_id=household.id,
        display_name=user.name,
        user_id=user.id,
        role="admin",
        is_active=True,
    )
    db.add(admin)
    db.flush()
    today = clock.today_in(timezone)
    for chore_name, mode in chores.DEFAULT_CHORES:
        chores.create_chore(
            db, household, chore_name, member_ids=None, today=today, assignment_mode=mode
        )
    grocery_settings.seed(db, household.id)
    bills.seed(db, household.id)
    user.last_household_id = household.id  # a new house opens on every device
    db.commit()
    return admin


def update_household(
    db: Session, household: Household, name: str | None, address: str | None, timezone: str | None
) -> None:
    if name is not None:
        name = name.strip()
        if not name:
            raise BadRequest("A house needs a name")
        _ensure_name_free(db, household.created_by_id, name, exclude=household.id)
        household.name = name
    if address is not None:
        if not address.strip():
            raise BadRequest("A house needs an address")
        household.address = address.strip()
    if timezone is not None:
        household.timezone = timezone
    db.commit()


def memberships(db: Session, user: User) -> list[HouseholdMember]:
    return list(
        db.scalars(
            select(HouseholdMember)
            .where(HouseholdMember.user_id == user.id, HouseholdMember.is_active)
            .order_by(HouseholdMember.created_at)
        )
    )


def require_membership(
    db: Session, household_id: uuid.UUID, user: User, admin: bool = False
) -> HouseholdMember:
    member = db.scalar(
        select(HouseholdMember).where(
            HouseholdMember.household_id == household_id,
            HouseholdMember.user_id == user.id,
            HouseholdMember.is_active,
        )
    )
    if member is None:
        raise NotFound("Household not found")
    if admin and member.role != "admin":
        raise Forbidden("Only a household admin can do this")
    return member


def get_member(db: Session, member_id: uuid.UUID) -> HouseholdMember:
    member = db.get(HouseholdMember, member_id)
    if member is None:
        raise NotFound("Member not found")
    return member


def add_member(
    db: Session,
    household: Household,
    display_name: str,
    user_id: uuid.UUID | None = None,
    actor: HouseholdMember | None = None,
) -> HouseholdMember:
    member = HouseholdMember(
        household_id=household.id,
        display_name=display_name,
        user_id=user_id,
        role="member",
        is_active=True,
    )
    db.add(member)
    db.flush()
    chores.add_member_to_rotations(db, member, clock.today_in(household.timezone))
    if actor is not None:
        activity.record(db, household.id, "member_added", actor, subject_id=member.id)
    db.commit()
    return member


def deactivate_member(db: Session, member: HouseholdMember, acting: HouseholdMember) -> None:
    if member.id == acting.id:
        raise BadRequest("You can't remove yourself")
    member.is_active = False
    member.user_id = None
    db.flush()
    chores.remove_member_from_rotations(db, member, clock.today_in(member.household.timezone))
    activity.record(db, member.household_id, "member_removed", acting, subject_id=member.id)
    db.commit()


def find_by_invite(db: Session, code: str) -> Household:
    household = db.scalar(select(Household).where(Household.invite_code == code.upper()))
    if household is None:
        raise NotFound("Invalid invite code")
    return household


def unclaimed_members(household: Household) -> list[HouseholdMember]:
    return [m for m in household.members if m.is_active and m.user_id is None]


def accept_invite(
    db: Session,
    household: Household,
    user: User,
    member_id: uuid.UUID | None,
    display_name: str | None,
) -> HouseholdMember:
    if any(m.user_id == user.id and m.is_active for m in household.members):
        raise Conflict("You are already a member of this household")
    if member_id is None:
        member = add_member(db, household, display_name or user.name, user_id=user.id)
    else:
        member = next((m for m in unclaimed_members(household) if m.id == member_id), None)
        if member is None:
            raise BadRequest("That person has already been claimed or does not exist")
        member.user_id = user.id
    activity.record(db, household.id, "member_joined", member, subject_id=member.id)
    user.last_household_id = household.id
    db.commit()
    return member


def member_out(member: HouseholdMember) -> MemberOut:
    return MemberOut(
        id=member.id,
        display_name=member.display_name,
        role=member.role,
        is_active=member.is_active,
        has_account=member.user_id is not None,
    )


def household_out(me: HouseholdMember) -> HouseholdOut:
    h = me.household
    return HouseholdOut(
        id=h.id,
        name=h.name,
        address=h.address,
        timezone=h.timezone,
        invite_code=h.invite_code,
        created_by_me=h.created_by_id is not None and h.created_by_id == me.user_id,
        my_member_id=me.id,
        my_role=me.role,
    )
