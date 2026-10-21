import uuid
from collections import Counter
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import Chore, ChoreLog, ChoreTask, Household, HouseholdMember
from app.schemas.chore import (
    ChoreBrief,
    LogOut,
    OpenChoreCount,
    OpenChoreOut,
    ScheduleDay,
    ScheduleSlot,
    TaskOut,
    UpcomingTurn,
)
from app.schemas.household import MemberBrief
from app.services import activity, chores, rotation, suggest
from app.services.errors import BadRequest, NotFound

OVERDUE_LOOKBACK_DAYS = 7
MAX_SCHEDULE_DAYS = 31
MAX_BACKFILL_DAYS = 31


# --- Generating turns -------------------------------------------------------------------------


def _upsert_turn(db: Session, chore: Chore, member_id: uuid.UUID, due: date) -> None:
    db.execute(
        insert(ChoreTask)
        .values(
            id=uuid.uuid4(), chore_id=chore.id, member_id=member_id, due_date=due, status="pending"
        )
        .on_conflict_do_nothing(index_elements=["chore_id", "due_date"])
    )


def ensure_chore(db: Session, chore: Chore, today: date, include_current: bool = True) -> None:
    """Persist this chore's turns from its last recorded turn up to the current period.

    Past periods nobody opened the app for are filled in (so they show up as missed), but never
    before `tracked_from` or more than a month back. The current period's pending turn follows
    the current rotation; completed turns are never changed. Idempotent and concurrency-safe.
    """
    current = rotation.period_start(today, chore.frequency)
    order = [r.member_id for r in chore.rotation]
    if not chore.is_active or chore.is_open or not order:
        db.execute(
            delete(ChoreTask).where(
                ChoreTask.chore_id == chore.id,
                ChoreTask.status == "pending",
                ChoreTask.due_date >= current,
            )
        )
        return

    step = rotation.step_days(chore.frequency)
    last = db.scalar(
        select(func.max(ChoreTask.due_date)).where(
            ChoreTask.chore_id == chore.id, ChoreTask.due_date < current
        )
    )
    floor = max(
        rotation.period_start(chore.tracked_from, chore.frequency),
        rotation.period_start(today - timedelta(days=MAX_BACKFILL_DAYS), chore.frequency),
    )
    day = (
        max(rotation.period_start(last + timedelta(days=step), chore.frequency), floor)
        if last
        else floor
    )
    while day < current:
        _upsert_turn(db, chore, rotation.assignee(order, chore.rotation_start_date, day, step), day)
        day += timedelta(days=step)

    if include_current:
        member_id = rotation.assignee(order, chore.rotation_start_date, current, step)
        _upsert_turn(db, chore, member_id, current)
        db.execute(
            update(ChoreTask)
            .where(
                ChoreTask.chore_id == chore.id,
                ChoreTask.due_date == current,
                ChoreTask.status == "pending",
                ChoreTask.member_id != member_id,
            )
            .values(member_id=member_id)
        )


def sync(db: Session, household: Household, today: date) -> None:
    """Bring every chore's turns up to date, then commit."""
    for chore in chores.list_chores(db, household.id, include_inactive=False):
        ensure_chore(db, chore, today)
    db.commit()


def current_tasks(db: Session, household_id: uuid.UUID, today: date) -> list[ChoreTask]:
    """Turns for today (daily chores) and this week (weekly chores)."""
    monday = rotation.period_start(today, "weekly")
    return list(
        db.scalars(
            select(ChoreTask)
            .join(Chore)
            .where(
                Chore.household_id == household_id,
                Chore.is_active,
                Chore.assignment_mode == "rotation",
                or_(
                    and_(Chore.frequency == "daily", ChoreTask.due_date == today),
                    and_(Chore.frequency == "weekly", ChoreTask.due_date == monday),
                ),
            )
            .order_by(Chore.frequency, Chore.position, Chore.created_at)
            .execution_options(populate_existing=True)
        ).unique()
    )


def overdue_for(db: Session, today_by_member: dict[uuid.UUID, date]) -> list[ChoreTask]:
    """My pending turns whose period ended in the last week."""
    if not today_by_member:
        return []
    earliest = min(today_by_member.values()) - timedelta(days=OVERDUE_LOOKBACK_DAYS + 7)
    rows = db.scalars(
        select(ChoreTask)
        .join(Chore)
        .where(
            ChoreTask.member_id.in_(list(today_by_member)),
            ChoreTask.status == "pending",
            ChoreTask.due_date >= earliest,
            Chore.is_active,
            Chore.assignment_mode == "rotation",
        )
        .order_by(ChoreTask.due_date)
    ).unique()
    result = []
    for t in rows:
        today = today_by_member[t.member_id]
        end = rotation.period_end(t.due_date, t.chore.frequency)
        if today - timedelta(days=OVERDUE_LOOKBACK_DAYS) <= end < today:
            result.append(t)
    return result


