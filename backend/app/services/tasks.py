import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import Chore, ChoreTask, Household, HouseholdMember
from app.schemas.chore import ChoreBrief, ScheduleDay, ScheduleSlot, TaskOut
from app.schemas.household import MemberBrief
from app.services import chores, rotation
from app.services.errors import Forbidden, NotFound

OVERDUE_LOOKBACK_DAYS = 7
MAX_SCHEDULE_DAYS = 31


def ensure_tasks(db: Session, household: Household, on: date) -> None:
    """Persist the assignment of every active chore for `on` (idempotent, concurrency-safe).

    A pending task is re-pointed if the rotation changed; completed tasks are never touched.
    """
    for chore in chores.list_chores(db, household.id, include_inactive=False):
        member_id = rotation.assignee(
            [r.member_id for r in chore.rotation], chore.rotation_start_date, on
        )
        if member_id is None:
            db.execute(
                delete(ChoreTask).where(
                    ChoreTask.chore_id == chore.id,
                    ChoreTask.due_date == on,
                    ChoreTask.status == "pending",
                )
            )
            continue
        db.execute(
            insert(ChoreTask)
            .values(
                id=uuid.uuid4(),
                chore_id=chore.id,
                member_id=member_id,
                due_date=on,
                status="pending",
            )
            .on_conflict_do_nothing(index_elements=["chore_id", "due_date"])
        )
        db.execute(
            update(ChoreTask)
            .where(
                ChoreTask.chore_id == chore.id,
                ChoreTask.due_date == on,
                ChoreTask.status == "pending",
                ChoreTask.member_id != member_id,
            )
            .values(member_id=member_id)
        )
    db.commit()


def tasks_on(db: Session, household_id: uuid.UUID, on: date) -> list[ChoreTask]:
    return list(
        db.scalars(
            select(ChoreTask)
            .join(Chore)
            .where(Chore.household_id == household_id, Chore.is_active, ChoreTask.due_date == on)
            .order_by(Chore.position, Chore.created_at)
            .execution_options(populate_existing=True)
        ).unique()
    )


def overdue_for(db: Session, today_by_member: dict[uuid.UUID, date]) -> list[ChoreTask]:
    """Pending tasks from the last week, given each of my member ids and its household's today."""
    member_ids = list(today_by_member)
    if not member_ids:
        return []
    rows = db.scalars(
        select(ChoreTask)
        .join(Chore)
        .where(
            ChoreTask.member_id.in_(member_ids),
            ChoreTask.status == "pending",
            Chore.is_active,
        )
        .order_by(ChoreTask.due_date)
    ).unique()
    return [
        t
        for t in rows
        if today_by_member[t.member_id] - timedelta(days=OVERDUE_LOOKBACK_DAYS)
        <= t.due_date
        < today_by_member[t.member_id]
    ]


def get_task(db: Session, task_id: uuid.UUID) -> ChoreTask:
    task = db.get(ChoreTask, task_id)
    if task is None:
        raise NotFound("Task not found")
    return task


def set_status(db: Session, task: ChoreTask, acting: HouseholdMember, done: bool) -> ChoreTask:
    if task.member_id != acting.id and acting.role != "admin":
        raise Forbidden("Only the assigned person or an admin can update this task")
    task.status = "done" if done else "pending"
    task.completed_at = datetime.now(UTC) if done else None
    db.commit()
    return task


def _brief(member: HouseholdMember) -> MemberBrief:
    return MemberBrief(id=member.id, display_name=member.display_name)


def task_out(task: ChoreTask, household: Household, me: HouseholdMember | None) -> TaskOut:
    chore = task.chore
    order = [r.member for r in chore.rotation]
    nxt = rotation.assignee(order, chore.rotation_start_date, task.due_date + timedelta(days=1))
    return TaskOut(
        id=task.id,
        household_id=household.id,
        household_name=household.name,
        chore=ChoreBrief(id=chore.id, name=chore.name),
        member=_brief(task.member),
        due_date=task.due_date,
        status=task.status,
        completed_at=task.completed_at,
        next_assignee=_brief(nxt) if nxt else None,
        is_mine=me is not None and task.member_id == me.id,
    )


def schedule(
    db: Session, household: Household, today: date, start: date, days: int
) -> list[ScheduleDay]:
    """Past/today come from persisted tasks; future days are projected from the rotation."""
    days = max(1, min(days, MAX_SCHEDULE_DAYS))
    end = start + timedelta(days=days - 1)
    if start <= today <= end:
        ensure_tasks(db, household, today)

    active = chores.list_chores(db, household.id, include_inactive=False)
    stored = {
        (t.chore_id, t.due_date): t
        for t in db.scalars(
            select(ChoreTask).where(
                ChoreTask.chore_id.in_([c.id for c in active]),
                ChoreTask.due_date.between(start, min(end, today)),
            )
        ).unique()
    }

    result = []
    for offset in range(days):
        day = start + timedelta(days=offset)
        slots = []
        for chore in active:
            brief = ChoreBrief(id=chore.id, name=chore.name)
            task = stored.get((chore.id, day))
            if task is not None:
                slots.append(
                    ScheduleSlot(chore=brief, member=_brief(task.member), status=task.status)
                )
            elif day >= today:
                member = rotation.assignee(
                    [r.member for r in chore.rotation], chore.rotation_start_date, day
                )
                if member is not None:
                    slots.append(ScheduleSlot(chore=brief, member=_brief(member), status=None))
        result.append(ScheduleDay(date=day, slots=slots))
    return result
