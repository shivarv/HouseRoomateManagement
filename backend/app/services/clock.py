from datetime import date, datetime
from zoneinfo import ZoneInfo


def today_in(timezone: str) -> date:
    """The current calendar date in a household's timezone. Patched in tests."""
    return datetime.now(ZoneInfo(timezone)).date()