# --- Completing turns -------------------------------------------------------------------------


def get_task(db: Session, task_id: uuid.UUID) -> ChoreTask:
    task = db.get(ChoreTask, task_id)
    if task is None:
        raise NotFound("Task not found")
    return task


def _household_member(
    db: Session, household_id: uuid.UUID, member_id: uuid.UUID
) -> HouseholdMember:
    member = db.get(HouseholdMember, member_id)
    if member is None or member.household_id != household_id or not member.is_active:
        raise BadRequest("That person is not an active member of this household")
    return member


def complete(
    db: Session, task: ChoreTask, actor: HouseholdMember, completed_by_id: uuid.UUID | None
) -> ChoreTask:
    """Anyone in the house can mark a turn done, for themselves or on behalf of someone else."""
    doer = _household_member(db, actor.household_id, completed_by_id or actor.id)
    task.status = "done"
    task.completed_at = datetime.now(UTC)
    task.completed_by_id = doer.id
    activity.record(
        db,
        actor.household_id,
        "completed",
        actor,
        chore=task.chore,
        subject_id=doer.id,
        assignee_id=task.member_id,
        due_date=task.due_date,
    )
    db.commit()
    db.refresh(task)
    return task


def reopen(db: Session, task: ChoreTask, actor: HouseholdMember) -> ChoreTask:
    if task.status != "done":
        return task
    previous = task.completed_by_id
    task.status = "pending"
    task.completed_at = None
    task.completed_by_id = None
    activity.record(
        db,
        actor.household_id,
        "reopened",
        actor,
        chore=task.chore,
        subject_id=previous,
        assignee_id=task.member_id,
        due_date=task.due_date,
    )
    db.commit()
    db.refresh(task)
    return task


# --- Open chores ------------------------------------------------------------------------------


def add_log(
    db: Session, chore: Chore, actor: HouseholdMember, member_id: uuid.UUID | None, today: date
) -> ChoreLog:
    if not chore.is_open:
        raise BadRequest("This chore uses a rotation; mark its turn done instead")
    if not chore.is_active:
        raise BadRequest("This chore is paused")
    doer = _household_member(db, chore.household_id, member_id or actor.id)
    log = ChoreLog(chore_id=chore.id, member_id=doer.id, logged_by_id=actor.id, done_on=today)
    db.add(log)
    activity.record(
        db, chore.household_id, "logged", actor, chore=chore, subject_id=doer.id, due_date=today
    )
    db.commit()
    db.refresh(log)
    return log


def get_log(db: Session, log_id: uuid.UUID) -> ChoreLog:
    log = db.get(ChoreLog, log_id)
    if log is None:
        raise NotFound("Log entry not found")
    return log


def remove_log(db: Session, log: ChoreLog, actor: HouseholdMember) -> None:
    activity.record(
        db,
        log.chore.household_id,
        "log_removed",
        actor,
        chore=log.chore,
        subject_id=log.member_id,
        due_date=log.done_on,
    )
    db.delete(log)
    db.commit()


def log_out(log: ChoreLog) -> LogOut:
    return LogOut(
        id=log.id,
        member=_brief(log.member),
        logged_by=_brief(log.logged_by) if log.logged_by else None,
        done_on=log.done_on,
        created_at=log.created_at,
    )


def open_chores(db: Session, household: Household, today: date) -> list[OpenChoreOut]:
    active_open = [
        c for c in chores.list_chores(db, household.id, include_inactive=False) if c.is_open
    ]
    if not active_open:
        return []
    month_start = today.replace(day=1)
    year_start = today.replace(month=1, day=1)
    week_start = rotation.period_start(today, "weekly")
    members = chores.active_members(db, household.id)
    result = []
    for chore in active_open:
        logs = list(
            db.scalars(
                select(ChoreLog)
                .where(
                    ChoreLog.chore_id == chore.id, ChoreLog.done_on >= min(year_start, week_start)
                )
                .order_by(ChoreLog.created_at.desc())
            ).unique()
        )
        last = (
            logs[0]
            if logs
            else db.scalars(
                select(ChoreLog)
                .where(ChoreLog.chore_id == chore.id)
                .order_by(ChoreLog.created_at.desc())
                .limit(1)
            ).first()
        )
        month_counts = Counter(log.member_id for log in logs if log.done_on >= month_start)
        year_counts = Counter(log.member_id for log in logs if log.done_on >= year_start)
        last_by_member: dict = {}
        for log in logs:  # newest first, so the first one seen per person is their latest
            last_by_member.setdefault(log.member_id, log.done_on)
        ranked = suggest.rank(
            [m.id for m in members],
            year_counts,
            month_counts,
            last_by_member,
            seed=f"{chore.id}:{today.isoformat()}",
        )
        by_id = {m.id: m for m in members}
        people = [
            OpenChoreCount(
                member=_brief(by_id[mid]),
                this_year=year_counts[mid],
                this_month=month_counts[mid],
                last_done=last_by_member.get(mid),
            )
            for mid in ranked
        ]
        result.append(
            OpenChoreOut(
                household_id=household.id,
                household_name=household.name,
                chore=_chore_brief(chore),
                target_per_week=chore.target_per_week,
                today_logs=[log_out(log) for log in logs if log.done_on == today],
                this_week_count=sum(1 for log in logs if log.done_on >= week_start),
                last_done=log_out(last) if last else None,
                people=people,
                suggested=people[0].member if people else None,
                suggested_reason=(
                    suggest.reason(people[0].this_year, people[0].this_month) if people else None
                ),
            )
        )
    return result


