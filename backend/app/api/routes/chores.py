import uuid
from datetime import date

from fastapi import APIRouter, Query, status

from app.api.deps import CurrentUser, DbSession
from app.models import Chore, Household
from app.schemas.chore import (
    ChoreCreate,
    ChoreOut,
    ChoreUpdate,
    HouseholdTasksToday,
    MyTasksToday,
    RotationUpdate,
    ScheduleOut,
    TaskOut,
)
from app.schemas.household import MemberBrief
from app.services import chores as chore_svc
from app.services import clock
from app.services import households as household_svc
from app.services import tasks as task_svc

router = APIRouter(tags=["chores"])


def _chores_out(db, household: Household) -> list[ChoreOut]:
    today = clock.today_in(household.timezone)
    task_svc.ensure_tasks(db, household, today)
    today_by_chore = {t.chore_id: t.member for t in task_svc.tasks_on(db, household.id, today)}
    return [
        _chore_out(c, today_by_chore.get(c.id)) for c in chore_svc.list_chores(db, household.id)
    ]


def _chore_out(chore: Chore, today_member) -> ChoreOut:
    return ChoreOut(
        id=chore.id,
        name=chore.name,
        frequency=chore.frequency,
        is_active=chore.is_active,
        rotation=[MemberBrief.model_validate(r.member) for r in chore.rotation],
        today_assignee=MemberBrief.model_validate(today_member) if today_member else None,
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
        db, household, body.name.strip(), body.member_ids, clock.today_in(household.timezone)
    )
    db.commit()
    return _single_chore_out(db, chore)


@router.patch("/chores/{chore_id}", response_model=ChoreOut)
def update_chore(chore_id: uuid.UUID, body: ChoreUpdate, db: DbSession, user: CurrentUser):
    chore = chore_svc.get_chore(db, chore_id)
    household_svc.require_membership(db, chore.household_id, user, admin=True)
    if body.name is not None:
        chore.name = body.name.strip()
    if body.is_active is not None:
        chore.is_active = body.is_active
    db.commit()
    return _single_chore_out(db, chore)


@router.put("/chores/{chore_id}/rotation", response_model=ChoreOut)
def update_rotation(chore_id: uuid.UUID, body: RotationUpdate, db: DbSession, user: CurrentUser):
    chore = chore_svc.get_chore(db, chore_id)
    me = household_svc.require_membership(db, chore.household_id, user, admin=True)
    chore_svc.set_rotation(db, chore, body.member_ids, clock.today_in(me.household.timezone))
    db.commit()
    return _single_chore_out(db, chore)


@router.delete("/chores/{chore_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_chore(chore_id: uuid.UUID, db: DbSession, user: CurrentUser):
    chore = chore_svc.get_chore(db, chore_id)
    household_svc.require_membership(db, chore.household_id, user, admin=True)
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
    task_svc.ensure_tasks(db, household, today)
    tasks = [
        task_svc.task_out(t, household, me) for t in task_svc.tasks_on(db, household.id, today)
    ]
    return HouseholdTasksToday(date=today, tasks=tasks)


@router.get("/me/tasks/today", response_model=MyTasksToday)
def my_tasks_today(db: DbSession, user: CurrentUser):
    """The in-app reminder: what the logged-in person has to do today, across their households."""
    mine: list[TaskOut] = []
    today_by_member = {}
    me_by_member = {}
    for me in household_svc.memberships(db, user):
        household = me.household
        today = clock.today_in(household.timezone)
        today_by_member[me.id] = today
        me_by_member[me.id] = me
        task_svc.ensure_tasks(db, household, today)
        mine += [
            task_svc.task_out(t, household, me)
            for t in task_svc.tasks_on(db, household.id, today)
            if t.member_id == me.id
        ]
    overdue = [
        task_svc.task_out(t, me_by_member[t.member_id].household, me_by_member[t.member_id])
        for t in task_svc.overdue_for(db, today_by_member)
    ]
    return MyTasksToday(tasks=mine, overdue=overdue)


@router.post("/tasks/{task_id}/complete", response_model=TaskOut)
def complete_task(task_id: uuid.UUID, db: DbSession, user: CurrentUser):
    return _set_task_status(task_id, db, user, done=True)


@router.post("/tasks/{task_id}/reopen", response_model=TaskOut)
def reopen_task(task_id: uuid.UUID, db: DbSession, user: CurrentUser):
    return _set_task_status(task_id, db, user, done=False)


def _set_task_status(task_id: uuid.UUID, db, user, done: bool) -> TaskOut:
    task = task_svc.get_task(db, task_id)
    me = household_svc.require_membership(db, task.chore.household_id, user)
    task_svc.set_status(db, task, me, done)
    return task_svc.task_out(task, me.household, me)
