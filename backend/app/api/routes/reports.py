import uuid
from datetime import datetime

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, DbSession
from app.schemas.chore import ActivityOut, ReportMonths, ReportOut
from app.services import activity, clock, report
from app.services import households as household_svc
from app.services import tasks as task_svc
from app.services.errors import Forbidden

router = APIRouter(tags=["activity & reports"])


@router.get("/households/{household_id}/activity", response_model=list[ActivityOut])
def get_activity(
    household_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
    limit: int = Query(default=50, ge=1, le=activity.MAX_FEED),
    before: datetime | None = None,
    month: str | None = Query(default=None, description="YYYY-MM: every event in that month"),
):
    """What happened in the house, newest first.

    Without `month`: the latest `limit` events (everyone). With `month`: every event in that
    calendar month of the household's timezone; past months are admin only, like the report.
    """
    me = household_svc.require_membership(db, household_id, user)
    if month is None:
        return [activity.event_out(e) for e in activity.feed(db, household_id, limit, before)]
    household = me.household
    today = clock.today_in(household.timezone)
    month_start = report.parse_month(month)
    if month_start > today:
        return []
    if report.month_key(month_start) != report.month_key(today) and me.role != "admin":
        raise Forbidden("Only admins can see past months")
    events = activity.month_feed(db, household_id, month_start, household.timezone)
    return [activity.event_out(e) for e in events]


@router.get("/households/{household_id}/report", response_model=ReportOut)
def get_report(
    household_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
    month: str | None = Query(default=None, description="YYYY-MM; defaults to the current month"),
):
    """Current month: everyone. Past months (History): admins only."""
    me = household_svc.require_membership(db, household_id, user)
    household = me.household
    today = clock.today_in(household.timezone)
    month_start = report.parse_month(month) if month else today.replace(day=1)
    if report.month_key(month_start) != report.month_key(today) and me.role != "admin":
        raise Forbidden("Only admins can see past months")
    task_svc.sync(db, household, today)
    return report.month_report(db, household, month_start, today)


@router.get("/households/{household_id}/report/months", response_model=ReportMonths)
def get_report_months(household_id: uuid.UUID, db: DbSession, user: CurrentUser):
    me = household_svc.require_membership(db, household_id, user, admin=True)
    today = clock.today_in(me.household.timezone)
    return ReportMonths(months=report.available_months(db, household_id, today))