def upcoming_for(db: Session, me: HouseholdMember, today: date) -> list[UpcomingTurn]:
    """My next turn for each active rotation chore I'm in."""
    household = me.household
    result = []
    for chore in chores.list_chores(db, household.id, include_inactive=False):
        if chore.is_open:
            continue
        when = rotation.next_turn(
            [r.member_id for r in chore.rotation],
            chore.rotation_start_date,
            rotation.period_start(today, chore.frequency),
            me.id,
            rotation.step_days(chore.frequency),
        )
        if when is not None:
            result.append(
                UpcomingTurn(
                    household_id=household.id,
                    household_name=household.name,
                    chore=_chore_brief(chore),
                    due_date=when,
                )
            )
    return result


# --- Output -----------------------------------------------------------------------------------


def _brief(member: HouseholdMember) -> MemberBrief:
    return MemberBrief(id=member.id, display_name=member.display_name)


def _chore_brief(chore: Chore) -> ChoreBrief:
    return ChoreBrief(
        id=chore.id,
        name=chore.name,
        frequency=chore.frequency,
        assignment_mode=chore.assignment_mode,
    )


def task_out(task: ChoreTask, household: Household, me: HouseholdMember | None) -> TaskOut:
    chore = task.chore
    step = rotation.step_days(chore.frequency)
    order = [r.member for r in chore.rotation]
    nxt = rotation.assignee(
        order, chore.rotation_start_date, task.due_date + timedelta(days=step), step
    )
    return TaskOut(
        id=task.id,
        household_id=household.id,
        household_name=household.name,
        chore=_chore_brief(chore),
        member=_brief(task.member),
        due_date=task.due_date,
        period_end=rotation.period_end(task.due_date, chore.frequency),
        status=task.status,
        completed_at=task.completed_at,
        completed_by=_brief(task.completed_by) if task.completed_by else None,
        next_assignee=_brief(nxt) if nxt else None,
        is_mine=me is not None and task.member_id == me.id,
    )


def schedule(
    db: Session, household: Household, today: date, start: date, days: int
) -> list[ScheduleDay]:
    """Past/current turns come from the database; future ones are projected from the rotation."""
    days = max(1, min(days, MAX_SCHEDULE_DAYS))
    end = start + timedelta(days=days - 1)
    sync(db, household, today)

    active = [
        c for c in chores.list_chores(db, household.id, include_inactive=False) if not c.is_open
    ]
    stored = {
        (t.chore_id, t.due_date): t
        for t in db.scalars(
            select(ChoreTask).where(
                ChoreTask.chore_id.in_([c.id for c in active]),
                ChoreTask.due_date.between(rotation.period_start(start, "weekly"), end),
            )
        ).unique()
    }

    result = []
    for offset in range(days):
        day = start + timedelta(days=offset)
        slots = []
        for chore in active:
            period = rotation.period_start(day, chore.frequency)
            task = stored.get((chore.id, period))
            if task is not None:
                slots.append(
                    ScheduleSlot(
                        chore=_chore_brief(chore), member=_brief(task.member), status=task.status
                    )
                )
            elif period >= rotation.period_start(today, chore.frequency):
                member = rotation.assignee(
                    [r.member for r in chore.rotation],
                    chore.rotation_start_date,
                    period,
                    rotation.step_days(chore.frequency),
                )
                if member is not None:
                    slots.append(
                        ScheduleSlot(chore=_chore_brief(chore), member=_brief(member), status=None)
                    )
        result.append(ScheduleDay(date=day, slots=slots))
    return result
