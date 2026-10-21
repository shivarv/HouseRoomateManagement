import uuid
from datetime import date

from fastapi import APIRouter, Query, status

from app.api.deps import CurrentUser, DbSession
from app.models import Chore, Household
from app.schemas.chore import (
    ChoreCreate,
    ChoreOut,
    ChoreUpdate,
    CompleteTask,
    HouseholdTasksToday,
    LogCreate,
    LogOut,
    MyTasksToday,
    OpenChoreOut,
    RotationUpdate,
    ScheduleOut,
    TaskOut,
)
from app.schemas.household import MemberBrief
from app.services import activity, clock
from app.services import chores as chore_svc
from app.services import households as household_svc
from app.services import tasks as task_svc

router = APIRouter(tags=["chores"])


def _chores_out(db, household: Household) -> list[ChoreOut]:
    today = clock.today_in(household.timezone)
    task_svc.sync(db, household, today)
    current = {t.chore_id: t.member for t in task_svc.current_tasks(db, household.id, today)}
    return [_chore_out(c, current.get(c.id)) for c in chore_svc.list_chores(db, household.id)]


def _chore_out(chore: Chore, current_member) -> ChoreOut:
    return ChoreOut(
        id=chore.id,
        name=chore.name,
        frequency=chore.frequency,
        assignment_mode=chore.assignment_mode,
        target_per_week=chore.target_per_week,
        is_active=chore.is_active,
        rotation=[MemberBrief.model_validate(r.member) for r in chore.rotation],
        today_assignee=MemberBrief.model_validate(current_member) if current_member else None,
    )


def _single_chore_out(db, chore: Chore) -> ChoreOut:
    household = db.get(Household, chore.household_id)
    return next(c for c in _chores_out(db, household) if c.id == chore.id)


@router.get("/households/{household_id}/chores", response_model=list[ChoreOut])
def list_chores(household_id: uuid.UUID, db: DbSession, user: CurrentUser):
    me = household_svc.require_membership(db, household_id, user)
    return _chores_out(db, me.household)


@router.post(
    "/households/{household_id}/chores",
    response_model=ChoreOut,
    status_code=status.HTTP_201_CREATED,
)
def create_chore(household_id: uuid.UUID, body: ChoreCreate, db: DbSession, user: CurrentUser):
    me = household_svc.require_membership(db, household_id, user, admin=True)
    household = me.household
    chore = chore_svc.create_chore(
        db,
        household,
        body.name.strip(),
        body.member_ids,
        clock.today_in(household.timezone),
        frequency=body.frequency,
        assignment_mode=body.assignment_mode,
        target_per_week=body.target_per_week,
    )
    kind = "open to anyone" if body.assignment_mode == "open" else "rotation"
    activity.record(
        db, household.id, "chore_created", me, chore=chore, detail=f"{body.frequency}, {kind}"
    )
    db.commit()
    return _single_chore_out(db, chore)


@router.patch("/chores/{chore_id}", response_model=ChoreOut)
def update_chore(chore_id: uuid.UUID, body: ChoreUpdate, db: DbSession, user: CurrentUser):
    chore = chore_svc.get_chore(db, chore_id)
    me = household_svc.require_membership(db, chore.household_id, user, admin=True)
    changes = []
    if body.name is not None and body.name.strip() != chore.name:
        changes.append(f"renamed from {chore.name}")
        chore.name = body.name.strip()
    changes += chore_svc.update_settings(
        db,
        chore,
        clock.today_in(me.household.timezone),
        is_active=body.is_active,
        frequency=body.frequency,
        assignment_mode=body.assignment_mode,
        target_per_week=body.target_per_week,
    )
    if changes:
        activity.record(
            db, chore.household_id, "chore_updated", me, chore=chore, detail=", ".join(changes)
        )
    db.commit()
    return _single_chore_out(db, chore)


@router.put("/chores/{chore_id}/rotation", response_model=ChoreOut)
def update_rotation(chore_id: uuid.UUID, body: RotationUpdate, db: DbSession, user: CurrentUser):
    chore = chore_svc.get_chore(db, chore_id)
    me = household_svc.require_membership(db, chore.household_id, user, admin=True)
    before = [r.member_id for r in chore.rotation]
    chore_svc.set_rotation(db, chore, body.member_ids, clock.today_in(me.household.timezone))
    if before != body.member_ids:
        activity.record(db, chore.household_id, "rotation_changed", me, chore=chore)
    db.commit()
    return _single_chore_out(db, chore)


