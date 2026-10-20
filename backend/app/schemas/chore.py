import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.household import MemberBrief


class ChoreCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    # Ordered rotation. Omit to rotate through every active member in the order they were added.
    member_ids: list[uuid.UUID] | None = None


class ChoreUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    is_active: bool | None = None


class RotationUpdate(BaseModel):
    member_ids: list[uuid.UUID]


class ChoreOut(BaseModel):
    id: uuid.UUID
    name: str
    frequency: Literal["daily"]
    is_active: bool
    rotation: list[MemberBrief]
    today_assignee: MemberBrief | None


class ChoreBrief(BaseModel):
    id: uuid.UUID
    name: str


class TaskOut(BaseModel):
    id: uuid.UUID
    household_id: uuid.UUID
    household_name: str
    chore: ChoreBrief
    member: MemberBrief
    due_date: date
    status: Literal["pending", "done"]
    completed_at: datetime | None
    next_assignee: MemberBrief | None
    is_mine: bool


class HouseholdTasksToday(BaseModel):
    date: date
    tasks: list[TaskOut]


class MyTasksToday(BaseModel):
    tasks: list[TaskOut]
    overdue: list[TaskOut]


class ScheduleSlot(BaseModel):
    chore: ChoreBrief
    member: MemberBrief
    status: Literal["pending", "done"] | None  # None = not yet generated (future day)


class ScheduleDay(BaseModel):
    date: date
    slots: list[ScheduleSlot]


class ScheduleOut(BaseModel):
    days: list[ScheduleDay]
