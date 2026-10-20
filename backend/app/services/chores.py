import uuid
from datetime import date

from sqlalchemy import delete, exists, func, select
from sqlalchemy.orm import Session

from app.models import Chore, ChoreRotationMember, ChoreTask, Household, HouseholdMember
from app.services import rotation
from app.services.errors import BadRequest, NotFound

DEFAULT_CHORES = ("Cooking", "Clean hall", "Dispose garbage")


def get_chore(db: Session, chore_id: uuid.UUID) -> Chore:
    chore = db.get(Chore, chore_id)
    if chore is None:
        raise NotFound("Chore not found")
    return chore


def list_chores(db: Session, household_id: uuid.UUID, include_inactive: bool = True) -> list[Chore]:
    query = select(Chore).where(Chore.household_id == household_id)
    if not include_inactive:
        query = query.where(Chore.is_active.is_(True))
    return list(db.scalars(query.order_by(Chore.position, Chore.created_at)))


def create_chore(
    db: Session,
    household: Household,
    name: str,
    member_ids: list[uuid.UUID] | None,
    today: date,
) -> Chore:
    existing = (
        db.scalar(select(func.count(Chore.id)).where(Chore.household_id == household.id)) or 0
    )
    chore = Chore(
        household_id=household.id,
        name=name,
        position=existing,
        frequency="daily",
        rotation_start_date=rotation.staggered_start(today, existing),
        is_active=True,
    )
    db.add(chore)
    db.flush()
    if member_ids is None:
        member_ids = [m.id for m in active_members(db, household.id)]
    set_rotation(db, chore, member_ids, today)
    return chore


def active_members(db: Session, household_id: uuid.UUID) -> list[HouseholdMember]:
    return list(
        db.scalars(
            select(HouseholdMember)
            .where(HouseholdMember.household_id == household_id, HouseholdMember.is_active)
            .order_by(HouseholdMember.created_at)
        )
    )


def set_rotation(db: Session, chore: Chore, member_ids: list[uuid.UUID], today: date) -> None:
    """Replace a chore's ordered rotation.

    Once a rotation has history (tasks before today), the start date is rebased so the
    current person keeps today and the cycle continues. During initial setup (no history yet)
    the start date is kept, which preserves the stagger between chores.
    """
    if len(set(member_ids)) != len(member_ids):
        raise BadRequest("A member can appear only once in a rotation")
    valid = {m.id for m in active_members(db, chore.household_id)}
    if not set(member_ids) <= valid:
        raise BadRequest("Rotation contains people who are not active members of this household")

    old = [r.member_id for r in chore.rotation]
    if old == member_ids:
        return

    has_history = db.scalar(
        select(exists().where(ChoreTask.chore_id == chore.id, ChoreTask.due_date < today))
    )
    if has_history:
        chore.rotation_start_date = rotation.rebased_start(
            old, member_ids, chore.rotation_start_date, today
        )

    for row in chore.rotation:
        db.expunge(row)
    db.execute(delete(ChoreRotationMember).where(ChoreRotationMember.chore_id == chore.id))
    db.add_all(
        ChoreRotationMember(chore_id=chore.id, position=i, member_id=member_id)
        for i, member_id in enumerate(member_ids)
    )
    db.flush()
    db.expire(chore, ["rotation"])


def add_member_to_rotations(db: Session, member: HouseholdMember, today: date) -> None:
    for chore in list_chores(db, member.household_id, include_inactive=False):
        ids = [r.member_id for r in chore.rotation]
        if member.id not in ids:
            set_rotation(db, chore, [*ids, member.id], today)


def remove_member_from_rotations(db: Session, member: HouseholdMember, today: date) -> None:
    for chore in list_chores(db, member.household_id):
        ids = [r.member_id for r in chore.rotation]
        if member.id in ids:
            set_rotation(db, chore, [i for i in ids if i != member.id], today)
