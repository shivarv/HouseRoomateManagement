import secrets
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Household, HouseholdMember, User
from app.schemas.household import HouseholdOut, MemberOut
from app.services import chores, clock
from app.services.errors import BadRequest, Conflict, Forbidden, NotFound

# No 0/O/1/I so codes are easy to read out loud.
INVITE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def _new_invite_code(db: Session) -> str:
    while True:
        code = "".join(secrets.choice(INVITE_ALPHABET) for _ in range(8))
        if db.scalar(select(Household.id).where(Household.invite_code == code)) is None:
            return code


def create_household(db: Session, user: User, name: str, timezone: str) -> HouseholdMember:
    household = Household(name=name, timezone=timezone, invite_code=_new_invite_code(db))
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
    for chore_name in chores.DEFAULT_CHORES:
        chores.create_chore(db, household, chore_name, member_ids=None, today=today)
    db.commit()
    return admin


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
    db: Session, household: Household, display_name: str, user_id: uuid.UUID | None = None
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
    db.commit()
    return member


def deactivate_member(db: Session, member: HouseholdMember, acting: HouseholdMember) -> None:
    if member.id == acting.id:
        raise BadRequest("You can't remove yourself")
    member.is_active = False
    member.user_id = None
    db.flush()
    chores.remove_member_from_rotations(db, member, clock.today_in(member.household.timezone))
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
        return add_member(db, household, display_name or user.name, user_id=user.id)
    member = next((m for m in unclaimed_members(household) if m.id == member_id), None)
    if member is None:
        raise BadRequest("That person has already been claimed or does not exist")
    member.user_id = user.id
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
        timezone=h.timezone,
        invite_code=h.invite_code,
        my_member_id=me.id,
        my_role=me.role,
    )
