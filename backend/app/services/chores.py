import uuid
from datetime import date

from sqlalchemy import delete, exists, func, select
from sqlalchemy.orm import Session

from app.models import Chore, ChoreRotationMember, ChoreTask, Household, HouseholdMember
from app.services import rotation
from app.services.errors import BadRequest, NotFound

# (name, assignment mode). Garbage isn't turn-based: whoever does it logs it.
DEFAULT_CHORES = (("Cooking", "rotation"), ("Clean hall", "rotation"), ("Dispose garbage", "open"))


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


def _staggered_start(db: Session, household_id: uuid.UUID, frequency: str, today: date) -> date:
    """Each chore of the same frequency starts one slot later than the previous one."""
    same_kind = (
        db.scalar(
            select(func.count(Chore.id)).where(
                Chore.household_id == household_id, Chore.frequency == frequency
            )
        )
        or 0
    )
    return rotation.staggered_start(
        rotation.period_start(today, frequency), same_kind, rotation.step_days(frequency)
    )


def create_chore(
    db: Session,
    household: Household,
    name: str,
    member_ids: list[uuid.UUID] | None,
    today: date,
    frequency: str = "daily",
    assignment_mode: str = "rotation",
    target_per_week: int | None = None,
) -> Chore:
    position = db.scalar(select(func.count(Chore.id)).where(Chore.household_id == household.id))
    chore = Chore(
        household_id=household.id,
        name=name,
        position=position or 0,
        frequency=frequency,
        assignment_mode=assignment_mode,
        target_per_week=target_per_week,
        rotation_start_date=_staggered_start(db, household.id, frequency, today),
        tracked_from=today,
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


def _drop_pending_current(db: Session, chore: Chore, today: date) -> None:
    db.execute(
        delete(ChoreTask).where(
            ChoreTask.chore_id == chore.id,
            ChoreTask.status == "pending",
            ChoreTask.due_date >= rotation.period_start(today, chore.frequency),
        )
    )


def update_settings(
    db: Session,
    chore: Chore,
    today: date,
    *,
    is_active: bool | None = None,
    frequency: str | None = None,
    assignment_mode: str | None = None,
    target_per_week: int | None = None,
) -> list[str]:
    """Apply setting changes; returns human-readable descriptions for the activity feed."""
    changes: list[str] = []
    if frequency is not None and frequency != chore.frequency:
        _drop_pending_current(db, chore, today)
        chore.rotation_start_date = _staggered_start(db, chore.household_id, frequency, today)
        chore.frequency = frequency
        chore.tracked_from = today
        changes.append(f"now {frequency}")
    if assignment_mode is not None and assignment_mode != chore.assignment_mode:
        _drop_pending_current(db, chore, today)
        chore.assignment_mode = assignment_mode
        chore.tracked_from = today
        changes.append("now open to anyone" if assignment_mode == "open" else "now a rotation")
    if target_per_week is not None:
        chore.target_per_week = target_per_week or None
        changes.append(
            f"target {target_per_week}× per week" if target_per_week else "target removed"
        )
    if is_active is not None and is_active != chore.is_active:
        chore.is_active = is_active
        if is_active:
            chore.tracked_from = today  # paused periods don't count as missed
        else:
            _drop_pending_current(db, chore, today)
        changes.append("resumed" if is_active else "paused")
    db.flush()
    return changes


def set_rotation(db: Session, chore: Chore, member_ids: list[uuid.UUID], today: date) -> None:
    """Replace a chore's ordered rotation.

    Once a rotation has history (tasks before the current period), the start date is rebased so
    the current person keeps the current period and the cycle continues. During initial setup
    (no history yet) the start date is kept, which preserves the stagger between chores.
    """
    from app.services import tasks  # local import: tasks depends on this module

    if len(set(member_ids)) != len(member_ids):
        raise BadRequest("A member can appear only once in a rotation")
    valid = {m.id for m in active_members(db, chore.household_id)}
    if not set(member_ids) <= valid:
        raise BadRequest("Rotation contains people who are not active members of this household")

    old = [r.member_id for r in chore.rotation]
    if old == member_ids:
        return

    current = rotation.period_start(today, chore.frequency)
    # Record past turns with the old order before it changes.
    tasks.ensure_chore(db, chore, today, include_current=False)
    has_history = db.scalar(
        select(exists().where(ChoreTask.chore_id == chore.id, ChoreTask.due_date < current))
    )
    if has_history:
        chore.rotation_start_date = rotation.rebased_start(
            old, member_ids, chore.rotation_start_date, current, rotation.step_days(chore.frequency)
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