@router.delete("/chores/{chore_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_chore(chore_id: uuid.UUID, db: DbSession, user: CurrentUser):
    chore = chore_svc.get_chore(db, chore_id)
    me = household_svc.require_membership(db, chore.household_id, user, admin=True)
    activity.record(db, chore.household_id, "chore_deleted", me, chore=chore)
    db.flush()
    db.delete(chore)
    db.commit()


@router.get("/households/{household_id}/schedule", response_model=ScheduleOut)
def get_schedule(
    household_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
    start: date | None = Query(default=None, alias="from"),
    days: int = Query(default=7, ge=1, le=task_svc.MAX_SCHEDULE_DAYS),
):
    me = household_svc.require_membership(db, household_id, user)
    today = clock.today_in(me.household.timezone)
    return ScheduleOut(days=task_svc.schedule(db, me.household, today, start or today, days))


@router.get("/households/{household_id}/tasks/today", response_model=HouseholdTasksToday)
def household_tasks_today(household_id: uuid.UUID, db: DbSession, user: CurrentUser):
    me = household_svc.require_membership(db, household_id, user)
    household = me.household
    today = clock.today_in(household.timezone)
    task_svc.sync(db, household, today)
    tasks = [
        task_svc.task_out(t, household, me) for t in task_svc.current_tasks(db, household.id, today)
    ]
    return HouseholdTasksToday(
        date=today, tasks=tasks, open=task_svc.open_chores(db, household, today)
    )


@router.get("/me/tasks/today", response_model=MyTasksToday)
def my_tasks_today(db: DbSession, user: CurrentUser):
    """The in-app reminder: my turns today/this week, missed ones, and chores anyone can do."""
    mine: list[TaskOut] = []
    others: list[TaskOut] = []
    upcoming = []
    open_chores: list[OpenChoreOut] = []
    today_by_member = {}
    me_by_member = {}
    for me in household_svc.memberships(db, user):
        household = me.household
        today = clock.today_in(household.timezone)
        today_by_member[me.id] = today
        me_by_member[me.id] = me
        task_svc.sync(db, household, today)
        for t in task_svc.current_tasks(db, household.id, today):
            (mine if t.member_id == me.id else others).append(task_svc.task_out(t, household, me))
        upcoming += task_svc.upcoming_for(db, me, today)
        open_chores += task_svc.open_chores(db, household, today)
    overdue = [
        task_svc.task_out(t, me_by_member[t.member_id].household, me_by_member[t.member_id])
        for t in task_svc.overdue_for(db, today_by_member)
    ]
    upcoming.sort(key=lambda u: u.due_date)
    return MyTasksToday(
        tasks=mine, others=others, upcoming=upcoming, overdue=overdue, open=open_chores
    )


@router.post("/tasks/{task_id}/complete", response_model=TaskOut)
def complete_task(
    task_id: uuid.UUID, db: DbSession, user: CurrentUser, body: CompleteTask | None = None
):
    task = task_svc.get_task(db, task_id)
    me = household_svc.require_membership(db, task.chore.household_id, user)
    task_svc.complete(db, task, me, body.completed_by_member_id if body else None)
    return task_svc.task_out(task, me.household, me)


@router.post("/tasks/{task_id}/reopen", response_model=TaskOut)
def reopen_task(task_id: uuid.UUID, db: DbSession, user: CurrentUser):
    task = task_svc.get_task(db, task_id)
    me = household_svc.require_membership(db, task.chore.household_id, user)
    task_svc.reopen(db, task, me)
    return task_svc.task_out(task, me.household, me)


@router.post("/chores/{chore_id}/logs", response_model=LogOut, status_code=status.HTTP_201_CREATED)
def log_open_chore(
    chore_id: uuid.UUID, db: DbSession, user: CurrentUser, body: LogCreate | None = None
):
    chore = chore_svc.get_chore(db, chore_id)
    me = household_svc.require_membership(db, chore.household_id, user)
    log = task_svc.add_log(
        db, chore, me, body.member_id if body else None, clock.today_in(me.household.timezone)
    )
    return task_svc.log_out(log)


@router.delete("/chore-logs/{log_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_log(log_id: uuid.UUID, db: DbSession, user: CurrentUser):
    log = task_svc.get_log(db, log_id)
    me = household_svc.require_membership(db, log.chore.household_id, user)
    task_svc.remove_log(db, log, me)
