import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.household import MemberBrief

Frequency = Literal["daily", "weekly"]
AssignmentMode = Literal["rotation", "open"]
TaskStatus = Literal["pending", "done"]


class ChoreCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    frequency: Frequency = "daily"
    assignment_mode: AssignmentMode = "rotation"
    target_per_week: int | None = Field(default=None, ge=1, le=100)
    # Ordered rotation. Omit to rotate through every active member in the order they were added.
    member_ids: list[uuid.UUID] | None = None


class ChoreUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    is_active: bool | None = None
    frequency: Frequency | None = None
    assignment_mode: AssignmentMode | None = None
    target_per_week: int | None = Field(default=None, ge=0, le=100)  # 0 clears the target


class RotationUpdate(BaseModel):
    member_ids: list[uuid.UUID]


class ChoreOut(BaseModel):
    id: uuid.UUID
    name: str
    frequency: Frequency
    assignment_mode: AssignmentMode
    target_per_week: int | None
    is_active: bool
    rotation: list[MemberBrief]
    today_assignee: MemberBrief | None  # whose turn it is in the current period (rotation only)


class ChoreBrief(BaseModel):
    id: uuid.UUID
    name: str
    frequency: Frequency = "daily"
    assignment_mode: AssignmentMode = "rotation"


class TaskSwap(BaseModel):
    """This turn changed hands through a swap."""

    id: uuid.UUID
    role: Literal["given", "payback"]  # given: took it over from `other`; payback: paying them back
    other: MemberBrief
    can_cancel: bool = False  # I'm one of the two people in the swap


class TaskOut(BaseModel):
    id: uuid.UUID
    household_id: uuid.UUID
    household_name: str
    chore: ChoreBrief
    member: MemberBrief  # whose turn it is
    due_date: date  # period start
    period_end: date  # same as due_date for daily chores, Sunday for weekly
    status: TaskStatus
    completed_at: datetime | None
    completed_by: MemberBrief | None
    next_assignee: MemberBrief | None
    is_mine: bool
    swap: TaskSwap | None = None
    swap_request_id: uuid.UUID | None = None  # an open "Ask for a swap" on this turn


class CompleteTask(BaseModel):
    completed_by_member_id: uuid.UUID | None = None  # defaults to the caller


class LogCreate(BaseModel):
    member_id: uuid.UUID | None = None  # who did it; defaults to the caller


class LogOut(BaseModel):
    id: uuid.UUID
    member: MemberBrief
    logged_by: MemberBrief | None
    done_on: date
    created_at: datetime


class OpenChoreCount(BaseModel):
    member: MemberBrief
    this_year: int
    this_month: int
    last_done: date | None


class OpenChoreOut(BaseModel):
    """An open chore as shown on the Today screen: anyone can do it."""

    household_id: uuid.UUID
    household_name: str
    chore: ChoreBrief
    target_per_week: int | None
    today_logs: list[LogOut]
    this_week_count: int
    last_done: LogOut | None
    # Everyone, fewest this year first: tap your name when you did it.
    people: list[OpenChoreCount]
    suggested: MemberBrief | None  # first in `people`; a hint, not an assignment
    suggested_reason: str | None


class HouseholdTasksToday(BaseModel):
    date: date
    tasks: list[TaskOut]
    open: list[OpenChoreOut]


class UpcomingTurn(BaseModel):
    household_id: uuid.UUID
    household_name: str
    chore: ChoreBrief
    due_date: date  # period start of my next turn


class MyTasksToday(BaseModel):
    tasks: list[TaskOut]  # my turns now (today / this week)
    others: list[TaskOut]  # everyone else's turns now, so My day shows every chore
    upcoming: list[UpcomingTurn]  # my next turn per rotation chore, soonest first
    overdue: list[TaskOut]
    open: list[OpenChoreOut]


class ScheduleSlot(BaseModel):
    chore: ChoreBrief
    member: MemberBrief
    status: TaskStatus | None  # None = not yet generated (future)
    swapped_with: MemberBrief | None = None  # set when this turn changed hands through a swap


class ScheduleDay(BaseModel):
    date: date
    slots: list[ScheduleSlot]


class ScheduleOut(BaseModel):
    days: list[ScheduleDay]


SwapStatus = Literal["open", "accepted", "cancelled", "expired"]


class SwapCreate(BaseModel):
    due_date: date  # period start of my turn
    note: str | None = Field(default=None, max_length=200)


class SwapOut(BaseModel):
    id: uuid.UUID
    household_id: uuid.UUID
    household_name: str
    chore: ChoreBrief
    given_date: date  # the turn being given away (period start)
    period_end: date
    requester: MemberBrief
    acceptor: MemberBrief | None
    payback_date: date | None  # set once accepted: the acceptor's turn the requester now does
    status: SwapStatus
    note: str | None
    created_at: datetime
    is_mine: bool  # I asked
    can_accept: bool  # I can take it
    payback_preview: date | None  # the turn I'd give back if I took it


class ActivityOut(BaseModel):
    id: uuid.UUID
    action: str
    created_at: datetime
    actor: MemberBrief | None
    subject: MemberBrief | None
    assignee: MemberBrief | None
    chore_id: uuid.UUID | None
    chore_name: str | None
    due_date: date | None
    detail: str | None
    via: str | None = None  # "voice" / "typed": done through the assistant


class ReportRow(BaseModel):
    member: MemberBrief
    is_active: bool
    done: int  # times this person did the chore this month
    share: float  # done / total done for the chore (0..1)
    turns: int | None  # rotation: own turns so far this month
    missed: int | None  # rotation: own turns that ended without being done
    covered_by_others: int | None  # rotation: own turns someone else did
    covered_for_others: int | None  # rotation: other people's turns this person did
    last_done: date | None


class ChoreReport(BaseModel):
    chore: ChoreBrief
    is_active: bool
    total_done: int
    total_missed: int | None
    rows: list[ReportRow]  # sorted by `done`, most first


class LeaderboardRow(BaseModel):
    member: MemberBrief
    is_active: bool
    done: int
    missed: int
    covered_for_others: int


class ReportOut(BaseModel):
    month: str  # YYYY-MM
    start: date
    end: date
    is_current: bool
    fair_share: float  # 1 / active people
    chores: list[ChoreReport]
    leaderboard: list[LeaderboardRow]


class ReportMonths(BaseModel):
    months: list[str]  # YYYY-MM, newest first
